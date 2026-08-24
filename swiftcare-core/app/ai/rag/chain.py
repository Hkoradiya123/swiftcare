from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag.embedder import embed, _get_client
from app.ai.rag.retriever import retrieve
from app.core.config import get_settings


async def query(db: AsyncSession, patient_id: int, question: str) -> dict:
    query_vector = await embed(question)
    chunks = await retrieve(db, patient_id, query_vector)

    if not chunks:
        return {"answer": "No visit records found for this patient.", "sources": []}

    context = "\n\n".join(
        f"[Visit Summary #{c.visit_summary_id}]\n{c.content}" for c in chunks
    )
    source_ids = list({c.visit_summary_id for c in chunks})

    system_prompt = (
        "You are a clinical assistant. Answer the provider's question using ONLY "
        "the visit summaries provided. Cite the visit summary ID for each fact you state. "
        "If the answer cannot be found in the summaries, say so."
    )
    user_message = f"Patient visit records:\n{context}\n\nQuestion: {question}"

    settings = get_settings()
    response = await _get_client().chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0,
    )

    return {
        "answer": response.choices[0].message.content,
        "sources": source_ids,
    }
