"""Bootstrap the initial administrator account.

Usage:
    python -m app.scripts.create_admin --username admin --email admin@example.com --password <password>
"""
import argparse
import getpass

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import ROLE_ADMIN, User
from app.security import get_password_hash


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or promote the initial administrator account.")
    parser.add_argument("--username", default="admin", help="Administrator username (default: admin)")
    parser.add_argument("--email", default="admin@example.com", help="Administrator email")
    parser.add_argument("--password", default=None, help="Administrator password (prompted if omitted)")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    password = args.password or getpass.getpass("Enter password for admin: ")

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == args.username))
        if user is not None:
            user.hashed_password = get_password_hash(password)
            user.role = ROLE_ADMIN
            user.email = user.email or args.email
            user.is_active = True
            print(f"Updated existing user '{args.username}' to administrator.")
        else:
            user = User(
                username=args.username,
                email=args.email,
                full_name="Administrator",
                hashed_password=get_password_hash(password),
                role=ROLE_ADMIN,
                is_active=True,
            )
            db.add(user)
            print(f"Created administrator '{args.username}'.")
        db.commit()


if __name__ == "__main__":
    main()