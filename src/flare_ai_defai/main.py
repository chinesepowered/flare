"""
AI Agent API Main Application Module

This module initializes and configures the FastAPI application for the AI Agent API.
It sets up CORS middleware, integrates various providers (AI, blockchain, attestation),
and configures the chat routing system.

Dependencies:
    - FastAPI for the web framework
    - Structlog for structured logging
    - CORS middleware for cross-origin resource sharing
    - Custom providers for AI, blockchain, and attestation services
"""

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from flare_ai_defai import (
    ChatRouter,
    FlareProvider,
    GeminiProvider,
    PromptService,
    Vtpm,
)
from flare_ai_defai.settings import settings

logger = structlog.get_logger(__name__)


def validate_required_prompts(prompt_service):
    """Validate that all required prompts are registered in the library."""
    required_prompts = [
        "semantic_router", 
        "token_send", 
        "token_swap", 
        "generate_account",
        "conversational",
        "request_attestation",
        "tx_confirmation",
        "price_quote",
        "follow_up_token_swap",
        "follow_up_token_send"
    ]
    
    missing_prompts = []
    for prompt_name in required_prompts:
        try:
            prompt_service.library.get_prompt(prompt_name)
        except KeyError:
            missing_prompts.append(prompt_name)
    
    if missing_prompts:
        logger.warning(f"Missing required prompts: {', '.join(missing_prompts)}")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application instance.

    This function:
    1. Creates a new FastAPI instance
    2. Configures CORS middleware with settings from the configuration
    3. Initializes required service providers:
       - GeminiProvider for AI capabilities
       - FlareProvider for blockchain interactions
       - Vtpm for attestation services
       - PromptService for managing chat prompts
    4. Sets up routing for chat endpoints

    Returns:
        FastAPI: Configured FastAPI application instance

    Configuration:
        The following settings are used from settings module:
        - api_version: API version string
        - cors_origins: List of allowed CORS origins
        - gemini_api_key: API key for Gemini AI service
        - gemini_model: Model identifier for Gemini AI
        - web3_provider_url: URL for Web3 provider
        - simulate_attestation: Boolean flag for attestation simulation
    """
    app = FastAPI(
        title="AI Agent API", version=settings.api_version, redirect_slashes=False
    )

    # Configure CORS middleware with settings from configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize prompt service
    prompts = PromptService()
    
    # Validate required prompts
    validate_required_prompts(prompts)
    
    # Initialize router with service providers
    chat = ChatRouter(
        ai=GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model),
        blockchain=FlareProvider(web3_provider_url=settings.web3_provider_url),
        attestation=Vtpm(simulate=settings.simulate_attestation),
        prompts=prompts,
    )

    # Register chat routes with API
    app.include_router(chat.router, prefix="/api/routes/chat", tags=["chat"])
    return app


app = create_app()


def start() -> None:
    """
    Start the FastAPI application server using uvicorn.

    This function initializes and runs the uvicorn server with the configuration:
    - Host: 0.0.0.0 (accessible from all network interfaces)
    - Port: 8000 (default HTTP port for the application)
    - App: The FastAPI application instance

    Note:
        This function is typically called when running the application directly,
        not when importing as a module.
    """
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)  # noqa: S104


if __name__ == "__main__":
    start()
