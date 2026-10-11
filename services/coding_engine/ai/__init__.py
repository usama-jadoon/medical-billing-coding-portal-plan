from services.coding_engine.ai.base import LLMProvider, LLMRequest, LLMResponse, LLMCandidateCode
from services.coding_engine.ai.mock_llm import MockLLMProvider
from services.coding_engine.ai.gateway import (
    AIGatewayBroker,
    AIGatewayRequest,
    AIGatewayResponse,
    ClaimDto,
    get_ai_gateway_broker,
)
from services.api.config import settings


def get_llm_provider() -> LLMProvider:
    return MockLLMProvider()
