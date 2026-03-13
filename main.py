from anthropic import AnthropicVertex

client = AnthropicVertex(region="global", project_id="duetai-399118")
message = client.messages.create(
 max_tokens=1024,
 messages=[{"role": "user", "content": "Hello! Can you help me?"}],
 model="claude-sonnet-4-6"
)
print(message.content[0].text)