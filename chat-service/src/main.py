from fastapi import FastAPI, status
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import logging
from src.core.config import configure_logging, settings
from typing import AsyncGenerator
from src.repositories.vector_store import VectorStoreManager
from src.services.streaming import OllamaStreamingService
from pydantic import BaseModel, Field
from typing import List, Optional
from fastapi.responses import StreamingResponse
import json
import uuid
from fastapi.responses import JSONResponse
from src.schemas import DocumentUpsertRequest

# Initialize logging before anything else
configure_logging()
logger = logging.getLogger(__name__)

# Add conversation storage at the top
conversations = {}  # Stores conversation history {conversation_id: {user_id: str, messages: list}}

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle startup and shutdown events"""
    logger.info("Starting application...")
    
    # Initialize ChromaDB
    vector_store = VectorStoreManager()
    chroma_connected = await vector_store.initialize()
    app.state.vector_store = vector_store
    
    logger.info(f"ChromaDB connection {'successful' if chroma_connected else 'failed'}")
    
    # Initialize OllamaStreamingService
    ollama_service = OllamaStreamingService(
        vector_store=vector_store)
    ollama_initialized = await ollama_service.initialize_model()
    app.state.ollama_service = ollama_service
    
    logger.info(f"Ollama initialization {'successful' if ollama_initialized else 'failed'}")
    
    yield
    
    logger.info("Shutting down...")
    # Cleanup would go here

def create_app() -> FastAPI:
    app = FastAPI(
        title="Chat Service",
        lifespan=lifespan,
        redoc_url=None if settings.is_production else "/redoc",
        docs_url=None if settings.is_production else "/docs"
    )
    
    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return app

# Initialize the application
app = create_app()

@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Health check endpoint"""
    vector_store: VectorStoreManager = app.state.vector_store
    ollama_service: OllamaStreamingService = app.state.ollama_service
    return {
        "status": "OK",
        "environment": settings.app_env,
        "chroma_connected": vector_store.is_connected,
        "ollama_available": ollama_service.is_initialized
    }

class ChatMessage(BaseModel):
    role: str  # 'system', 'user', 'assistant'
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    stream: Optional[bool] = True
    user_id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )
    conversation_id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )

@app.post("/message")
async def chat_endpoint(request: ChatRequest):
    ollama_service: OllamaStreamingService = app.state.ollama_service
    
    # Get or create conversation
    conv = conversations.get(request.conversation_id, {
        "user_id": request.user_id,  # Will use generated ID if not provided
        "messages": []
    })
    
    # Combine with history
    full_messages = [
        *[ChatMessage(**msg) for msg in conv["messages"]],
        *request.messages
    ]
    
    async def generate():
        full_response = []
        async for chunk in ollama_service.generate_stream(
            messages=full_messages,
            user_id=request.user_id,
            conversation_id=request.conversation_id
        ):
            # Collect response content
            if chunk.get("event") == "message":
                full_response.append(chunk["data"]["content"])
            
            yield f"data: {json.dumps(chunk)}\n\n"
        
        # Update conversation history after stream completes
        conv["messages"].extend([
            *[msg.dict() for msg in request.messages],
            {"role": "assistant", "content": "".join(full_response)}
        ])
        conversations[request.conversation_id] = conv
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "X-User-ID": request.user_id,
            "X-Conversation-ID": request.conversation_id
        }
    )

@app.post("/upsert")
async def upsert_documents(data: DocumentUpsertRequest):
    """Endpoint for testing document insertion"""
    try:
        await app.state.vector_store.upsert_documents(
            documents=data.documents,
            user_id=data.user_id
        )
        return {"status": "success"}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )