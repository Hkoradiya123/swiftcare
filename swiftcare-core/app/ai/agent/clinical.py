import json

from langchain_core.tools import tool

from app.models.user import User


def _access_denied() -> str:
    return "Access denied. You must be logged in to access patient records."


def make_clinical_tools(session_factory, current_user: User | None) -> list:
    """Clinical tools. Each tool opens its own session to avoid shared-session concurrency bugs."""

    async def _check_provider_access(db, current_user: User, patient_id: int) -> bool:
        from app.repositories.provider import ProviderRepository
        from app.repositories.appointment import AppointmentRepository
        provider = await ProviderRepository(db).get_by_user_id(current_user.id)
        if not provider:
            return False
        return await AppointmentRepository(db).has_appointment_with_patient(provider.id, patient_id)

    async def _resolve_patient_id(db, requested_id: int | None) -> int | None:
        if current_user is None:
            return None
        if current_user.role == "patient":
            from app.repositories.patient import PatientRepository
            patient = await PatientRepository(db).get_by_user_id(current_user.id)
            return patient.id if patient else None
        if current_user.role == "provider":
            if requested_id is None:
                return None
            allowed = await _check_provider_access(db, current_user, requested_id)
            return requested_id if allowed else None
        # admin
        return requested_id

    @tool
    async def get_my_patients() -> str:
        """
        List all patients the current provider has seen or scheduled.
        Returns patient id, name, date of birth. Requires provider login.
        """
        if current_user is None:
            return _access_denied()
        if current_user.role == "patient":
            return "Patients cannot list other patients."

        from sqlalchemy import select, distinct
        from app.models.appointment import Appointment
        from app.models.patient import Patient
        from sqlalchemy.orm import selectinload

        async with session_factory() as db:
            if current_user.role == "admin":
                stmt = (
                    select(Patient)
                    .where(Patient.deleted_at.is_(None))
                    .options(selectinload(Patient.user))
                    .limit(50)
                )
            else:
                from app.repositories.provider import ProviderRepository
                provider = await ProviderRepository(db).get_by_user_id(current_user.id)
                if not provider:
                    return "Provider profile not found."
                subq = select(distinct(Appointment.patient_id)).where(
                    Appointment.provider_id == provider.id,
                    Appointment.deleted_at.is_(None),
                )
                stmt = (
                    select(Patient)
                    .where(Patient.id.in_(subq), Patient.deleted_at.is_(None))
                    .options(selectinload(Patient.user))
                )

            result = await db.execute(stmt)
            patients = result.scalars().all()
            if not patients:
                return "No patients found."
            return json.dumps([
                {"patient_id": p.id, "name": p.user.full_name, "dob": str(p.date_of_birth)}
                for p in patients
            ])

    @tool
    async def get_patient_appointments(patient_id: int) -> str:
        """Get appointments for a patient — includes appointment_id, status, date, and reason. Requires login."""
        if current_user is None:
            return _access_denied()

        async with session_factory() as db:
            allowed_id = await _resolve_patient_id(db, patient_id)
            if allowed_id is None:
                return "Access denied."

            from sqlalchemy import select
            from app.models.appointment import Appointment
            result = await db.execute(
                select(Appointment)
                .where(Appointment.patient_id == allowed_id, Appointment.deleted_at.is_(None))
                .order_by(Appointment.scheduled_start.desc())
                .limit(10)
            )
            appointments = result.scalars().all()
            if not appointments:
                return "No appointments found for this patient."
            return json.dumps([
                {
                    "appointment_id": a.id,
                    "status": a.status,
                    "date": str(a.scheduled_start),
                    "reason": a.reason,
                }
                for a in appointments
            ])

    @tool
    async def confirm_prescription_details(
        patient_id: int,
        appointment_id: int,
        drug_name: str,
        dosage_amount: float,
        dosage_unit: str,
        frequency_per_day: int,
        duration_days: int,
        instructions: str = "",
        notes: str = "",
    ) -> str:
        """
        Show prescription details to the user and ask for confirmation BEFORE creating it.
        Always call this first. Only call create_prescription after the user explicitly confirms.
        """
        lines = [
            "Please confirm the following prescription details:",
            f"  Patient ID   : {patient_id}",
            f"  Appointment  : {appointment_id}",
            f"  Drug         : {drug_name}",
            f"  Dose         : {dosage_amount} {dosage_unit}",
            f"  Frequency    : {frequency_per_day}x per day",
            f"  Duration     : {duration_days} days",
        ]
        if instructions:
            lines.append(f"  Instructions : {instructions}")
        if notes:
            lines.append(f"  Notes        : {notes}")
        lines.append("\nReply **yes** to confirm and create, or **no** to cancel.")
        return "\n".join(lines)

    @tool
    async def create_prescription(
        patient_id: int,
        appointment_id: int,
        drug_name: str,
        dosage_amount: float,
        dosage_unit: str,
        frequency_per_day: int,
        duration_days: int,
        instructions: str = "",
        notes: str = "",
    ) -> str:
        """
        Create a prescription for a patient. Provider only.
        IMPORTANT: Always call confirm_prescription_details first and wait for user confirmation.
        Only call this tool after the user has explicitly replied 'yes' or 'confirm'.
        dosage_unit examples: mg, ml, tablet. frequency_per_day: times per day. duration_days: how many days.
        Checks for drug allergies automatically. Appointment must be in 'completed' status.
        """
        if current_user is None or current_user.role not in ("provider", "admin"):
            return "Only providers can create prescriptions."

        async with session_factory() as db:
            allowed_id = await _resolve_patient_id(db, patient_id)
            if allowed_id is None:
                return "Access denied. You do not have a relationship with this patient."

            from app.repositories.provider import ProviderRepository
            from app.schemas.prescription import PrescriptionCreate, PrescriptionItemCreate
            from app.services.prescription import PrescriptionService

            provider = await ProviderRepository(db).get_by_user_id(current_user.id)
            if not provider:
                return "Provider profile not found."

            data = PrescriptionCreate(
                appointment_id=appointment_id,
                patient_id=allowed_id,
                notes=notes or None,
                items=[PrescriptionItemCreate(
                    drug_name=drug_name,
                    dosage_amount=dosage_amount,
                    dosage_unit=dosage_unit,
                    frequency_per_day=frequency_per_day,
                    duration_days=duration_days,
                    instructions=instructions or None,
                )],
            )
            try:
                rx = await PrescriptionService(db).create(provider.id, data)
                return json.dumps({"prescription_id": rx.id, "status": "created", "drug": drug_name})
            except Exception as e:
                detail = getattr(e, "detail", str(e))
                return f"Failed to create prescription: {detail}"

    @tool
    async def query_patient_history(patient_id: int, question: str) -> str:
        """
        Answer a clinical question about a patient's visit history using their medical records.
        Requires login. Providers can only access their own patients.
        """
        if current_user is None:
            return _access_denied()

        async with session_factory() as db:
            allowed_id = await _resolve_patient_id(db, patient_id)
            if allowed_id is None:
                return "Access denied. You do not have a relationship with this patient."

            from app.ai.rag.chain import query as rag_query
            result = await rag_query(db, allowed_id, question)
        return result["answer"]

    @tool
    async def get_patient_prescriptions(patient_id: int) -> str:
        """Get active prescriptions for a patient. Requires login."""
        if current_user is None:
            return _access_denied()

        async with session_factory() as db:
            allowed_id = await _resolve_patient_id(db, patient_id)
            if allowed_id is None:
                return "Access denied."

            from app.repositories.prescription import PrescriptionRepository
            prescriptions = await PrescriptionRepository(db).list_for_patient(allowed_id)
            if not prescriptions:
                return "No prescriptions found for this patient."
            out = []
            for rx in prescriptions:
                for item in rx.items:
                    out.append(
                        f"- [{rx.status}] {item.drug_name} {item.dosage_amount}{item.dosage_unit} "
                        f"{item.frequency_per_day}x/day for {item.duration_days} days"
                        + (f" ({item.instructions})" if item.instructions else "")
                    )
            return "\n".join(out)

    @tool
    async def get_patient_allergies(patient_id: int) -> str:
        """Get recorded allergies for a patient. Requires login."""
        if current_user is None:
            return _access_denied()

        async with session_factory() as db:
            allowed_id = await _resolve_patient_id(db, patient_id)
            if allowed_id is None:
                return "Access denied."

            from app.repositories.prescription import AllergyRepository
            allergies = await AllergyRepository(db).get_for_patient(allowed_id)
            if not allergies:
                return "No allergies recorded for this patient."
            return json.dumps([
                {"allergen": a.allergen_normalized, "type": a.allergy_type, "reaction": a.reaction}
                for a in allergies
            ])

    return [
        get_my_patients,
        get_patient_appointments,
        get_patient_prescriptions,
        get_patient_allergies,
        confirm_prescription_details,
        create_prescription,
        query_patient_history,
    ]
