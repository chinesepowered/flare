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

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from web3 import Web3
from web3.exceptions import Web3RPCError

from flare_ai_defai.ai import GeminiProvider
from flare_ai_defai.attestation import Vtpm, VtpmAttestationError
from flare_ai_defai.blockchain import FlareProvider, BlazeDEXProvider
from flare_ai_defai.prompts import PromptService, SemanticRouterResponse
from flare_ai_defai.settings import settings

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
        self.logger = logger.bind(router="chat")
        self._setup_routes()

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
            SemanticRouterResponse.CONVERSATION: self.handle_conversation,
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
        send_token_response = self.ai.generate(
            prompt=prompt, response_mime_type=mime_type, response_schema=schema
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

        tx = self.blockchain.create_send_flr_tx(
            to_address=send_token_json.get("to_address"),
            amount=send_token_json.get("amount"),
        )
        self.logger.debug("send_token_tx", tx=tx)
        self.blockchain.add_tx_to_queue(msg=message, tx=tx)
        formatted_preview = (
            "Transaction Preview: "
            + f"Sending {Web3.from_wei(tx.get('value', 0), 'ether')} "
            + f"FLR to {tx.get('to')}\nType CONFIRM to proceed."
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
        if not all(key in swap_json for key in ["from_token", "to_token", "amount"]):
            try:
                prompt, _, _ = self.prompts.get_formatted_prompt("follow_up_token_swap")
                follow_up_response = self.ai.generate(prompt=prompt)
                return {"response": follow_up_response.text}
            except KeyError:
                # Fallback if prompt is missing
                return {"response": "I need more information to process your swap. Please specify the token you want to swap from, the token you want to swap to, and the amount."}
        
        from_token = swap_json["from_token"]
        to_token = swap_json["to_token"]
        amount = swap_json["amount"]
        
        # Initialize BlazeDEX provider
        blazedex = BlazeDEXProvider(self.blockchain.w3)
        
        try:
            # Get a quote for the swap
            expected_output, price_impact = blazedex.get_swap_quote(
                from_token, to_token, amount
            )
            
            # If swapping a token other than FLR, we need to approve it first
            if from_token != "FLR":
                # Check if approval is needed
                token_address = blazedex.get_token_address(from_token)
                token_contract = blazedex.get_token_contract(token_address)
                
                # Get token decimals
                decimals = token_contract.functions.decimals().call()
                amount_in_token_units = int(amount * (10 ** decimals))
                
                # Check current allowance
                allowance = token_contract.functions.allowance(
                    self.blockchain.address, 
                    blazedex.router.address
                ).call()
                
                if allowance < amount_in_token_units:
                    # Create approval transaction
                    approval_tx = blazedex.approve_token(
                        from_token, amount, self.blockchain.address
                    )
                    
                    # Add approval transaction to queue
                    self.blockchain.add_tx_to_queue(
                        msg=f"Approve {from_token} for swap", tx=approval_tx
                    )
                    
                    approval_preview = (
                        f"Transaction Preview (1/2): Approve {amount} {from_token} "
                        f"for trading on BlazeDEX\nType CONFIRM to proceed."
                    )
                    return {"response": approval_preview}
            
            # Create the swap transaction
            swap_tx = blazedex.create_swap_tx(
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
            # Use a default amount of 1.0 for price quotes
            amount = 1.0
            
            # Initialize BlazeDEX provider
            blazedex = BlazeDEXProvider(self.blockchain.w3)
            
            # Get a quote for the swap
            expected_output, price_impact = blazedex.get_swap_quote(
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
