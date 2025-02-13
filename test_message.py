import requests
import uuid
import json

chat_response = requests.post(
    "http://localhost:8000/chat/message",
    json={
        "messages": [
            {"role": "user", "content": """Hello Deepseek! What is my name?"""}
        ],
        "user_id": "2d372ddb-7cb6-46a9-8897-bdbc594ff37d",
        "conversation_id": "99f08a62-7fec-4563-9b53-80471ed0a2a3"
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
        if event_data.get('event') == 'end':
            print(event_data['data']['user_id'])
            print(event_data['data']['conversation_id'])
