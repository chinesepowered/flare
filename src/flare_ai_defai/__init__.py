from flare_ai_defai.ai import GeminiProvider
from flare_ai_defai.api import ChatRouter, router
from flare_ai_defai.attestation import Vtpm
from flare_ai_defai.blockchain import FlareProvider
# Temporarily disabled SparkDEX in favor of BlazeSwap
# from flare_ai_defai.sparkdex import SparkDEXProvider
from flare_ai_defai.blockchain.blazedex import BlazeDEXProvider
from flare_ai_defai.prompts import (
    PromptService,
    SemanticRouterResponse,
)
from .qdrant_client import initialize_qdrant_client

__all__ = [
    "ChatRouter",
    "FlareProvider",
    "BlazeDEXProvider",
    "GeminiProvider",
    "PromptService",
    "SemanticRouterResponse",
    "Vtpm",
    "router",
    "initialize_qdrant_client",
]
