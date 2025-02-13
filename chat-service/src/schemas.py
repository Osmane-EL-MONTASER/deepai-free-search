from pydantic import BaseModel
from typing import List, Dict, Any

class DocumentUpsertRequest(BaseModel):
    documents: List[Dict[str, Any]]
    conversation_id: str 