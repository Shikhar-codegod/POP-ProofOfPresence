"""Initial database schema for POP (ProofOfPresence)

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-27 12:00:00.000000 UTC

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("admin", "inspector", "viewer", name="user_role_enum"),
            nullable=False,
            server_default="viewer",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)

    # 2. Create centres table
    op.create_table(
        "centres",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=128), nullable=False),
        sa.Column("district", sa.String(length=128), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_centres_code"), "centres", ["code"], unique=True)
    op.create_index(op.f("ix_centres_state"), "centres", ["state"], unique=False)
    op.create_index(op.f("ix_centres_district"), "centres", ["district"], unique=False)

    # 3. Create cameras table
    op.create_table(
        "cameras",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("centre_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("centres.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("rtsp_url", sa.String(length=512), nullable=True),
        sa.Column("location_description", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_cameras_centre_id"), "cameras", ["centre_id"], unique=False)

    # 4. Create device_keys table
    op.create_table(
        "device_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("centre_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("centres.id", ondelete="SET NULL"), nullable=True),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_device_keys_key_hash"), "device_keys", ["key_hash"], unique=True)
    op.create_index(op.f("ix_device_keys_centre_id"), "device_keys", ["centre_id"], unique=False)
    op.create_index(op.f("ix_device_keys_camera_id"), "device_keys", ["camera_id"], unique=False)

    # 5. Create readings table
    op.create_table(
        "readings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("centre_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("centres.id", ondelete="CASCADE"), nullable=False),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_count", sa.Integer(), nullable=False),
        sa.Column("stable_count", sa.Integer(), nullable=False),
        sa.Column("equipment", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("frame_quality", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("camera_id", "timestamp", name="uq_readings_camera_timestamp"),
    )
    op.create_index(op.f("ix_readings_centre_id"), "readings", ["centre_id"], unique=False)
    op.create_index(op.f("ix_readings_camera_id"), "readings", ["camera_id"], unique=False)
    op.create_index(op.f("ix_readings_timestamp"), "readings", ["timestamp"], unique=False)
    op.create_index("ix_readings_centre_timestamp", "readings", ["centre_id", "timestamp"], unique=False)
    op.create_index("ix_readings_camera_timestamp", "readings", ["camera_id", "timestamp"], unique=False)

    # 6. Create sanctioned_inventory table
    op.create_table(
        "sanctioned_inventory",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("centre_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("centres.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_type", sa.String(length=128), nullable=False),
        sa.Column("sanctioned_quantity", sa.Integer(), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_sanctioned_inventory_centre_id"), "sanctioned_inventory", ["centre_id"], unique=False)
    op.create_index(op.f("ix_sanctioned_inventory_item_type"), "sanctioned_inventory", ["item_type"], unique=False)

    # 7. Create attendance_records table
    op.create_table(
        "attendance_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("centre_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("centres.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("enrolled_count", sa.Integer(), nullable=False),
        sa.Column("official_present_count", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("centre_id", "date", name="uq_attendance_centre_date"),
    )
    op.create_index(op.f("ix_attendance_records_centre_id"), "attendance_records", ["centre_id"], unique=False)
    op.create_index(op.f("ix_attendance_records_date"), "attendance_records", ["date"], unique=False)


def downgrade() -> None:
    op.drop_table("attendance_records")
    op.drop_table("sanctioned_inventory")
    op.drop_table("readings")
    op.drop_table("device_keys")
    op.drop_table("cameras")
    op.drop_table("centres")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS user_role_enum")
