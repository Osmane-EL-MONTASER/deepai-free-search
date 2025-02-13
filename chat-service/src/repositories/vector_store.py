import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any
import logging
from src.core.config import settings
from functools import lru_cache
import json
from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from chromadb import HttpClient

logger = logging.getLogger(__name__)

class VectorStoreManager:
    def __init__(self):
        self._client = None
        self._collection = None
        self._embedding_fn = None
        
    async def initialize(self):
        """Initialize connection to ChromaDB using LangChain with local embeddings"""
        try:
            # Initialize embedding function
            self._embedding_fn = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
            
            # Create HTTP client directly instead of using Settings
            chroma_client = HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port
            )
            
            # Initialize Chroma client with direct HTTP client
            self._client = Chroma(
                collection_name=settings.chroma_collection,
                embedding_function=self._embedding_fn,
                client=chroma_client,
                collection_metadata={"hnsw:space": "cosine"}
            )
            
            # Get the underlying chromadb collection
            self._collection = self._client._collection
            
            logger.info("ChromaDB initialized with local embeddings")
        except Exception as e:
            logger.error(f"ChromaDB initialization failed: {str(e)}")
            raise

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
            # Use LangChain's built-in similarity search with metadata filtering
            results = self._client.similarity_search_with_score(
                query=query,
                k=k,
                filter={"conversation_id": conversation_id}
            )

            return [
                {
                    "text": doc.page_content,
                    "metadata": doc.metadata,
                    "score": 1 - score
                }
                for doc, score in results
            ]
        except Exception as e:
            logger.error("Context retrieval failed", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "conversation_id": conversation_id,
                "query": query
            })
            return []

    async def upsert_documents(self, documents: List[Dict[str, Any]], conversation_id: str):
        """Store documents with metadata in ChromaDB"""
        if not self.is_connected:
            raise ConnectionError("ChromaDB not connected")

        try:
            ids = [str(doc["id"]) for doc in documents]
            metadatas = [{**doc["metadata"], "conversation_id": conversation_id} for doc in documents]
            texts = [doc["text"] for doc in documents]
            
            # Use LangChain's add_texts method which handles embeddings automatically
            self._client.add_texts(
                texts=texts,
                metadatas=metadatas,
                ids=ids
            )
            logger.info(f"Upserted {len(documents)} documents for conversation {conversation_id}")
        except Exception as e:
            logger.error(f"Document upsert failed: {str(e)}")
            raise 