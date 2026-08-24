from openai import AsyncOpenAI
from app.core.config import get_settings

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=get_settings().openai_api_key)
    return _client


async def embed(text: str) -> list[float]:
    response = await _get_client().embeddings.create(
        model=get_settings().openai_embedding_model,
        input=text,
    )
    return response.data[0].embedding
