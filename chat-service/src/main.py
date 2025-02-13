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

# Initialize logging before anything else
configure_logging()
logger = logging.getLogger(__name__)

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
    conversation_id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),  # Generate ID if not provided
        pattern=r"^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-4[a-fA-F0-9]{3}-[89abAB][a-fA-F0-9]{3}-[a-fA-F0-9]{12}$"  # UUID validation
    )

@app.post("/message")
async def chat_endpoint(request: ChatRequest):
    ollama_service: OllamaStreamingService = app.state.ollama_service
    
    async def generate():
        async for chunk in ollama_service.generate_stream(
            messages=request.messages,
            conversation_id=request.conversation_id
        ):
            # Convert to SSE format
            yield f"data: {json.dumps(chunk)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )