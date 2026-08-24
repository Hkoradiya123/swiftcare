"""
One-shot backfill: creates VisitSummary + embedding for completed appointments
that have no summary yet. Uses appointment reason + notes as the summary text.
Run from swiftcare-core/:  python backfill_embeddings.py
"""
import asyncio
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

import app.models  # registers all models on Base.metadata
from app.db.engine import AsyncSessionLocal
from app.models.appointment import Appointment
from app.models.visit_summary import VisitSummary
from app.models.visit_embedding import VisitEmbedding
from app.models.prescription import Prescription
from app.ai.rag.embedder import embed


async def backfill():
    async with AsyncSessionLocal() as db:
        # completed appointments with no visit summary
        stmt = (
            select(Appointment)
            .where(
                Appointment.status == "completed",
                Appointment.deleted_at.is_(None),
                ~Appointment.id.in_(select(VisitSummary.appointment_id)),
            )
        )
        result = await db.execute(stmt)
        appointments = result.scalars().all()

        print(f"Found {len(appointments)} completed appointments with no summary.")

        for appt in appointments:
            # build summary from reason + notes
            summary_text = appt.reason
            if appt.notes:
                summary_text += f"\n\nNotes: {appt.notes}"

            # create visit summary
            vs = VisitSummary(
                appointment_id=appt.id,
                patient_id=appt.patient_id,
                summary=summary_text,
            )
            db.add(vs)
            await db.flush()

            # fetch prescriptions
            rx_result = await db.execute(
                select(Prescription)
                .where(
                    Prescription.appointment_id == appt.id,
                    Prescription.deleted_at.is_(None),
                )
                .options(selectinload(Prescription.items))
            )
            prescriptions = rx_result.scalars().all()

            content = summary_text
            if prescriptions:
                lines = ["\n\nPrescriptions issued:"]
                for rx in prescriptions:
                    for item in rx.items:
                        lines.append(
                            f"- {item.drug_name} {item.dosage_amount}{item.dosage_unit} "
                            f"{item.frequency_per_day}x/day for {item.duration_days} days"
                            + (f" — {item.instructions}" if item.instructions else "")
                        )
                content += "\n".join(lines)

            print(f"  Embedding appt_id={appt.id} patient_id={appt.patient_id} "
                  f"({len(prescriptions)} prescriptions)...", end=" ", flush=True)

            vector = await embed(content)
            db.add(VisitEmbedding(
                patient_id=appt.patient_id,
                visit_summary_id=vs.id,
                content=content,
                embedding=vector,
            ))
            print("done")

        await db.commit()
        print(f"\nBackfill complete. {len(appointments)} summaries + embeddings created.")


if __name__ == "__main__":
    asyncio.run(backfill())
