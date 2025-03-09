"""
Chat Router Module

This module implements the main chat routing system for the AI Agent API.
It handles message routing, blockchain interactions, attestations, and AI responses.

The module provides a ChatRouter class that integrates various services:
- AI capabilities through GeminiProvider
- Blockchain operations through FlareProvider
- Attestation services through Vtpm
- Prompt management through PromptService
"""

import json
import re
import hashlib
import uuid

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from web3 import Web3
from web3.exceptions import Web3RPCError

from flare_ai_defai.ai import GeminiProvider, EmbeddingTaskType
from flare_ai_defai.attestation import Vtpm, VtpmAttestationError
from flare_ai_defai.blockchain import FlareProvider, BlazeDEXProvider
from flare_ai_defai.blockchain.blazedex import TOKEN_ADDRESSES
from flare_ai_defai.prompts import PromptService, SemanticRouterResponse
from flare_ai_defai.settings import settings

# New imports for Qdrant and RAG
from flare_ai_defai.qdrant_client import initialize_qdrant_client
from flare_ai_defai.rag_utils import embed_chunks
from qdrant_client import models

logger = structlog.get_logger(__name__)
router = APIRouter()


class ChatMessage(BaseModel):
    """
    Pydantic model for chat message validation.

    Attributes:
        message (str): The chat message content, must not be empty
    """

    message: str = Field(..., min_length=1)


