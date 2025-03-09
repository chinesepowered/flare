"""
Gemini AI Provider Module

This module implements the Gemini AI provider for the AI Agent API, integrating
with Google's Generative AI service. It handles chat sessions, content generation,
and message management while maintaining a consistent AI personality.
"""

from typing import Any
from typing_extensions import override  # Import override from typing_extensions
from enum import Enum

import google.generativeai as genai
import structlog
from google.generativeai.types import ContentDict

from flare_ai_defai.ai.base import BaseAIProvider, ModelResponse

logger = structlog.get_logger(__name__)


SYSTEM_INSTRUCTION = """
You are Artemis, an AI assistant specialized in helping users navigate
the Flare blockchain ecosystem. As an expert in blockchain data and operations,
you assist users with:

- Account creation and management on the Flare network
- Token swaps and transfers
- Understanding blockchain data structures and smart contracts
- Explaining technical concepts in accessible terms
- Monitoring network status and transaction processing

Your personality combines technical precision with light wit - you're
knowledgeable but approachable, occasionally using clever remarks while staying
focused on providing accurate, actionable guidance. You prefer concise responses
that get straight to the point, but can elaborate when technical concepts
need more explanation.

When helping users:
- Prioritize security best practices
- Verify user understanding of important steps
- Provide clear warnings about risks when relevant
- Format technical information (addresses, hashes, etc.) in easily readable ways

If users request operations you cannot directly perform, clearly explain what
steps they need to take themselves while providing relevant guidance.

You maintain professionalism while allowing your subtle wit to make interactions
more engaging - your goal is to be helpful first, entertaining second.
"""


class EmbeddingTaskType(str, Enum):
    """
    Enumeration for the different embedding task types.
    """

    RETRIEVAL_QUERY = "retrieval_query"
    RETRIEVAL_DOCUMENT = "retrieval_document"
    SEMANTIC_SIMILARITY = "semantic_similarity"
    CLASSIFICATION = "classification"
    CLUSTERING = "clustering"


