import requests

response = requests.post(
    "http://localhost:8000/chat/message",
    json={
        "messages": [
            {"role": "user", "content": "Hello, who are you? Nice to meet you! Can you explain Virtual Reality and Quantum Computing?"}
        ]
    },
    stream=True  # Enable streaming
)

# Print each chunk as it arrives
for line in response.iter_lines():
    if line:
        decoded_line = line.decode('utf-8').strip()
        print(decoded_line)