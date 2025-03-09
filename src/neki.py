
from flare_ai_defai.settings import settings

from flare_ai_defai import (
    FlareProvider,
    BlazeDEXProvider,
)
from flare_ai_defai.settings import settings


    # Initialize BlazeDEX provider
bd = BlazeDEXProvider(w3=FlareProvider(web3_provider_url=settings.web3_provider_url).w3)
    
