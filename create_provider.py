import argparse
import asyncio
from datetime import time
from decimal import Decimal
import getpass
import sys
from pathlib import Path

# Add swiftcare-core to sys.path
ROOT_DIR = Path(__file__).resolve().parent
CORE_DIR = ROOT_DIR / "swiftcare-core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.db.engine import AsyncSessionLocal
from app.models.enums import UserRole
from app.models.user import User
from app.models.provider import Provider, ProviderAvailability
from app.core.security import hash_password


async def create_or_promote_provider(
    email: str,
    full_name: str,
    password: str | None,
    specialization: str,
    license_number: str,
    consultation_fee: Decimal,
    default_slot_minutes: int,
    add_default_slots: bool = True,
) -> None:
    async with AsyncSessionLocal() as db:
        # 1. Check or Create User
        result = await db.execute(select(User).where(User.email == email.strip().lower()))
        user = result.scalar_one_or_none()

        if user:
            print(f"\nUser '{email}' exists (Current Role: {user.role}).")
            user.role = UserRole.PROVIDER.value
            user.is_active = True
            if full_name:
                user.full_name = full_name
            if password:
                user.hashed_password = hash_password(password)
            await db.commit()
            await db.refresh(user)
            print(f"Set user role to '{user.role}'.")
        else:
            if not password:
                print("ERROR: Password is required for new user creation.")
                return

            user = User(
                email=email.strip().lower(),
                hashed_password=hash_password(password),
                full_name=full_name.strip(),
                role=UserRole.PROVIDER.value,
                is_active=True,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            print(f"\nCreated new Provider User (User ID: {user.id}).")

        # 2. Check or Create Provider Profile
        result = await db.execute(
            select(Provider)
            .options(selectinload(Provider.availability))
            .where(Provider.user_id == user.id)
        )
        provider = result.scalar_one_or_none()

        if provider:
            print(f"Provider profile already exists (Provider ID: {provider.id}). Updating profile...")
            if specialization:
                provider.specialization = specialization
            if license_number:
                provider.license_number = license_number
            if consultation_fee:
                provider.consultation_fee = consultation_fee
            if default_slot_minutes:
                provider.default_slot_minutes = default_slot_minutes
            await db.commit()
            await db.refresh(provider)
        else:
            provider = Provider(
                user_id=user.id,
                specialization=specialization,
                license_number=license_number,
                consultation_fee=consultation_fee,
                default_slot_minutes=default_slot_minutes,
            )
            db.add(provider)
            await db.commit()
            await db.refresh(provider)
            print(f"Created Provider Clinical Profile (Provider ID: {provider.id}).")

        # 3. Default Availability Slots (Mon-Fri 09:00 - 17:00)
        if add_default_slots:
            res = await db.execute(
                select(ProviderAvailability).where(ProviderAvailability.provider_id == provider.id)
            )
            existing_slots = res.scalars().all()
            if not existing_slots:
                print("Adding default availability schedule (Monday - Friday, 09:00 - 17:00)...")
                for weekday in range(5):  # 0=Monday to 4=Friday
                    slot = ProviderAvailability(
                        provider_id=provider.id,
                        weekday=weekday,
                        start_time=time(9, 0),
                        end_time=time(17, 0),
                    )
                    db.add(slot)
                await db.commit()
                print("Default availability slots added successfully.")
            else:
                print(f"Provider already has {len(existing_slots)} availability slots configured.")

        # Summary
        print("\n" + "=" * 55)
        print("Provider Details Summary:")
        print(f"  Provider ID     : {provider.id}")
        print(f"  User ID         : {user.id}")
        print(f"  Email           : {user.email}")
        print(f"  Doctor Name     : {user.full_name}")
        print(f"  Role            : {user.role}")
        print(f"  Specialization  : {provider.specialization}")
        print(f"  License Number  : {provider.license_number}")
        print(f"  Consultation Fee: Rs. {provider.consultation_fee}")
        print(f"  Slot Duration   : {provider.default_slot_minutes} mins")
        print("=" * 55)


def main():
    parser = argparse.ArgumentParser(description="Create or promote a Provider (Doctor) in SwiftCare")
    parser.add_argument("--email", "-e", help="Doctor email address")
    parser.add_argument("--name", "-n", help="Doctor full name (e.g., Dr. Anjali Mehta)")
    parser.add_argument("--password", "-p", help="Doctor password")
    parser.add_argument("--specialization", "-s", default="General Medicine", help="Medical Specialization")
    parser.add_argument("--license", "-l", default="MED-REG-001", help="Medical License Number")
    parser.add_argument("--fee", "-f", type=float, default=500.0, help="Consultation Fee")
    parser.add_argument("--slot-minutes", "-m", type=int, default=30, choices=[15, 20, 30, 45, 60], help="Default slot minutes")
    parser.add_argument("--no-slots", action="store_true", help="Do not add default Mon-Fri availability slots")
    args = parser.parse_args()

    email = args.email or input("Enter Doctor Email: ").strip()
    if not email:
        print("Email cannot be empty!")
        sys.exit(1)

    name = args.name or input("Enter Doctor Full Name (e.g. Dr. Ramesh Kumar): ").strip()
    if not name:
        name = "Dr. Medical Provider"

    password = args.password
    if not password:
        password = getpass.getpass("Enter Password (press Enter to keep existing if user exists): ").strip()

    specialization = args.specialization
    if not args.email and not args.specialization:
        spec_in = input(f"Enter Specialization [{specialization}]: ").strip()
        if spec_in:
            specialization = spec_in

    license_no = args.license
    if not args.email and not args.license:
        lic_in = input(f"Enter License Number [{license_no}]: ").strip()
        if lic_in:
            license_no = lic_in

    fee = Decimal(str(args.fee))
    slot_minutes = args.slot_minutes

    asyncio.run(create_or_promote_provider(
        email=email,
        full_name=name,
        password=password if password else None,
        specialization=specialization,
        license_number=license_no,
        consultation_fee=fee,
        default_slot_minutes=slot_minutes,
        add_default_slots=not args.no_slots,
    ))


if __name__ == "__main__":
    main()
