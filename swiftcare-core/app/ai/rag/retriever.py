from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.visit_embedding import VisitEmbedding


async def retrieve(
    db: AsyncSession,
    patient_id: int,
    query_vector: list[float],
    limit: int = 3,
) -> list[VisitEmbedding]:
    stmt = (
        select(VisitEmbedding)
        .where(VisitEmbedding.patient_id == patient_id)
        .order_by(VisitEmbedding.embedding.cosine_distance(query_vector))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
