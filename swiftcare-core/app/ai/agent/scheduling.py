import json
from datetime import datetime

from langchain_core.tools import tool

from app.models.user import User


def make_scheduling_tools(session_factory, current_user: User | None) -> list:
    """Scheduling tools. Each tool opens its own session to avoid shared-session concurrency bugs."""

    @tool
    async def find_providers_by_specialization(specialization: str) -> str:
        """Find providers by medical specialization. Returns id, name, fee, slot duration."""
        from app.repositories.provider import ProviderRepository
        async with session_factory() as db:
            providers = await ProviderRepository(db).get_by_specialization(specialization, 1, 10)
            if not providers:
                return f"No providers found for: {specialization}"
            return json.dumps([
                {
                    "provider_id": p.id,
                    "name": p.user.full_name,
                    "specialization": p.specialization,
                    "consultation_fee": float(p.consultation_fee),
                    "default_slot_minutes": p.default_slot_minutes,
                }
                for p in providers
            ])

    @tool
    async def get_provider_availability(provider_id: int) -> str:
        """Get a provider's weekly availability schedule."""
        from app.repositories.provider import ProviderRepository
        async with session_factory() as db:
            slots = await ProviderRepository(db).get_all_availabilities(provider_id)
        if not slots:
            return f"Provider {provider_id} has no availability configured."
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        return json.dumps([
            {"weekday": days[s.weekday], "start_time": str(s.start_time), "end_time": str(s.end_time)}
            for s in slots
        ])

    @tool
    async def check_slot_availability(provider_id: int, start_datetime: str, end_datetime: str) -> str:
        """
        Check if a time slot is free for a provider.
        Datetimes must be ISO 8601 (e.g. '2025-09-01T10:00:00+00:00').
        Returns 'available' or 'booked'.
        """
        from app.repositories.appointment import AppointmentRepository
        start = datetime.fromisoformat(start_datetime)
        end = datetime.fromisoformat(end_datetime)
        async with session_factory() as db:
            has_overlap = await AppointmentRepository(db).has_overlap(provider_id, start, end)
        return "booked" if has_overlap else "available"

    @tool
    async def confirm_appointment_details(
        provider_id: int,
        patient_id: int,
        start_datetime: str,
        end_datetime: str,
        appointment_type: str,
        reason: str,
    ) -> str:
        """
        Show appointment details to the user and ask for confirmation BEFORE booking.
        Always call this first. Only call book_appointment after the user explicitly confirms.
        """
        return (
            f"Please confirm the following appointment details:\n"
            f"  Provider ID  : {provider_id}\n"
            f"  Patient ID   : {patient_id}\n"
            f"  Type         : {appointment_type}\n"
            f"  Start        : {start_datetime}\n"
            f"  End          : {end_datetime}\n"
            f"  Reason       : {reason}\n\n"
            f"Reply **yes** to confirm and book, or **no** to cancel."
        )

    @tool
    async def book_appointment(
        provider_id: int,
        patient_id: int,
        start_datetime: str,
        end_datetime: str,
        appointment_type: str,
        reason: str,
    ) -> str:
        """
        Book an appointment. appointment_type: 'in_person' or 'telehealth'.
        Requires login. Patients can only book for themselves.
        IMPORTANT: Always call confirm_appointment_details first and wait for user confirmation.
        Only call this tool after the user has explicitly replied yes or confirm.
        """
        if current_user is None:
            return "You must be logged in to book an appointment."

        from app.schemas.appointment import AppointmentCreate
        from app.services.appointment import AppointmentService
        from app.models.enums import AppointmentType

        async with session_factory() as db:
            if current_user.role == "patient":
                from app.repositories.patient import PatientRepository
                patient = await PatientRepository(db).get_by_user_id(current_user.id)
                if not patient or patient.id != patient_id:
                    return "Patients can only book appointments for themselves."

            appt_type = AppointmentType.IN_PERSON if appointment_type == "in_person" else AppointmentType.TELEHEALTH
            data = AppointmentCreate(
                patient_id=patient_id,
                provider_id=provider_id,
                appointment_type=appt_type,
                scheduled_start=datetime.fromisoformat(start_datetime),
                scheduled_end=datetime.fromisoformat(end_datetime),
                reason=reason,
            )
            try:
                appt = await AppointmentService(db).create(data)
                return json.dumps({"appointment_id": appt.id, "status": "scheduled"})
            except Exception as e:
                detail = getattr(e, "detail", str(e))
                return f"Failed to book appointment: {detail}"

    @tool
    async def list_all_providers(page: int = 1) -> str:
        """
        List available providers with name, specialization, and consultation fee.
        Returns 20 per page. Check 'total' and 'page'/'total_pages' to decide if more pages exist.
        """
        import logging
        _log = logging.getLogger(__name__)
        from app.repositories.provider import ProviderRepository
        page_size = 20
        try:
            async with session_factory() as db:
                repo = ProviderRepository(db)
                total = await repo.count()
                providers = await repo.list_all(page, page_size)
        except Exception as exc:
            _log.exception("list_all_providers failed page=%s", page)
            return f"Failed to retrieve providers: {exc}"
        if not providers:
            return "No providers found."
        return json.dumps({
            "page": page,
            "total_pages": -(-total // page_size),
            "total": total,
            "providers": [
                {
                    "provider_id": p.id,
                    "name": p.user.full_name,
                    "specialization": p.specialization,
                    "consultation_fee": float(p.consultation_fee),
                }
                for p in providers
            ],
        })

    return [list_all_providers, find_providers_by_specialization, get_provider_availability, check_slot_availability, confirm_appointment_details, book_appointment]
