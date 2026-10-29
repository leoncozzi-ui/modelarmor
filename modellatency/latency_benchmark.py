#!/usr/bin/env python3
"""Latency benchmark: Gemini single-region (europe-west2) vs EU multi-region.

Sends the identical request body (test_prompt.json) to both Vertex AI
endpoints *in parallel* for N rounds, measures client-side wall-clock latency,
and runs an equivalence "eval" on every round to make sure both endpoints did
comparable work (same prompt tokens, similar output size, same finish reason,
valid JSON matching the response schema, same classification). Rounds that
fail the eval are flagged so latency is only compared under like-for-like
conditions.

Usage:
  python latency_benchmark.py                       # 5 rounds, defaults
  python latency_benchmark.py --rounds 10 --bust-cache
  python latency_benchmark.py --stream              # also measures TTFT

Auth: `gcloud auth print-access-token` by default; `--auth adc` for
Application Default Credentials.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import copy
import csv
import dataclasses
import datetime as dt
import json
import math
import pathlib
import statistics
import subprocess
import sys
import threading
import time
import uuid
from typing import Any

import requests

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_PROJECT = "duetai-399118"
DEFAULT_MODEL = "gemini-3.5-flash"

# name -> (host, location)
ENDPOINTS: dict[str, tuple[str, str]] = {
    "europe-west2 (single-region)": ("europe-west2-aiplatform.googleapis.com", "europe-west2"),
    "eu (multi-region)": ("aiplatform.eu.rep.googleapis.com", "eu"),
}


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
def get_access_token(mode: str) -> str:
    """mode='gcloud' uses the active gcloud user; mode='adc' uses Application Default Credentials."""
    if mode == "adc":
        import google.auth
        import google.auth.transport.requests

        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        creds.refresh(google.auth.transport.requests.Request())
        return creds.token
    return subprocess.check_output(
        ["gcloud", "auth", "print-access-token"], text=True, stderr=subprocess.DEVNULL
    ).strip()


# --------------------------------------------------------------------------- #
# Request execution
# --------------------------------------------------------------------------- #
@dataclasses.dataclass
class CallResult:
    endpoint: str
    round: int
    ok: bool
    http_status: int | None
    latency_s: float
    ttft_s: float | None = None
    text: str = ""
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    cached_tokens: int = 0
    output_tokens: int | None = None
    thought_tokens: int = 0
    model_version: str | None = None
    response_id: str | None = None
    error: str | None = None

    @property
    def out_chars(self) -> int:
        return len(self.text)


def build_url(host: str, location: str, project: str, model: str, stream: bool) -> str:
    method = "streamGenerateContent?alt=sse" if stream else "generateContent"
    return f"https://{host}/v1/projects/{project}/locations/{location}/publishers/google/models/{model}:{method}"


def _fill_from_response(res: CallResult, chunks: list[dict[str, Any]]) -> None:
    texts: list[str] = []
    for chunk in chunks:
        for cand in chunk.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                if "text" in part and not part.get("thought"):
                    texts.append(part["text"])
            if cand.get("finishReason"):
                res.finish_reason = cand["finishReason"]
        if chunk.get("usageMetadata"):
            um = chunk["usageMetadata"]
            res.prompt_tokens = um.get("promptTokenCount")
            res.cached_tokens = um.get("cachedContentTokenCount", 0)
            res.output_tokens = um.get("candidatesTokenCount")
            res.thought_tokens = um.get("thoughtsTokenCount", 0)
        res.model_version = chunk.get("modelVersion", res.model_version)
        res.response_id = chunk.get("responseId", res.response_id)
    res.text = "".join(texts)


def call_endpoint(
    session: requests.Session,
    name: str,
    url: str,
    token: str,
    body: dict[str, Any],
    round_no: int,
    stream: bool,
    start_barrier: threading.Barrier | None,
    timeout: float,
) -> CallResult:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = json.dumps(body)
    if start_barrier is not None:
        start_barrier.wait()  # release both threads at the same instant
    t0 = time.perf_counter()
    try:
        if not stream:
            r = session.post(url, headers=headers, data=payload, timeout=timeout)
            latency = time.perf_counter() - t0
            res = CallResult(name, round_no, r.ok, r.status_code, latency)
            if r.ok:
                _fill_from_response(res, [r.json()])
            else:
                res.error = r.text[:500]
            return res

        ttft = None
        chunks: list[dict[str, Any]] = []
        with session.post(url, headers=headers, data=payload, timeout=timeout, stream=True) as r:
            if not r.ok:
                return CallResult(name, round_no, False, r.status_code, time.perf_counter() - t0, error=r.text[:500])
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                chunk = json.loads(line[5:].strip())
                if ttft is None and any(
                    p.get("text") for c in chunk.get("candidates", []) for p in c.get("content", {}).get("parts", [])
                ):
                    ttft = time.perf_counter() - t0
                chunks.append(chunk)
            latency = time.perf_counter() - t0
        res = CallResult(name, round_no, True, r.status_code, latency, ttft_s=ttft)
        _fill_from_response(res, chunks)
        return res
    except Exception as exc:  # noqa: BLE001
        return CallResult(name, round_no, False, None, time.perf_counter() - t0, error=repr(exc))


# --------------------------------------------------------------------------- #
# Eval: are both outputs comparable?
# --------------------------------------------------------------------------- #
def _schema_check(text: str, schema: dict[str, Any] | None) -> tuple[bool, dict[str, Any] | None, str]:
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        return False, None, f"invalid JSON ({exc.msg})"
    if not isinstance(obj, dict):
        return False, None, "JSON is not an object"
    if schema:
        missing = [k for k in schema.get("required", []) if k not in obj]
        if missing:
            return False, obj, f"missing keys {missing}"
        for key, spec in schema.get("properties", {}).items():
            if "enum" in spec and key in obj and obj[key] not in spec["enum"]:
                return False, obj, f"{key}={obj[key]!r} not in enum"
    return True, obj, "ok"


def eval_pair(a: CallResult, b: CallResult, schema: dict[str, Any] | None, tol_pct: float, tol_abs: int) -> dict[str, Any]:
    checks: dict[str, tuple[bool, str]] = {}
    checks["both_ok"] = (a.ok and b.ok, f"{a.http_status} / {b.http_status}")
    if not (a.ok and b.ok):
        return {"pass": False, "checks": checks}

    checks["same_prompt_tokens"] = (a.prompt_tokens == b.prompt_tokens, f"{a.prompt_tokens} / {b.prompt_tokens}")
    checks["same_cached_tokens"] = (
        (a.cached_tokens > 0) == (b.cached_tokens > 0),
        f"{a.cached_tokens} / {b.cached_tokens} (implicit cache hits skew prefill latency)",
    )
    checks["same_finish_reason"] = (a.finish_reason == b.finish_reason, f"{a.finish_reason} / {b.finish_reason}")
    checks["same_model_version"] = (a.model_version == b.model_version, f"{a.model_version} / {b.model_version}")

    ao, bo = a.output_tokens or 0, b.output_tokens or 0
    diff = abs(ao - bo)
    allowed = max(tol_abs, tol_pct / 100 * max(ao, bo))
    checks["output_tokens_within_tol"] = (diff <= allowed, f"{ao} / {bo} (diff {diff}, allowed {allowed:.0f})")

    at, bt = a.thought_tokens, b.thought_tokens
    tdiff = abs(at - bt)
    tallowed = max(tol_abs, tol_pct / 100 * max(at, bt))
    checks["thought_tokens_within_tol"] = (tdiff <= tallowed, f"{at} / {bt} (diff {tdiff}, allowed {tallowed:.0f})")

    a_valid, a_obj, a_msg = _schema_check(a.text, schema)
    b_valid, b_obj, b_msg = _schema_check(b.text, schema)
    checks["valid_schema_json"] = (a_valid and b_valid, f"{a_msg} / {b_msg}")
    sel_key = "selection" if schema and "selection" in schema.get("properties", {}) else None
    if sel_key and a_obj and b_obj:
        checks["same_classification"] = (
            a_obj.get(sel_key) == b_obj.get(sel_key),
            f"{a_obj.get(sel_key)} / {b_obj.get(sel_key)}",
        )
    return {"pass": all(ok for ok, _ in checks.values()), "checks": checks}


# --------------------------------------------------------------------------- #
# Stats helpers
# --------------------------------------------------------------------------- #
def describe(xs: list[float]) -> dict[str, float]:
    if not xs:
        return {}
    s = sorted(xs)
    p90 = s[min(len(s) - 1, math.ceil(0.9 * len(s)) - 1)]
    return {
        "n": len(xs),
        "mean": statistics.fmean(xs),
        "median": statistics.median(xs),
        "stdev": statistics.stdev(xs) if len(xs) > 1 else 0.0,
        "min": s[0],
        "p90": p90,
        "max": s[-1],
    }


def paired_t(diffs: list[float]) -> tuple[float, float] | None:
    """Returns (t statistic, approx two-sided p) for paired differences."""
    if len(diffs) < 2:
        return None
    sd = statistics.stdev(diffs)
    if sd == 0:
        return (math.inf, 0.0)
    n = len(diffs)
    t = statistics.fmean(diffs) / (sd / math.sqrt(n))
    # Student-t two-sided p via regularized incomplete beta (no scipy needed).
    df = n - 1
    x = df / (df + t * t)
    p = _betainc(df / 2, 0.5, x)
    return t, p


def _betainc(a: float, b: float, x: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b + lbeta)
    if x > (a + 1) / (a + b + 2):
        return 1.0 - _betainc(b, a, 1 - x)
    # Lentz continued fraction
    f, c, d = 1.0, 1.0, 0.0
    for i in range(200):
        m = i // 2
        if i == 0:
            num = 1.0
        elif i % 2 == 0:
            num = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + num * d
        d = 1.0 / (d if abs(d) > 1e-30 else 1e-30)
        c = 1.0 + num / c if abs(c) > 1e-30 else 1e-30
        f *= c * d
        if abs(1.0 - c * d) < 1e-10:
            break
    return front * (f - 1.0) / a


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prompt", default=str(HERE / "test_prompt.json"))
    ap.add_argument("--project", default=DEFAULT_PROJECT)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--rounds", type=int, default=5, help="measured rounds (min 3)")
    ap.add_argument("--warmup", type=int, default=1, help="unmeasured warm-up rounds (TLS/conn setup)")
    ap.add_argument("--stream", action="store_true", help="use streamGenerateContent and record TTFT")
    ap.add_argument(
        "--bust-cache",
        action="store_true",
        help="prefix a per-round nonce to the prompt so neither region gets an implicit-cache hit",
    )
    ap.add_argument("--pause", type=float, default=2.0, help="seconds between rounds")
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--tol-pct", type=float, default=25.0, help="output-size tolerance in %%")
    ap.add_argument("--tol-abs", type=int, default=15, help="output-size tolerance in tokens (floor)")
    ap.add_argument("--out-dir", default=str(HERE / "results"))
    ap.add_argument("--auth", choices=["gcloud", "adc"], default="gcloud", help="credential source")
    args = ap.parse_args()

    if args.rounds < 3:
        ap.error("--rounds must be >= 3")

    base_body = json.loads(pathlib.Path(args.prompt).read_text())
    schema = base_body.get("generationConfig", {}).get("responseSchema")
    token = get_access_token(args.auth)
    names = list(ENDPOINTS)
    urls = {n: build_url(h, loc, args.project, args.model, args.stream) for n, (h, loc) in ENDPOINTS.items()}
    sessions = {n: requests.Session() for n in names}

    print(f"Model: {args.model}  Project: {args.project}  Mode: {'stream' if args.stream else 'unary'}")
    for n in names:
        print(f"  {n:30s} {urls[n]}")
    print(f"Rounds: {args.rounds} (+{args.warmup} warm-up)  bust-cache: {args.bust_cache}\n")

    def body_for_round(r: int) -> dict[str, Any]:
        if not args.bust_cache:
            return base_body
        b = copy.deepcopy(base_body)
        part = b["contents"][0]["parts"][0]
        part["text"] = f"[benchmark-run-id: {uuid.uuid4()} round {r}]\n" + part["text"]
        return b

    results: list[CallResult] = []
    evals: list[dict[str, Any]] = []
    total = args.warmup + args.rounds
    with cf.ThreadPoolExecutor(max_workers=len(names)) as pool:
        for i in range(total):
            warm = i < args.warmup
            r_no = i - args.warmup + 1
            body = body_for_round(i)  # same body for both endpoints in a round
            barrier = threading.Barrier(len(names))
            futs = {
                n: pool.submit(
                    call_endpoint, sessions[n], n, urls[n], token, body, r_no, args.stream, barrier, args.timeout
                )
                for n in names
            }
            pair = {n: f.result() for n, f in futs.items()}
            a, b = pair[names[0]], pair[names[1]]
            label = "warm-up" if warm else f"round {r_no}/{args.rounds}"
            line = "  ".join(
                f"{n.split()[0]}={p.latency_s:6.3f}s" + (f" (ttft {p.ttft_s:.3f}s)" if p.ttft_s else "")
                + ("" if p.ok else f" ERR {p.http_status}")
                for n, p in pair.items()
            )
            if warm:
                print(f"[{label:>11}] {line}")
                auth_err = [p for p in (a, b) if p.http_status in (401, 403)]
                if auth_err:
                    for p in auth_err:
                        print(f"  ! {p.endpoint}: {p.error[:300] if p.error else ''}", file=sys.stderr)
                    print("Aborting: authentication/permission error during warm-up (try --auth gcloud|adc).",
                          file=sys.stderr)
                    return 2
            else:
                ev = eval_pair(a, b, schema, args.tol_pct, args.tol_abs)
                ev["round"] = r_no
                evals.append(ev)
                results.extend([a, b])
                print(f"[{label:>11}] {line}  delta={a.latency_s - b.latency_s:+.3f}s  eval={'PASS' if ev['pass'] else 'FAIL'}")
                for cname, (ok, detail) in ev["checks"].items():
                    if not ok:
                        print(f"{'':15}x {cname}: {detail}")
                for p in (a, b):
                    if p.error:
                        print(f"{'':15}! {p.endpoint}: {p.error[:200]}")
            if i < total - 1:
                time.sleep(args.pause)

    # ----------------------------------------------------------------- report
    by_ep = {n: [r for r in results if r.endpoint == n and r.ok] for n in names}
    passed_rounds = {e["round"] for e in evals if e["pass"]}
    print("\n" + "=" * 96)
    print("LATENCY SUMMARY (seconds, client-side wall clock)")
    print("=" * 96)
    hdr = f"{'endpoint':30s} {'subset':10s} {'n':>3} {'mean':>7} {'median':>7} {'stdev':>7} {'min':>7} {'p90':>7} {'max':>7}"
    print(hdr)
    for n in names:
        for subset, rows in (
            ("all", by_ep[n]),
            ("eval-pass", [r for r in by_ep[n] if r.round in passed_rounds]),
        ):
            d = describe([r.latency_s for r in rows])
            if d:
                print(
                    f"{n:30s} {subset:10s} {d['n']:>3} {d['mean']:7.3f} {d['median']:7.3f} {d['stdev']:7.3f} "
                    f"{d['min']:7.3f} {d['p90']:7.3f} {d['max']:7.3f}"
                )
        if args.stream:
            d = describe([r.ttft_s for r in by_ep[n] if r.ttft_s is not None])
            if d:
                print(f"{n:30s} {'ttft':10s} {d['n']:>3} {d['mean']:7.3f} {d['median']:7.3f} {d['stdev']:7.3f} "
                      f"{d['min']:7.3f} {d['p90']:7.3f} {d['max']:7.3f}")

    def paired(rounds: set[int]) -> list[float]:
        a_map = {r.round: r.latency_s for r in by_ep[names[0]]}
        b_map = {r.round: r.latency_s for r in by_ep[names[1]]}
        return [a_map[k] - b_map[k] for k in sorted(rounds) if k in a_map and k in b_map]

    print("\nPAIRED DIFFERENCE  (single-region minus multi-region; negative => single-region faster)")
    summary: dict[str, Any] = {}
    for subset, rounds in (("all", {e["round"] for e in evals}), ("eval-pass", passed_rounds)):
        diffs = paired(rounds)
        if not diffs:
            print(f"  {subset:10s} no comparable rounds")
            continue
        mean_a = statistics.fmean([r.latency_s for r in by_ep[names[0]] if r.round in rounds])
        mean_b = statistics.fmean([r.latency_s for r in by_ep[names[1]] if r.round in rounds])
        tt = paired_t(diffs)
        faster = names[0] if mean_a < mean_b else names[1]
        pct = abs(mean_a - mean_b) / max(mean_a, mean_b) * 100
        wins_a = sum(1 for x in diffs if x < 0)
        sig = f"t={tt[0]:+.2f}, p~{tt[1]:.3f}" if tt else "n/a"
        print(
            f"  {subset:10s} n={len(diffs)}  mean diff={statistics.fmean(diffs):+.3f}s  "
            f"median diff={statistics.median(diffs):+.3f}s  {sig}"
        )
        print(f"  {'':10s} {faster} is {pct:.1f}% faster on mean; single-region won {wins_a}/{len(diffs)} rounds")
        summary[subset] = {
            "n": len(diffs), "mean_diff_s": statistics.fmean(diffs), "median_diff_s": statistics.median(diffs),
            "t": tt[0] if tt else None, "p": tt[1] if tt else None, "faster": faster, "pct_faster": pct,
            "single_region_wins": wins_a,
        }

    print("\nEVAL (output equivalence per round)")
    print(f"  passed {len(passed_rounds)}/{len(evals)} rounds "
          f"(tolerance: max({args.tol_abs} tokens, {args.tol_pct:.0f}%))")
    for n in names:
        rows = by_ep[n]
        if rows:
            print(f"  {n:30s} out_tokens mean={statistics.fmean([r.output_tokens or 0 for r in rows]):6.1f}  "
                  f"out_chars mean={statistics.fmean([r.out_chars for r in rows]):6.1f}  "
                  f"prompt_tokens={rows[0].prompt_tokens}  cache_hits={sum(1 for r in rows if r.cached_tokens)}/{len(rows)}")

    # ----------------------------------------------------------------- persist
    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    csv_path = out / f"latency_{stamp}.csv"
    with csv_path.open("w", newline="") as fh:
        fields = [f.name for f in dataclasses.fields(CallResult)] + ["out_chars", "eval_pass"]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in results:
            row = dataclasses.asdict(r)
            row["out_chars"] = r.out_chars
            row["eval_pass"] = r.round in passed_rounds
            w.writerow(row)
    json_path = out / f"latency_{stamp}.json"
    json_path.write_text(json.dumps({
        "args": vars(args), "urls": urls, "summary": summary,
        "evals": [{**e, "checks": {k: {"ok": v[0], "detail": v[1]} for k, v in e["checks"].items()}} for e in evals],
        "results": [dataclasses.asdict(r) for r in results],
    }, indent=2))
    print(f"\nSaved: {csv_path}\n       {json_path}")
    return 0 if passed_rounds else 1


if __name__ == "__main__":
    sys.exit(main())
