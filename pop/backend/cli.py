"""Command-line interface for platform management and credential generation."""

import argparse
import logging
import sys
from typing import Optional
import uuid

from sqlalchemy import select
from app.core.database import SyncSessionLocal
from app.core.security import generate_raw_device_key, get_password_hash, hash_device_key
from app.models.camera import Camera
from app.models.centre import Centre
from app.models.device_key import DeviceKey
from app.models.user import User, UserRole

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("pop.cli")


def create_user_cmd(email: str, password: str, role_str: str) -> None:
    """Create a new platform user."""
    try:
        role = UserRole(role_str.lower())
    except ValueError:
        logger.error(f"Invalid role '{role_str}'. Allowed values: {[r.value for r in UserRole]}")
        sys.exit(1)

    with SyncSessionLocal() as session:
        clean_email = email.strip().lower()
        existing = session.execute(select(User).where(User.email == clean_email)).scalar_one_or_none()
        if existing:
            logger.error(f"User with email '{clean_email}' already exists.")
            sys.exit(1)

        user = User(
            email=clean_email,
            hashed_password=get_password_hash(password),
            role=role,
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        print("\n========================================================")
        print(" USER CREATED SUCCESSFULLY")
        print("========================================================")
        print(f" User ID : {user.id}")
        print(f" Email   : {user.email}")
        print(f" Role    : {user.role.value}")
        print("========================================================\n")


def create_device_key_cmd(name: str, centre_code: Optional[str] = None, camera_id_str: Optional[str] = None) -> None:
    """Provision a new edge device key and print the raw secret only once."""
    with SyncSessionLocal() as session:
        centre_id = None
        if centre_code:
            centre = session.execute(select(Centre).where(Centre.code == centre_code.strip())).scalar_one_or_none()
            if not centre:
                logger.error(f"Centre with code '{centre_code}' not found.")
                sys.exit(1)
            centre_id = centre.id

        camera_id = None
        if camera_id_str:
            try:
                cam_uuid = uuid.UUID(camera_id_str.strip())
            except ValueError:
                logger.error(f"Invalid camera UUID '{camera_id_str}'.")
                sys.exit(1)
            camera = session.execute(select(Camera).where(Camera.id == cam_uuid)).scalar_one_or_none()
            if not camera:
                logger.error(f"Camera with ID '{cam_uuid}' not found.")
                sys.exit(1)
            camera_id = camera.id
            if not centre_id:
                centre_id = camera.centre_id

        raw_key = generate_raw_device_key()
        key_hash = hash_device_key(raw_key)

        device_key = DeviceKey(
            name=name.strip(),
            key_hash=key_hash,
            centre_id=centre_id,
            camera_id=camera_id,
            is_active=True,
        )
        session.add(device_key)
        session.commit()
        session.refresh(device_key)

        print("\n================================================================================")
        print(" EDGE DEVICE KEY PROVISIONED")
        print("================================================================================")
        print(f" Device Key ID : {device_key.id}")
        print(f" Label         : {device_key.name}")
        print(f" Centre ID     : {device_key.centre_id}")
        print(f" Camera ID     : {device_key.camera_id}")
        print("--------------------------------------------------------------------------------")
        print(f" PLAINTEXT KEY : {raw_key}")
        print("--------------------------------------------------------------------------------")
        print(" [WARNING] Store this key in your edge device config.yaml or environment.")
        print("           It will NEVER be displayed again and cannot be retrieved from the database.")
        print("================================================================================\n")


def main() -> None:
    """CLI argument parser entry point."""
    parser = argparse.ArgumentParser(description="POP (ProofOfPresence) CLI Management Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create-user
    user_parser = subparsers.add_parser("create-user", help="Create a platform user account")
    user_parser.add_argument("--email", required=True, help="User login email")
    user_parser.add_argument("--password", required=True, help="User password")
    user_parser.add_argument(
        "--role",
        default="viewer",
        choices=["admin", "inspector", "viewer"],
        help="Access role (default: viewer)",
    )

    # create-device-key
    key_parser = subparsers.add_parser("create-device-key", help="Provision an edge device key")
    key_parser.add_argument("--name", required=True, help="Label for this edge node")
    key_parser.add_argument("--centre-code", required=False, help="Associated Centre code (optional)")
    key_parser.add_argument("--camera-id", required=False, help="Associated Camera UUID (optional)")

    args = parser.parse_args()

    if args.command == "create-user":
        create_user_cmd(email=args.email, password=args.password, role_str=args.role)
    elif args.command == "create-device-key":
        create_device_key_cmd(name=args.name, centre_code=args.centre_code, camera_id_str=args.camera_id)


if __name__ == "__main__":
    main()
