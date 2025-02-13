import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from typing import List, Optional, Dict, Any
import logging
from src.core.config import settings
from functools import lru_cache

logger = logging.getLogger(__name__)

class VectorStoreManager:
    def __init__(self):
        self._client = None
        self._collection = None
        self._embedding_fn = None
        
    async def initialize(self):
        """Initialize connection to ChromaDB"""
        try:
            # Configure client
            self._client = chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port,
                settings=Settings(allow_reset=True, anonymized_telemetry=False)
            )

            # Initialize embedding function
            self._embedding_fn = embedding_functions.OllamaEmbeddingFunction(
                url=settings.ollama_host,
                model_name=settings.embedding_model
            )
            
            # Get or create collection
            self._collection = self._client.get_or_create_collection(
                name=settings.chroma_collection,
                embedding_function=self._embedding_fn,
                metadata={"hnsw:space": "cosine"}
            )
            
            logger.info(f"Connected to ChromaDB collection: {settings.chroma_collection}")
            return True
        except Exception as e:
            logger.error(f"ChromaDB connection failed: {str(e)}")
            return False

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._collection is not None

    @lru_cache(maxsize=settings.chroma_cache_size)
    async def get_embeddings(self, text: str) -> List[float]:
        """Get embeddings for a single text input with caching"""
        if not self.is_connected:
            raise ConnectionError("ChromaDB not connected")
            
        return self._embedding_fn([text])[0]

    async def get_relevant_context(self, query: str, conversation_id: str, k: int = 3) -> List[Dict[str, Any]]:
        """Retrieve relevant context from vector store"""
        if not self.is_connected:
            return []

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=k,
                where={"conversation_id": conversation_id},
                include=["documents", "metadatas", "distances"]
            )
            return [
                {
                    "text": doc,
                    "metadata": meta,
                    "score": 1 - distance
                }
                for doc, meta, distance in zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0]
                )
            ]
        except Exception as e:
            logger.error(f"Context retrieval failed: {str(e)}")
            return []

    async def upsert_documents(self, documents: List[Dict[str, Any]], conversation_id: str):
        """Store documents with metadata in ChromaDB"""
        if not self.is_connected:
            raise ConnectionError("ChromaDB not connected")

        try:
            ids = [str(doc["id"]) for doc in documents]
            metadatas = [{**doc["metadata"], "conversation_id": conversation_id} for doc in documents]
            texts = [doc["text"] for doc in documents]
            
            self._collection.upsert(
                ids=ids,
                metadatas=metadatas,
                documents=texts
            )
            logger.info(f"Upserted {len(documents)} documents for conversation {conversation_id}")
        except Exception as e:
            logger.error(f"Document upsert failed: {str(e)}")
            raise 