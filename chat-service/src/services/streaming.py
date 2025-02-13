from langchain_community.chat_models import ChatOllama
from typing import AsyncIterator
import logging
from src.repositories.vector_store import VectorStoreManager
from src.core.config import settings
import httpx
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import asyncio

logger = logging.getLogger(__name__)

class StreamConnectionError(Exception):
    """Custom error for stream failures"""
    pass

class OllamaStreamingService:
    """Orchestrates streaming LLM responses with context injection
    
    Responsibilities:
    - Manage streaming connections to Ollama
    - Integrate retrieved context
    - Handle streaming protocol
    - Implement safety checks
    """
    
    def __init__(self, vector_store: VectorStoreManager):
        """Initialize with dependencies
        
        Args:
            vector_store: Connected vector store instance
        """
        self._vector_store = vector_store
        self.is_initialized = False
        
    async def initialize_model(self):
        """Initialize LangChain Ollama connection with validation
        
        We need to do:
            1. Verify Ollama server availability
            2. Check if specified model is available
            3. Initialize LangChain ChatOllama client
            4. Perform test inference to validate functionality
        
        Raises:
            ConfigurationError: For invalid model or connection issues
            RuntimeError: For unexpected initialization failures
        """
        max_retries = 5
        retry_delay = 3  # seconds
        
        for attempt in range(max_retries):
            try:
                # 1. Verify Ollama server connectivity
                try:
                    async with httpx.AsyncClient() as client:
                        health_res = await client.get(
                            f"{str(settings.ollama_host).rstrip('/')}/api/tags",
                            timeout=settings.request_timeout
                        )
                        health_res.raise_for_status()
                except httpx.HTTPError as e:
                    raise ConnectionError(
                        f"Ollama server unreachable at {settings.ollama_host}"
                    ) from e

                # 2. Validate model availability
                available_models = {model["name"] for model in health_res.json().get("models", [])}
                if settings.llm_model not in available_models:
                    raise ValueError(
                        f"Model {settings.llm_model} not found. Available models: {', '.join(available_models)}"
                    )

                # 3. Initialize LangChain client with safety settings
                self._llm = ChatOllama(
                    base_url=str(settings.ollama_host).rstrip('/'),
                    model=settings.llm_model,
                    temperature=0,  # Safe default
                    streaming=True,
                    max_retries=3,
                    request_timeout=settings.request_timeout,
                    system="You are a helpful assistant. Respond concisely.",
                    stop=["<|im_end|>", "<|endoftext|>"],  # Common EOS tokens
                    headers={"Content-Type": "application/json"},
                    safe_mode=True  # Ollama's built-in content safety
                )

                # 4. Validate model functionality
                test_message = [HumanMessage(content="ping")]
                test_response = await self._llm.ainvoke(test_message)
                
                if not test_response or not test_response.content:
                    raise RuntimeError("Model returned empty response to test prompt")

                logger.info(f"Ollama initialized | Model: {settings.llm_model} | Version: {test_response.response_metadata.get('model')}")
                self.is_initialized = True
                return True

            except (ConnectionError, httpx.HTTPError) as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Ollama connection attempt {attempt+1}/{max_retries} failed. Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    continue
                raise

    def calculate_retry_timeout(self, retry_timeout: int) -> int:
        """Calculate retry timeout based on current time
        
        Args:
            retry_timeout: Current retry timeout in ms
            
        Returns:
            New retry timeout in ms
        """
        max_timeout = 20000
        return min(2 * retry_timeout, max_timeout)

    async def generate_stream(
        self,
        messages: list,
        conversation_id: str) -> AsyncIterator[dict]:
        """Main streaming generation method
        
        Implementation Details:
        1. Converts OpenAI-format messages to LangChain messages
        2. Uses LangChain's async streaming interface
        3. Implements chunk processing with error recovery
        4. Handles SSE event formatting
        5. Maintains streaming session state
        """
        # Validate LLM initialization
        if not hasattr(self, '_llm') or self._llm is None:
            logger.error("Ollama client not initialized")
            raise StreamConnectionError("LLM service unavailable")
        
        lc_messages = []
        logger.debug(f"Received {len(messages)} messages for conversation {conversation_id}")
        
        try:
            for i, msg in enumerate(messages):
                logger.debug(f"Processing message {i+1}: role={msg.role} content={msg.content[:50]}...")
                
                if msg.role == 'user':
                    lc_messages.append(HumanMessage(content=msg.content))
                elif msg.role == 'assistant':
                    lc_messages.append(AIMessage(content=msg.content))
                elif msg.role == 'system':
                    lc_messages.append(SystemMessage(content=msg.content))
                else:
                    logger.warning(f"Ignored unknown role: {msg.role}")
        except KeyError as e:
            logger.error(f"Invalid message format: {str(e)}")
            raise StreamConnectionError("Invalid message structure") from e

        # Streaming configuration
        retry_timeout = settings.request_timeout  # Initial retry timeout in ms
        
        try:
            # Add context retrieval at start of stream
            context = await self._vector_store.get_relevant_context(
                query=messages[-1].content,  # Last user message
                conversation_id=conversation_id  # Use conversation ID for context
            )
            
            # Start streaming
            async for chunk in self._llm.astream(lc_messages):
                # Handle normal response chunk
                yield {
                    "event": "message",
                    "data": {
                        "content": chunk.content,
                        "conversation_id": conversation_id,
                        "model": settings.llm_model
                    },
                    "retry": retry_timeout
                }
                
                # Reset retry timeout on successful chunk
                retry_timeout = settings.request_timeout

            # Final completion event
            yield {
                "event": "end",
                "data": {
                    "status": "completed",
                    "conversation_id": conversation_id  # Include in final message
                },
                "retry": retry_timeout
            }

        except httpx.ReadTimeout:
            logger.warning("Stream timeout, initiating recovery")
            yield {
                "event": "error",
                "data": {"error": "stream_timeout"},
                "retry": self.calculate_retry_timeout(retry_timeout)
            }
            raise StreamConnectionError("Stream timeout") from None
            
        except Exception as e:
            logger.error(f"Stream error: {str(e)}")
            yield {
                "event": "error",
                "data": {"error": "stream_failure"},
                "retry": self.calculate_retry_timeout(retry_timeout)
            }
            raise StreamConnectionError("Stream terminated") from e