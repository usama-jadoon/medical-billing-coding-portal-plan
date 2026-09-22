from services.coding_engine.ai.base import LLMProvider, LLMRequest, LLMResponse, LLMCandidateCode
from services.coding_engine.ai.mock_llm import MockLLMProvider
from services.api.config import settings


def get_llm_provider() -> LLMProvider:
    return MockLLMProvider()
