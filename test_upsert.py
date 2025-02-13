import requests
import uuid

# Create test conversation
conv_id = str(uuid.uuid4())

# Store test knowledge
test_docs = [{
    "id": "test_000",
    "text": """
                PUT YOUR KNOWLEDGE HERE
            """,
    "metadata": {
        "timestamp": "2025-02-13"
    }
}]

# Upsert test documents
upsert_response = requests.post(
    "http://localhost:8000/chat/upsert",
    json={
        "documents": test_docs,
        "conversation_id": "5b4332bb-12df-4173-9186-d63f6586ca40"
    }
)
print(f"Upsert Status: {upsert_response.status_code}")

# Add after upsert response check
if upsert_response.status_code != 200:
    print(f"Upsert failed: {upsert_response.text}")
    exit(1)