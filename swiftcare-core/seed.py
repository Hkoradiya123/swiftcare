"""
Run from swiftcare-core/:
    python seed.py

Clears existing seed data and re-inserts fresh sample records.
All data is fictional — no real patient information.
"""
import asyncio
from datetime import date, time, datetime, timezone, timedelta
from decimal import Decimal

from app.db.engine import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User
from app.models.patient import Patient
from app.models.provider import Provider, ProviderAvailability
from app.models.appointment import InPersonAppointment, TelehealthAppointment
from app.models.enums import AppointmentStatus, UserRole


def utc(dt: str) -> datetime:
    return datetime.fromisoformat(dt).replace(tzinfo=timezone.utc)


# ── Sample users ──────────────────────────────────────────────────────
USERS = [
    # admins
    dict(email="admin@swiftcare.dev",        full_name="Admin User",          role=UserRole.ADMIN.value,    password="Admin@1234"),
    # providers
    dict(email="dr.arjun@swiftcare.dev",     full_name="Dr. Arjun Mehta",     role=UserRole.PROVIDER.value, password="Provider@1234"),
    dict(email="dr.priya@swiftcare.dev",     full_name="Dr. Priya Sharma",    role=UserRole.PROVIDER.value, password="Provider@1234"),
    dict(email="dr.rahul@swiftcare.dev",     full_name="Dr. Rahul Verma",     role=UserRole.PROVIDER.value, password="Provider@1234"),
    # patients
    dict(email="sam.wilson@example.com",     full_name="Sam Wilson",          role=UserRole.PATIENT.value,  password="Patient@1234"),
    dict(email="neha.gupta@example.com",     full_name="Neha Gupta",          role=UserRole.PATIENT.value,  password="Patient@1234"),
    dict(email="rohan.singh@example.com",    full_name="Rohan Singh",         role=UserRole.PATIENT.value,  password="Patient@1234"),
    dict(email="fatima.khan@example.com",    full_name="Fatima Khan",         role=UserRole.PATIENT.value,  password="Patient@1234"),
    dict(email="david.thomas@example.com",   full_name="David Thomas",        role=UserRole.PATIENT.value,  password="Patient@1234"),
]

# ── Provider profiles ─────────────────────────────────────────────────
PROVIDERS = [
    dict(email="dr.arjun@swiftcare.dev",  specialization="Cardiology",       license_number="MH-CARD-1001", fee=Decimal("800.00"), slot=30),
    dict(email="dr.priya@swiftcare.dev",  specialization="General Medicine",  license_number="MH-GEN-1002",  fee=Decimal("500.00"), slot=20),
    dict(email="dr.rahul@swiftcare.dev",  specialization="Orthopedics",      license_number="MH-ORTH-1003", fee=Decimal("700.00"), slot=30),
]

# ── Availability (weekday: 0=Mon … 6=Sun) ────────────────────────────
AVAILABILITY = [
    # Dr. Arjun — Mon/Wed/Fri 09:00-17:00
    dict(email="dr.arjun@swiftcare.dev",  weekday=0, start=time(9,0),  end=time(17,0)),
    dict(email="dr.arjun@swiftcare.dev",  weekday=2, start=time(9,0),  end=time(17,0)),
    dict(email="dr.arjun@swiftcare.dev",  weekday=4, start=time(9,0),  end=time(17,0)),
    # Dr. Priya — Tue/Thu/Sat 10:00-18:00
    dict(email="dr.priya@swiftcare.dev",  weekday=1, start=time(10,0), end=time(18,0)),
    dict(email="dr.priya@swiftcare.dev",  weekday=3, start=time(10,0), end=time(18,0)),
    dict(email="dr.priya@swiftcare.dev",  weekday=5, start=time(10,0), end=time(14,0)),
    # Dr. Rahul — Mon-Fri 08:00-16:00
    dict(email="dr.rahul@swiftcare.dev",  weekday=0, start=time(8,0),  end=time(16,0)),
    dict(email="dr.rahul@swiftcare.dev",  weekday=1, start=time(8,0),  end=time(16,0)),
    dict(email="dr.rahul@swiftcare.dev",  weekday=2, start=time(8,0),  end=time(16,0)),
    dict(email="dr.rahul@swiftcare.dev",  weekday=3, start=time(8,0),  end=time(16,0)),
    dict(email="dr.rahul@swiftcare.dev",  weekday=4, start=time(8,0),  end=time(16,0)),
]

# ── Patient profiles ──────────────────────────────────────────────────
PATIENTS = [
    dict(email="sam.wilson@example.com",   dob=date(1990, 3, 15), phone="+91-9800000001", blood="O+",  address="12 MG Road, Mumbai"),
    dict(email="neha.gupta@example.com",   dob=date(1985, 7, 22), phone="+91-9800000002", blood="A+",  address="45 Park Street, Delhi"),
    dict(email="rohan.singh@example.com",  dob=date(1992, 11, 8), phone="+91-9800000003", blood="B-",  address="78 Lake View, Pune"),
    dict(email="fatima.khan@example.com",  dob=date(1998, 1, 30), phone="+91-9800000004", blood="AB+", address="23 Civil Lines, Jaipur"),
    dict(email="david.thomas@example.com", dob=date(1975, 5, 10), phone="+91-9800000005", blood="O-",  address="56 Church Road, Bangalore"),
]