class GeminiProvider(BaseAIProvider):
    """
    Provider class for Google's Gemini AI service.

    This class implements the BaseAIProvider interface to provide AI capabilities
    through Google's Gemini models. It manages chat sessions, generates content,
    and maintains conversation history.

    Attributes:
        chat (genai.ChatSession | None): Active chat session
        model (genai.GenerativeModel): Configured Gemini model instance
        chat_history (list[ContentDict]): History of chat interactions
        logger (BoundLogger): Structured logger for the provider
    """

    def __init__(self, api_key: str, model: str, **kwargs: str) -> None:
        """
        Initialize the Gemini provider with API credentials and model configuration.

        Args:
            api_key (str): Google API key for authentication
            model (str): Gemini model identifier to use
            **kwargs (str): Additional configuration parameters including:
                - system_instruction: Custom system prompt for the AI personality
        """
        genai.configure(api_key=api_key)
        self.chat: genai.ChatSession | None = None
        self.model = genai.GenerativeModel(
            model_name=model,
            system_instruction=kwargs.get("system_instruction", SYSTEM_INSTRUCTION),
        )
        self.chat_history: list[ContentDict] = [
            ContentDict(parts=["Hi, I'm Artemis"], role="model")
        ]
        self.logger = logger.bind(service="gemini")

    @override
    def reset(self) -> None:
        """
        Reset the provider state.

        Clears chat history and terminates active chat session.
        """
        self.chat_history = []
        self.chat = None
        self.logger.debug(
            "reset_gemini", chat=self.chat, chat_history=self.chat_history
        )

    @override
    def generate(
        self,
        prompt: str,
        response_mime_type: str | None = None,
        response_schema: Any | None = None,
    ) -> ModelResponse:
        """
        Generate content using the Gemini model.

        Args:
            prompt (str): Input prompt for content generation
            response_mime_type (str | None): Expected MIME type for the response
            response_schema (Any | None): Schema defining the response structure

        Returns:
            ModelResponse: Generated content with metadata including:
                - text: Generated text content
                - raw_response: Complete Gemini response object
                - metadata: Additional response information including:
                    - candidate_count: Number of generated candidates
                    - prompt_feedback: Feedback on the input prompt
        """
        response = self.model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type=response_mime_type, response_schema=response_schema
            ),
        )
        self.logger.debug("generate", prompt=prompt, response_text=response.text)
        return ModelResponse(
            text=response.text,
            raw_response=response,
            metadata={
                "candidate_count": len(response.candidates),
                "prompt_feedback": response.prompt_feedback,
            },
        )

    @override
    def send_message(
        self,
        msg: str,
    ) -> ModelResponse:
        """
        Send a message in a chat session and get the response.

        Initializes a new chat session if none exists, using the current chat history.

        Args:
            msg (str): Message to send to the chat session

        Returns:
            ModelResponse: Response from the chat session including:
                - text: Generated response text
                - raw_response: Complete Gemini response object
                - metadata: Additional response information including:
                    - candidate_count: Number of generated candidates
                    - prompt_feedback: Feedback on the input message
        """
        if not self.chat:
            self.chat = self.model.start_chat(history=self.chat_history)
        response = self.chat.send_message(msg)
        self.logger.debug("send_message", msg=msg, response_text=response.text)
        return ModelResponse(
            text=response.text,
            raw_response=response,
            metadata={
                "candidate_count": len(response.candidates),
                "prompt_feedback": response.prompt_feedback,
            },
        )

    def embed_content(
        self,
        contents: str,
        embedding_model: str = "models/embedding-001",
        task_type: EmbeddingTaskType = EmbeddingTaskType.RETRIEVAL_DOCUMENT,
    ) -> list[float]:
        """
        Generate embeddings for the given content using Google's Gemini embedding models.

        Args:
            contents (str): The content to embed
            embedding_model (str): The embedding model to use (e.g., "models/embedding-001")
            task_type (EmbeddingTaskType): The type of embedding task

        Returns:
            list[float]: The embedding vector
        """
        try:
            # Create a new embedding model instance
            model = genai.GenerativeModel(model_name=embedding_model)
            
            # Generate embeddings using the embed_content method
            response = model.embed_content(
                content=contents,
                task_type=task_type.value
            )
            
            return response.embedding
        except Exception as e:
            self.logger.error("embed_content_failed", error=str(e))
            return []

    def check_sanctions_qdrant(self, address: str, qdrant_client: Any, collection_name: str = "sanctions", threshold: float = 0.95) -> tuple[bool, list[dict]]:
        """
        Check if an address is in the sanctions list using Qdrant vector similarity search.
        
        Args:
            address (str): The blockchain address to check
            qdrant_client: The Qdrant client instance
            collection_name (str): The name of the Qdrant collection containing sanctioned addresses
            threshold (float): The similarity threshold for considering an address as sanctioned
            
        Returns:
            tuple[bool, list[dict]]: A tuple containing:
                - Boolean indicating if the address is sanctioned
                - List of similar sanctioned addresses with their similarity scores
        """
        try:
            # Generate embedding for the address
            address_embedding = self.embed_content(address)
            
            if not address_embedding:
                self.logger.error("sanctions_check_failed", error="Failed to generate embedding for address")
                return False, []
                
            # Search for similar addresses in the sanctions collection
            search_results = qdrant_client.search(
                collection_name=collection_name,
                query_vector=address_embedding,
                limit=5  # Return top 5 matches
            )
            
            # Check if any results exceed the similarity threshold
            matches = []
            is_sanctioned = False
            
            for result in search_results:
                similarity = result.score
                if similarity >= threshold:
                    is_sanctioned = True
                
                matches.append({
                    "address": result.payload.get("address", "Unknown"),
                    "similarity": similarity,
                    "reason": result.payload.get("reason", "Unknown")
                })
                
            return is_sanctioned, matches
            
        except Exception as e:
            self.logger.error("sanctions_check_failed", error=str(e))
            return False, []
            
    def check_sanctions_text(self, address: str, sanctions_file_path: str = "sanctioned_addresses_ETH.txt") -> tuple[bool, list[dict]]:
        """
        Check if an address is in the sanctions list using in-memory text comparison.
        
        Args:
            address (str): The blockchain address to check
            sanctions_file_path (str): Path to the text file containing sanctioned addresses
            
        Returns:
            tuple[bool, list[dict]]: A tuple containing:
                - Boolean indicating if the address is sanctioned
                - List containing the matched address if found
        """
        try:
            # Normalize the input address (lowercase, remove whitespace)
            normalized_address = address.lower().strip()
            
            # Load the sanctions list from file
            sanctioned_addresses = []
            try:
                with open(sanctions_file_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line:  # Skip empty lines
                            continue
                            
                        parts = line.split(',')
                        addr = parts[0].lower().strip()
                        reason = parts[1] if len(parts) > 1 else "Sanctioned address"
                        sanctioned_addresses.append({"address": addr, "reason": reason})
            except FileNotFoundError:
                self.logger.error("sanctions_file_not_found", path=sanctions_file_path)
                return False, []
                
            # Check if the address is in the sanctions list
            for sanctioned in sanctioned_addresses:
                if normalized_address == sanctioned["address"]:
                    return True, [{"address": sanctioned["address"], "similarity": 1.0, "reason": sanctioned["reason"]}]
                    
            return False, []
            
        except Exception as e:
            self.logger.error("sanctions_check_failed", error=str(e))
            return False, []
            
    def check_sanctions(self, address: str, query_context: str = "", qdrant_client: Any = None, **kwargs: Any) -> tuple[bool, list[dict]]:
        """
        Check if an address is in the sanctions list using the appropriate method based on context.
        
        Args:
            address (str): The blockchain address to check
            query_context (str): The context of the user's query to determine which method to use
            qdrant_client: The Qdrant client instance (required for Qdrant-based checks)
            **kwargs: Additional arguments to pass to the specific check method
            
        Returns:
            tuple[bool, list[dict]]: A tuple containing:
                - Boolean indicating if the address is sanctioned
                - List of matched addresses with their details
        """
        # Determine which method to use based on the query context
        if "qdrant" in query_context.lower() and qdrant_client:
            self.logger.info("using_qdrant_sanctions_check", address=address)
            return self.check_sanctions_qdrant(address, qdrant_client, **kwargs)
        else:
            self.logger.info("using_text_sanctions_check", address=address)
            sanctions_file_path = kwargs.get("sanctions_file_path", "sanctioned_addresses_ETH.txt")
            return self.check_sanctions_text(address, sanctions_file_path)
