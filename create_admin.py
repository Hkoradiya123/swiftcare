import argparse
import asyncio
import getpass
import sys
from pathlib import Path

# Add swiftcare-core to sys.path
ROOT_DIR = Path(__file__).resolve().parent
CORE_DIR = ROOT_DIR / "swiftcare-core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

# Ensure .env in ROOT_DIR is loaded
from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

from sqlalchemy import select
from app.db.engine import AsyncSessionLocal
from app.models.enums import UserRole
from app.models.user import User
from app.core.security import hash_password


async def create_or_promote_admin(email: str, full_name: str, password: str | None = None) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email.strip().lower()))
        user = result.scalar_one_or_none()

        if user:
            print(f"\nUser '{email}' already exists (Current Role: {user.role}).")
            if user.role == UserRole.ADMIN.value:
                print("User is already an Admin.")
            else:
                user.role = UserRole.ADMIN.value
                user.is_active = True
                if full_name:
                    user.full_name = full_name
                if password:
                    user.hashed_password = hash_password(password)
                await db.commit()
                print(f"SUCCESS: Promoted existing user '{email}' to role 'admin'!")
        else:
            if not password:
                print("ERROR: Password is required for new user creation.")
                return

            user = User(
                email=email.strip().lower(),
                hashed_password=hash_password(password),
                full_name=full_name.strip(),
                role=UserRole.ADMIN.value,
                is_active=True,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            print(f"\nSUCCESS: Created new Admin user (ID: {user.id})!")

        print("=" * 50)
        print("Admin User Details:")
        print(f"  ID       : {user.id}")
        print(f"  Email    : {user.email}")
        print(f"  Name     : {user.full_name}")
        print(f"  Role     : {user.role}")
        print(f"  Active   : {user.is_active}")
        print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="Create or promote a user to Admin in SwiftCare")
    parser.add_argument("--email", "-e", help="Admin email address")
    parser.add_argument("--name", "-n", help="Admin full name")
    parser.add_argument("--password", "-p", help="Admin password")
    args = parser.parse_args()

    email = args.email or input("Enter Admin Email: ").strip()
    if not email:
        print("Email cannot be empty!")
        sys.exit(1)

    name = args.name or input("Enter Admin Full Name: ").strip()
    if not name:
        name = "System Admin"

    password = args.password
    if not password:
        password = getpass.getpass("Enter Admin Password (press Enter to keep existing if user exists): ").strip()

    asyncio.run(create_or_promote_admin(email, name, password if password else None))


if __name__ == "__main__":
    main()
