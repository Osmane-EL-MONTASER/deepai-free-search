import requests
import uuid
import json

# Create test conversation
conv_id = str(uuid.uuid4())

chat_response = requests.post(
    "http://localhost:8000/chat/message",
    json={
        "messages": [
            {"role": "user", "content": "What do you know about my project"}
        ],
        "conversation_id": "5b4332bb-12df-4173-9186-d63f6586ca40"
    },
    stream=True
)

# Print responses
print("Chat Response:")
for line in chat_response.iter_lines():
    if line:
        decoded_line = line.decode('utf-8')
        if decoded_line.startswith('data: '):
            try:
                event_data = json.loads(decoded_line[6:])  # Remove 'data: ' prefix
                if event_data.get('event') == 'message':
                    print(event_data['data']['content'], end='', flush=True)
            except json.JSONDecodeError:
                pass  # Ignore invalid JSON lines