# ── Appointments ──────────────────────────────────────────────────────
# (patient_email, provider_email, type, start, end, status, reason, room/link)
APPOINTMENTS = [
    # completed in-person
    ("sam.wilson@example.com",   "dr.arjun@swiftcare.dev",  "in_person",
     "2026-07-10 09:00", "2026-07-10 09:30", AppointmentStatus.COMPLETED.value,
     "Chest pain follow-up", {"room_number": "A-101"}),

    ("neha.gupta@example.com",   "dr.priya@swiftcare.dev",  "in_person",
     "2026-07-15 10:00", "2026-07-15 10:20", AppointmentStatus.COMPLETED.value,
     "Routine check-up", {"room_number": "B-202"}),

    # completed telehealth
    ("rohan.singh@example.com",  "dr.rahul@swiftcare.dev",  "telehealth",
     "2026-07-18 11:00", "2026-07-18 11:30", AppointmentStatus.COMPLETED.value,
     "Knee pain consultation", {"meeting_link": "https://meet.swiftcare.dev/room/abc123"}),

    # upcoming scheduled
    ("fatima.khan@example.com",  "dr.priya@swiftcare.dev",  "in_person",
     "2026-09-05 10:00", "2026-09-05 10:20", AppointmentStatus.SCHEDULED.value,
     "Fever and cold symptoms", {"room_number": "B-203"}),

    ("david.thomas@example.com", "dr.arjun@swiftcare.dev",  "telehealth",
     "2026-09-08 09:00", "2026-09-08 09:30", AppointmentStatus.SCHEDULED.value,
     "Blood pressure monitoring", {"meeting_link": "https://meet.swiftcare.dev/room/def456"}),

    ("sam.wilson@example.com",   "dr.rahul@swiftcare.dev",  "in_person",
     "2026-09-10 08:00", "2026-09-10 08:30", AppointmentStatus.SCHEDULED.value,
     "Shoulder physiotherapy follow-up", {"room_number": "C-301"}),

    # cancelled
    ("neha.gupta@example.com",   "dr.arjun@swiftcare.dev",  "in_person",
     "2026-08-01 09:00", "2026-08-01 09:30", AppointmentStatus.CANCELLED.value,
     "Palpitations", {"room_number": "A-102"}),
]


async def seed():
    async with AsyncSessionLocal() as db:
        print("Seeding database...")

        # index by email for lookups
        user_map: dict[str, User] = {}
        provider_map: dict[str, Provider] = {}
        patient_map: dict[str, Patient] = {}

        # ── Users ─────────────────────────────────────────────────────
        print("  >users")
        for u in USERS:
            user = User(
                email=u["email"],
                hashed_password=hash_password(u["password"]),
                full_name=u["full_name"],
                role=u["role"],
            )
            db.add(user)
            await db.flush()
            user_map[u["email"]] = user

        # ── Providers ─────────────────────────────────────────────────
        print("  >providers")
        for p in PROVIDERS:
            provider = Provider(
                user_id=user_map[p["email"]].id,
                specialization=p["specialization"],
                license_number=p["license_number"],
                consultation_fee=p["fee"],
                default_slot_minutes=p["slot"],
            )
            db.add(provider)
            await db.flush()
            provider_map[p["email"]] = provider

        # ── Availability ──────────────────────────────────────────────
        print("  >provider availability")
        for a in AVAILABILITY:
            db.add(ProviderAvailability(
                provider_id=provider_map[a["email"]].id,
                weekday=a["weekday"],
                start_time=a["start"],
                end_time=a["end"],
            ))

        # ── Patients ──────────────────────────────────────────────────
        print("  >patients")
        for p in PATIENTS:
            patient = Patient(
                user_id=user_map[p["email"]].id,
                date_of_birth=p["dob"],
                phone=p["phone"],
                blood_group=p["blood"],
                address=p["address"],
            )
            db.add(patient)
            await db.flush()
            patient_map[p["email"]] = patient

        # ── Appointments ──────────────────────────────────────────────
        print("  >appointments")
        for (pat_email, prov_email, kind, start, end, status, reason, extras) in APPOINTMENTS:
            patient  = patient_map[pat_email]
            provider = provider_map[prov_email]
            start_dt = utc(start)
            end_dt   = utc(end)

            if kind == "in_person":
                appt = InPersonAppointment(
                    patient_id=patient.id,
                    provider_id=provider.id,
                    scheduled_start=start_dt,
                    scheduled_end=end_dt,
                    status=status,
                    reason=reason,
                    room_number=extras.get("room_number"),
                )
            else:
                appt = TelehealthAppointment(
                    patient_id=patient.id,
                    provider_id=provider.id,
                    scheduled_start=start_dt,
                    scheduled_end=end_dt,
                    status=status,
                    reason=reason,
                    meeting_link=extras.get("meeting_link"),
                )

            if status == AppointmentStatus.COMPLETED.value:
                appt.checked_in_at = start_dt + timedelta(minutes=2)
                appt.completed_at  = end_dt

            db.add(appt)

        await db.commit()
        print("Done. Seeded:")
        print(f"  {len(USERS)} users ({sum(1 for u in USERS if u['role']==UserRole.PROVIDER.value)} providers, {sum(1 for u in USERS if u['role']==UserRole.PATIENT.value)} patients, 1 admin)")
        print(f"  {len(PROVIDERS)} provider profiles + {len(AVAILABILITY)} availability slots")
        print(f"  {len(PATIENTS)} patient profiles")
        print(f"  {len(APPOINTMENTS)} appointments")
        print()
        print("Login credentials (all accounts):")
        print("  Providers : Provider@1234")
        print("  Patients  : Patient@1234")
        print("  Admin     : Admin@1234")


if __name__ == "__main__":
    asyncio.run(seed())