class ChatRouter:
    """
    Main router class handling chat messages and their routing to appropriate handlers.

    This class integrates various services and provides routing logic for different
    types of chat messages including blockchain operations, attestations, and general
    conversation.

    Attributes:
        ai (GeminiProvider): Provider for AI capabilities
        blockchain (FlareProvider): Provider for blockchain operations
        blazedex (BlazeDEXProvider): Provider for DEX operations
        attestation (Vtpm): Provider for attestation services
        prompts (PromptService): Service for managing prompts
        logger (BoundLogger): Structured logger for the chat router
    """

    def __init__(
        self,
        ai: GeminiProvider,
        blockchain: FlareProvider,
        attestation: Vtpm,
        prompts: PromptService,
        blazedex: BlazeDEXProvider,
        qdrant_client: initialize_qdrant_client,
    ) -> None:
        """
        Initialize the ChatRouter with required service providers.

        Args:
            ai: Provider for AI capabilities
            blockchain: Provider for blockchain operations
            attestation: Provider for attestation services
            prompts: Service for managing prompts
        """
        self._router = APIRouter()
        self.ai = ai
        self.blockchain = blockchain
        self.attestation = attestation
        self.prompts = prompts
        self.blazedex = blazedex
        self.qdrant_client = qdrant_client
        self.logger = logger.bind(router="chat")
        self.sanctioned_addresses = self.load_sanctioned_addresses()
        # Initialize Qdrant client and Sentence Transformer model
        self.collection_name = "flare_knowledge"  # You can configure this in settings
        # self.embedding_client = GeminiEmbedding(api_key=settings.gemini_api_key)

        # Load account from private key during initialization
        try:
            # Replace with your private key or retrieve it from a secure source
            private_key = settings.flare_private_key
            account = self.blockchain.w3.eth.account.from_key(private_key)
            self.blockchain.address = account.address
            self.blockchain.private_key = private_key
            self.logger.info("Account loaded during initialization", address=self.blockchain.address)
        except Exception as e:
            self.logger.error("Account loading failed during initialization", error=str(e))

        self._setup_routes()
        self.load_sanctioned_addresses_into_qdrant()

    def _setup_routes(self) -> None:
        """
        Set up FastAPI routes for the chat endpoint.
        Handles message routing, command processing, and transaction confirmations.
        """

        @self._router.post("/")
        async def chat(message: ChatMessage) -> dict[str, str]:  # pyright: ignore [reportUnusedFunction]
            """
            Process incoming chat messages and route them to appropriate handlers.

            Args:
                message: Validated chat message

            Returns:
                dict[str, str]: Response containing handled message result

            Raises:
                HTTPException: If message handling fails
            """
            try:
                self.logger.debug("received_message", message=message.message)

                if message.message.startswith("/"):
                    return await self.handle_command(message.message)
                if (
                    self.blockchain.tx_queue
                    and message.message == self.blockchain.tx_queue[-1].msg
                ):
                    try:
                        tx_hash = self.blockchain.send_tx_in_queue()
                    except Web3RPCError as e:
                        self.logger.exception("send_tx_failed", error=str(e))
                        msg = (
                            f"Unfortunately the tx failed with the error:\n{e.args[0]}"
                        )
                        return {"response": msg}

                    prompt, mime_type, schema = self.prompts.get_formatted_prompt(
                        "tx_confirmation",
                        tx_hash=tx_hash,
                        block_explorer=settings.web3_explorer_url,
                    )
                    tx_confirmation_response = self.ai.generate(
                        prompt=prompt,
                        response_mime_type=mime_type,
                        response_schema=schema,
                    )
                    return {"response": tx_confirmation_response.text}
                if self.attestation.attestation_requested:
                    try:
                        resp = self.attestation.get_token([message.message])
                    except VtpmAttestationError as e:
                        resp = f"The attestation failed with  error:\n{e.args[0]}"
                    self.attestation.attestation_requested = False
                    return {"response": resp}

                route = await self.get_semantic_route(message.message)
                return await self.route_message(route, message.message)

            except Exception as e:
                self.logger.exception("message_handling_failed", error=str(e))
                raise HTTPException(status_code=500, detail=str(e)) from e

    @property
    def router(self) -> APIRouter:
        """Get the FastAPI router with registered routes."""
        return self._router

    async def handle_command(self, command: str) -> dict[str, str]:
        """
        Handle special command messages starting with '/'.

        Args:
            command: Command string to process

        Returns:
            dict[str, str]: Response containing command result
        """
        if command == "/reset":
            self.blockchain.reset()
            self.ai.reset()
            return {"response": "Reset complete"}
        return {"response": "Unknown command"}

    async def get_semantic_route(self, message: str) -> SemanticRouterResponse:
        """
        Determine the semantic route for a message using AI provider.

        Args:
            message: Message to route

        Returns:
            SemanticRouterResponse: Determined route for the message
        """
        try:
            prompt, mime_type, schema = self.prompts.get_formatted_prompt(
                "semantic_router", user_input=message
            )
            route_response = self.ai.generate(
                prompt=prompt, response_mime_type=mime_type, response_schema=schema
            )
            return SemanticRouterResponse(route_response.text)
        except Exception as e:
            self.logger.exception("routing_failed", error=str(e))
            return SemanticRouterResponse.CONVERSATIONAL

    async def route_message(
        self, route: SemanticRouterResponse, message: str
    ) -> dict[str, str]:
        """
        Route a message to the appropriate handler based on semantic route.
        
        Args:
            route: Determined semantic route
            message: Original message to handle
            
        Returns:
            dict[str, str]: Response from the appropriate handler
        """
        handlers = {
            SemanticRouterResponse.GENERATE_ACCOUNT: self.handle_generate_account,
            SemanticRouterResponse.SEND_TOKEN: self.handle_send_token,
            SemanticRouterResponse.TOKEN_SWAP: self.handle_token_swap,
            SemanticRouterResponse.PRICE_QUOTE: self.handle_price_quote,
            SemanticRouterResponse.REQUEST_ATTESTATION: self.handle_attestation,
            SemanticRouterResponse.CHECK_LIQUIDITY: self.handle_check_liquidity,
            SemanticRouterResponse.CONVERSATION: self.handle_conversation,
            SemanticRouterResponse.CHECK_SANCTIONS: self.handle_check_sanctions,
        }
        
        handler = handlers.get(route)
        if not handler:
            return {"response": "Unsupported route"}
        
        return await handler(message)

    async def handle_generate_account(self, _: str) -> dict[str, str]:
        """
        Handle account generation requests.

        Args:
            _: Unused message parameter

        Returns:
            dict[str, str]: Response containing new account information
                or existing account
        """
        if self.blockchain.address:
            return {"response": f"Account exists - {self.blockchain.address}"}
        address = self.blockchain.generate_account()
        prompt, mime_type, schema = self.prompts.get_formatted_prompt(
            "generate_account", address=address
        )
        gen_address_response = self.ai.generate(
            prompt=prompt, response_mime_type=mime_type, response_schema=schema
        )
        return {"response": gen_address_response.text}

    async def handle_send_token(self, message: str) -> dict[str, str]:
        """
        Handle token sending requests.

        Args:
            message: Message containing token sending details

        Returns:
            dict[str, str]: Response containing transaction preview or follow-up prompt
        """
        if not self.blockchain.address:
            await self.handle_generate_account(message)

        prompt, mime_type, schema = self.prompts.get_formatted_prompt(
            "token_send", user_input=message
        )
        self.logger.debug("Formatted prompt", prompt=prompt)
        send_token_response = self.ai.generate(
            prompt=prompt, response_mime_type=mime_type, response_schema=schema
        )
        self.logger.debug("Response format",send_token_response)
        send_token_json = json.loads(send_token_response.text)
        expected_json_len = 2
        if (
            len(send_token_json) != expected_json_len
            or send_token_json.get("amount") == 0.0
        ):
            try:
                prompt, _, _ = self.prompts.get_formatted_prompt("follow_up_token_send")
                follow_up_response = self.ai.generate(prompt)
                return {"response": follow_up_response.text}
            except KeyError:
                # Fallback if prompt is missing
                return {"response": "I need more information to process your transfer. Please specify the destination address and the amount of FLR you want to send."}

        to_address = send_token_json.get("to_address")
        amount = send_token_json.get("amount")

        # Check if the recipient address is sanctioned
        # First, check against the in-memory list
        if await self.is_sanctioned_address(to_address):
            return {"response": "I cannot process this transaction as the recipient address is sanctioned."}

        # Query Qdrant for similar sanctioned addresses
        query_embedding = embed_chunks([to_address])[0][1]  # Embed the address
        search_result = self.qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=3  # Limit to top 3 results
        )

        # Extract sanctioned addresses from the search results
        similar_sanctioned_addresses = [
            hit.payload["text"] for hit in search_result
        ]

        # Augment the prompt with sanctioned addresses
        prompt_augmentation = (
            "The following addresses are known to be sanctioned or "
            f"similar to sanctioned addresses: {', '.join(similar_sanctioned_addresses)}. "
            "Consider this information when generating your response. If the user is attempting to send tokens to an address similar to a sanctioned address, warn them."
        )

        # Get the base prompt
        base_prompt, mime_type, schema = self.prompts.get_formatted_prompt(
            "token_send", user_input=message
        )

        # Combine the base prompt with the augmentation
        augmented_prompt = base_prompt + "\n" + prompt_augmentation

        # Generate the response using the augmented prompt
        send_token_response = self.ai.generate(
            prompt=augmented_prompt, response_mime_type=mime_type, response_schema=schema
        )
        send_token_json = json.loads(send_token_response.text)

        expected_json_len = 2
        if (
            len(send_token_json) != expected_json_len
            or send_token_json.get("amount") == 0.0
        ):
            try:
                prompt, _, _ = self.prompts.get_formatted_prompt("follow_up_token_send")
                follow_up_response = self.ai.generate(prompt)
                return {"response": follow_up_response.text}
            except KeyError:
                # Fallback if prompt is missing
                return {"response": "I need more information to process your transfer. Please specify the destination address and the amount of FLR you want to send."}

        to_address = send_token_json.get("to_address")
        amount = send_token_json.get("amount")

        # If swapping from FLR, we need to approve WFLR
        from_token_for_approval = "WFLR"
        if message.startswith("FLR"):
            from_token_for_approval = "FLR"

        # Check if approval is needed
        token_address = self.blazedex.get_token_address(from_token_for_approval)
        token_contract = self.blazedex.get_token_contract(token_address)
        
        # Get token decimals
        decimals = token_contract.functions.decimals().call()
        amount_in_token_units = int(amount * (10 ** decimals))
        
        # Check current allowance
        allowance = token_contract.functions.allowance(
            self.blockchain.address, 
            self.blazedex.router_contract.address
        ).call()
        
        if allowance < amount_in_token_units:
            # Create approval transaction
            approval_tx = self.blazedex.approve_token(
                from_token_for_approval, amount, self.blockchain.address
            )
            
            # Add approval transaction to queue
            self.blockchain.add_tx_to_queue(
                msg=f"Approve {from_token_for_approval} for swap", tx=approval_tx
            )
            
            approval_preview = (
                f"Transaction Preview (1/2): Approve {amount} {from_token_for_approval} "
                f"for trading on BlazeDEX\nType CONFIRM to proceed."
            )
            return {"response": approval_preview}

        tx = self.blockchain.create_send_flr_tx(
            to_address=to_address,
            amount=amount,
        )
        self.logger.debug("send_token_tx", tx=tx)
        self.blockchain.add_tx_to_queue(msg=message, tx=tx)
        formatted_preview = (
            "Transaction Preview: "
            + f"Sending {Web3.from_wei(tx.get('value', 0), 'ether')} "
            + f"{from_token_for_approval} to {tx.get('to')}\nType CONFIRM to proceed."
        )
        return {"response": formatted_preview}

    async def handle_token_swap(self, message: str) -> dict[str, str]:
        """
        Handle token swap requests.
        
        Args:
            message: Message containing token swap details
            
        Returns:
            dict[str, str]: Response containing transaction preview or follow-up prompt
        """
        if not self.blockchain.address:
            return await self.handle_generate_account(message)
        
        # Get the token swap parameters from the message
        prompt, mime_type, schema = self.prompts.get_formatted_prompt(
            "token_swap", user_input=message
        )
        swap_response = self.ai.generate(
            prompt=prompt, response_mime_type=mime_type, response_schema=schema
        )
        swap_json = json.loads(swap_response.text)
        
        # Validate the swap parameters
        from_token = swap_json.get("from_token")
        to_token = swap_json.get("to_token")
        amount = swap_json.get("amount")

        # If amount is not provided in the JSON response, try to extract it from the message
        if from_token and to_token and not amount:
            # Try to extract the amount from the message using a simple regex
            amount_match = re.search(r'(\d+(\.\d+)?)\s+' + re.escape(from_token), message, re.IGNORECASE)
            if amount_match:
                amount = float(amount_match.group(1))
                self.logger.debug("extracted_amount_from_message", amount=amount)

        if not all([from_token, to_token, amount]):
            try:
                prompt, _, _ = self.prompts.get_formatted_prompt("follow_up_token_swap")
                follow_up_response = self.ai.generate(prompt=prompt)
                return {"response": follow_up_response.text}
            except KeyError:
                # Fallback if prompt is missing
                return {"response": "I need more information to process your swap. Please specify the token you want to swap from, the token you want to swap to, and the amount."}

        try:
            # Get a quote for the swap
            expected_output, price_impact = self.blazedex.get_swap_quote(
                from_token, to_token, amount
            )
            
            # If swapping a token other than FLR, we need to approve it first
            if from_token != "FLR":
                # Check if approval is needed
                from_token_for_approval = from_token
                if from_token == "FLR":
                    from_token_for_approval = "WFLR"
                
                token_address = self.blazedex.get_token_address(from_token_for_approval)
                token_contract = self.blazedex.get_token_contract(token_address)
                
                # Get token decimals
                decimals = token_contract.functions.decimals().call()
                amount_in_token_units = int(amount * (10 ** decimals))
                
                # Check current allowance
                allowance = token_contract.functions.allowance(
                    self.blockchain.address, 
                    self.blazedex.router_contract.address
                ).call()
                
                if allowance < amount_in_token_units:
                    # Create approval transaction
                    approval_tx = self.blazedex.approve_token(
                        from_token_for_approval, amount, self.blockchain.address
                    )
                    
                    # Add approval transaction to queue
                    self.blockchain.add_tx_to_queue(
                        msg=f"Approve {from_token_for_approval} for swap", tx=approval_tx
                    )
                    
                    approval_preview = (
                        f"Transaction Preview (1/2): Approve {amount} {from_token_for_approval} "
                        f"for trading on BlazeDEX\nType CONFIRM to proceed."
                    )
                    return {"response": approval_preview}
            
            # Create the swap transaction
            swap_tx = self.blazedex.create_swap_tx(
                from_token, to_token, amount, self.blockchain.address
            )
            
            # Add swap transaction to queue
            self.blockchain.add_tx_to_queue(msg=message, tx=swap_tx)
            
            # Format the transaction preview
            if from_token == "FLR":
                value_display = f"{Web3.from_wei(swap_tx.get('value', 0), 'ether')} {from_token}"
            else:
                value_display = f"{amount} {from_token}"
                
            swap_preview = (
                f"Transaction Preview: Swap {value_display} for approximately "
                f"{expected_output:.6f} {to_token} (Price Impact: {price_impact:.2f}%)\n"
                f"Type CONFIRM to proceed."
            )
            
            return {"response": swap_preview}
            
        except Exception as e:
            self.logger.error("token_swap_failed", error=str(e))
            error_response = f"Sorry, I couldn't process your swap request: {str(e)}"
            return {"response": error_response}

    async def handle_attestation(self, _: str) -> dict[str, str]:
        """
        Handle attestation requests.

        Args:
            _: Unused message parameter

        Returns:
            dict[str, str]: Response containing attestation request
        """
        prompt = self.prompts.get_formatted_prompt("request_attestation")[0]
        request_attestation_response = self.ai.generate(prompt=prompt)
        self.attestation.attestation_requested = True
        return {"response": request_attestation_response.text}

    async def handle_conversation(self, message: str) -> dict[str, str]:
        """
        Handle general conversation messages.

        Args:
            message: Message to process

        Returns:
            dict[str, str]: Response from AI provider
        """
        # Use RAG to enhance the conversation
        # context = self.get_relevant_context(message)
        # augmented_message = f"Context: {context}\nUser message: {message}"
        # self.logger.info(augmented_message)
        response = self.ai.send_message(message)
        return {"response": response.text}

    async def handle_price_quote(self, message: str) -> dict[str, str]:
        """
        Handle price quote requests for token swaps.
        
        Args:
            message: Message containing token swap details
            
        Returns:
            dict[str, str]: Response containing price quote information
        """
        if not self.blockchain.address:
            return await self.handle_generate_account(message)
        
        # Get the token swap parameters from the message
        prompt, mime_type, schema = self.prompts.get_formatted_prompt(
            "price_quote", user_input=message
        )
        
        try:
            swap_response = self.ai.generate(
                prompt=prompt, response_mime_type=mime_type, response_schema=schema
            )
            
            swap_json = json.loads(swap_response.text)
            
            # Validate the swap parameters
            if not all(key in swap_json for key in ["from_token", "to_token"]):
                prompt, _, _ = self.prompts.get_formatted_prompt("follow_up_token_swap")
                follow_up_response = self.ai.generate(prompt=prompt)
                return {"response": follow_up_response.text}
            
            from_token = swap_json["from_token"]
            to_token = swap_json["to_token"]
            
            # Try to extract the amount from the message if specified
            amount = 1.0  # Default amount for price quotes
            amount_match = re.search(r'(\d+(\.\d+)?)\s+' + re.escape(from_token), message, re.IGNORECASE)
            if amount_match:
                amount = float(amount_match.group(1))
                self.logger.debug("extracted_amount_from_message_for_price_quote", amount=amount)
            
            # Get a quote for the swap
            expected_output, price_impact = self.blazedex.get_swap_quote(
                from_token, to_token, amount
            )
            
            # Format the price quote response
            price_quote = (
                f"Price Quote: {amount} {from_token} ≈ {expected_output:.6f} {to_token}\n"
                f"Rate: 1 {from_token} ≈ {expected_output/amount:.6f} {to_token}\n"
                f"Price Impact: {price_impact:.2f}%\n\n"
                f"To execute this swap, say: \"Swap {amount} {from_token} to {to_token}\""
            )
            
            return {"response": price_quote}
            
        except Exception as e:
            self.logger.error("price_quote_failed", error=str(e))
            error_response = f"Sorry, I couldn't get a price quote: {str(e)}"
            return {"response": error_response}

    async def handle_check_liquidity(self, message: str) -> dict[str, str]:
        """
        Handle liquidity pool status check requests.
        
        Args:
            message: Message containing liquidity check request
            
        Returns:
            dict[str, str]: Response containing liquidity pool information
        """
        try:
            # For now, we'll use a simple approach to extract token pairs
            # Later, you can implement a more sophisticated extraction using AI
            tokens = []
            message = message.upper()
            
            # Look for common token symbols in the message
            for token in TOKEN_ADDRESSES.keys():
                if token in message:
                    tokens.append(token)
            
            # If we couldn't find exactly two tokens, provide a helpful response
            if len(tokens) != 2:
                return {
                    "response": "I couldn't clearly identify which token pair you're asking about. "
                    "Please specify both tokens clearly, for example: 'Check liquidity pool status for FLR to USDT'"
                }
            
            token_a, token_b = tokens[0], tokens[1]
            
            # Check if pair exists
            pair_exists = self.blazedex.check_pair_exists(token_a, token_b)
            
            if not pair_exists:
                return {
                    "response": f"The {token_a}/{token_b} pair doesn't exist on BlazeSwap. "
                    f"This means there isn't a direct trading route between these tokens. "
                    f"You might need to use an intermediate token like FLR or WFLR to trade between them."
                }
            
            # Get liquidity pool status
            pool_status = self.blazedex.get_liquidity_pool_status(token_a, token_b)
            
            # Format the response
            response = (
                f"Here's the current status of the {token_a}/{token_b} liquidity pool on BlazeSwap:\n\n"
                f"- Pool exists: Yes\n"
                f"- Pair address: {pool_status['pair_address']}\n"
                f"- {token_a} reserves: {pool_status['reserves_a']:,.2f} {token_a}\n"
                f"- {token_b} reserves: {pool_status['reserves_b']:,.2f} {token_b}\n"
                f"- Total liquidity: {pool_status['total_liquidity']:,.2f} LP tokens\n\n"
                f"This pool has {'good' if pool_status['total_liquidity'] > 0 else 'limited'} liquidity, "
                f"which means you {'should' if pool_status['total_liquidity'] > 0 else 'might not'} be able to trade "
                f"between {token_a} and {token_b} with minimal slippage for reasonable trade sizes."
            )
            
            return {"response": response}
        except Exception as e:
            self.logger.exception("check_liquidity_error", error=str(e))
            return {
                "response": f"I encountered an error while checking the liquidity pool status: {str(e)}. "
                f"Please make sure you're using valid token symbols."
            }

    def load_sanctioned_addresses(self) -> set[str]:
        """
        Load sanctioned addresses from a text file.

        Returns:
            set[str]: A set of sanctioned addresses in lowercase
        """
        try:
            with open("src/flare_ai_defai/sanctioned_addresses_ETH.txt", "r") as f:
                addresses = {line.strip().lower() for line in f}
            self.logger.info(
                "Sanctioned addresses loaded", count=len(addresses)
            )  # Log the number of addresses loaded
            return addresses
        except FileNotFoundError:
            self.logger.warning("Sanctioned addresses file not found")
            return set()
        except Exception as e:
            self.logger.error(
                "Failed to load sanctioned addresses", error=str(e)
            )  # Log any exceptions
            return set()

    def load_sanctioned_addresses_into_qdrant(self) -> None:
        """
        Load sanctioned addresses into Qdrant for RAG.
        """
        try:
            # Read sanctioned addresses from the file
            with open("src/flare_ai_defai/sanctioned_addresses_ETH.txt", "r") as f:
                addresses = [line.strip() for line in f]

            # Chunk the addresses
            chunks = addresses  # Simplest chunking: one address per chunk

            # Embed the chunks using Gemini Provider
            embedded_chunks = embed_chunks(chunks)

            # Prepare points for Qdrant
            points = []
            for i, (chunk, embedding) in enumerate(embedded_chunks):
                point_id = uuid.uuid4().hex  # Use UUID for point_id
                points.append(
                    models.PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={"text": chunk}
                    )
                )

            # Upload points to Qdrant
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True  # Wait until points are indexed
            )

            self.logger.info(
                "Sanctioned addresses loaded into Qdrant", count=len(addresses)
            )

        except FileNotFoundError:
            self.logger.warning("Sanctioned addresses file not found")
        except Exception as e:
            self.logger.error(
                "Failed to load sanctioned addresses into Qdrant", error=str(e)
            )

    async def is_sanctioned_address(self, address: str) -> bool:
        """
        Check if an address is sanctioned.

        Args:
            address: The address to check

        Returns:
            bool: True if the address is sanctioned, False otherwise
        """
        return address.lower() in self.sanctioned_addresses

    def get_relevant_context(self, query: str, top_k: int = 3) -> str:
        """
        Retrieves relevant context from Qdrant based on the query.

        Args:
            query: The user's query.
            top_k: Number of results to retrieve.

        Returns:
            str: Concatenated text from the retrieved documents.
        """
        query_vector = self.ai.embed_content(
            contents=query,
        )
        search_result = self.qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k
        )
        context = "\n".join([hit.payload['text'] for hit in search_result])
        return context

    async def handle_check_sanctions(self, message: str) -> dict[str, str]:
        """
        Handle sanctions check requests.

        Args:
            message: Message containing sanctions check request

        Returns:
            dict[str, str]: Response containing sanctions check result
        """
        # Extract the address from the message
        address = None
        # Use a regex to find a potential address
        address_match = re.search(r'(0x[a-fA-F0-9]{40})', message)
        if address_match:
            address = address_match.group(1)

        if not address:
            return {"response": "Could not identify a valid address in your message."}

        # Determine which method to use based on the query context
        if "qdrant" in message.lower():
            # Use Qdrant for sanctions check
            is_sanctioned, matches = await self.check_sanctions_qdrant(address)
            if is_sanctioned:
                self.logger.debug("sanctions_check", method="qdrant", address=address, sanctioned=True, matches=matches)
                return {"response": f"The address {address} is sanctioned."}
            else:
                self.logger.debug("sanctions_check", method="qdrant", address=address, sanctioned=False)
                return {"response": f"The address {address} is not sanctioned."}
        else:
            # Use text file lookup for sanctions check
            is_sanctioned = await self.is_sanctioned_address(address)
            if is_sanctioned:
                self.logger.debug("sanctions_check", method="text_file", address=address, sanctioned=True)
                return {"response": f"The address {address} is sanctioned."}
            else:
                self.logger.debug("sanctions_check", method="text_file", address=address, sanctioned=False)
                return {"response": f"The address {address} is not sanctioned."}

    async def check_sanctions_qdrant(self, address: str, collection_name: str = "flare_knowledge", threshold: float = 0.95) -> tuple[bool, list[dict]]:
        """
        Check if an address is sanctioned using Qdrant.

        Args:
            address: The address to check
            collection_name: Name of the Qdrant collection
            threshold: Similarity threshold for matching

        Returns:
            tuple[bool, list[dict]]: True if the address is sanctioned, False otherwise
        """
        query_vector = self.ai.embed_content(
            contents=address,
        )
        search_results = self.qdrant_client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=10  # Adjust the limit as needed
        )
        matches = [hit.payload['text'] for hit in search_results]
        return (len(matches) > 0, matches)
