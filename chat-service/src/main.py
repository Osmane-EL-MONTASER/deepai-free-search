from fastapi import FastAPI, status
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import logging
from src.core.config import configure_logging, settings
from typing import AsyncGenerator
from src.repositories.vector_store import VectorStoreManager

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
    return {
        "status": "OK",
        "environment": settings.app_env,
        "chroma_connected": vector_store.is_connected if vector_store else False,
        "ollama_available": False  # We'll implement this next
    } 