"""Database seeding script for POP (ProofOfPresence).

Provisions realistic vocational skilling centres across India with:
- Administrative & Inspector accounts
- 5 Centres across different states (with lat/lng coordinates)
- CCTV Cameras with generated edge device keys
- Sanctioned infrastructure inventory
- 14 days of historical attendance and CCTV reading telemetry
- 2 centres configured with deliberate, high-severity attendance mismatches (ghost attendance).
"""

from datetime import date, datetime, timedelta, timezone
import logging
import random
import sys
import uuid
from typing import Dict, List, Tuple

from sqlalchemy import delete, select
from app.core.database import SyncSessionLocal, sync_engine
from app.core.security import generate_raw_device_key, get_password_hash, hash_device_key
from app.models.attendance_record import AttendanceRecord
from app.models.camera import Camera
from app.models.centre import Centre
from app.models.device_key import DeviceKey
from app.models.reading import Reading
from app.models.sanctioned_inventory import SanctionedInventory
from app.models.user import User, UserRole

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pop.seed")


def seed_database() -> None:
    """Execute complete database seeding."""
    logger.info("Beginning database seed...")

    with SyncSessionLocal() as session:
        # 1. Clean existing records (in reverse foreign-key order)
        logger.info("Purging existing records...")
        session.execute(delete(Reading))
        session.execute(delete(DeviceKey))
        session.execute(delete(SanctionedInventory))
        session.execute(delete(AttendanceRecord))
        session.execute(delete(Camera))
        session.execute(delete(Centre))
        session.execute(delete(User))
        session.commit()

        # 2. Seed Users
        logger.info("Seeding administrative & inspector users...")
        admin_user = User(
            id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
            email="admin@pop.gov.in",
            hashed_password=get_password_hash("AdminSecret123!"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        inspector_user = User(
            id=uuid.UUID("22222222-2222-4222-8222-222222222222"),
            email="inspector.verma@gov.in",
            hashed_password=get_password_hash("InspectorSecret123!"),
            role=UserRole.INSPECTOR,
            is_active=True,
        )
        viewer_user = User(
            id=uuid.UUID("33333333-3333-4333-8333-333333333333"),
            email="viewer.sharma@gov.in",
            hashed_password=get_password_hash("ViewerSecret123!"),
            role=UserRole.VIEWER,
            is_active=True,
        )
        session.add_all([admin_user, inspector_user, viewer_user])
        session.commit()

        # 3. Seed Centres metadata
        centres_data = [
            {
                "id": uuid.UUID("a1000000-0000-4000-8000-000000000001"),
                "name": "PMKK Gurugram - Technology & Green Skills Hub",
                "code": "HR-GGN-0104",
                "state": "Haryana",
                "district": "Gurugram",
                "latitude": 28.4595,
                "longitude": 77.0266,
                "has_mismatch": False,
                "enrolled": 30,
                "cameras": [
                    {"name": "Lab 1 - IT & Networking", "rtsp": "rtsp://cctv-ggn.internal/live/ch1", "loc": "Room 101, Ground Floor"},
                    {"name": "Classroom 2 - Solar Tech", "rtsp": "rtsp://cctv-ggn.internal/live/ch2", "loc": "Room 204, Second Floor"},
                ],
                "inventory": [
                    ("desktop_computer", 30),
                    ("networking_rack", 5),
                    ("solar_panel_trainer_kit", 8),
                    ("ergonomic_chair", 35),
                ],
            },
            {
                "id": uuid.UUID("a2000000-0000-4000-8000-000000000002"),
                "name": "PMKK Bengaluru Urban - Robotics & Automation Centre",
                "code": "KA-BLR-0219",
                "state": "Karnataka",
                "district": "Bengaluru Urban",
                "latitude": 12.9716,
                "longitude": 77.5946,
                "has_mismatch": False,
                "enrolled": 28,
                "cameras": [
                    {"name": "Robotics & PLC Automation Lab", "rtsp": "rtsp://cctv-blr.internal/live/ch1", "loc": "Main Mechatronics Bay"},
                ],
                "inventory": [
                    ("desktop_computer", 28),
                    ("industrial_workbench", 20),
                    ("plc_automation_trainer", 6),
                    ("oscilloscope", 14),
                ],
            },
            {
                "id": uuid.UUID("a3000000-0000-4000-8000-000000000003"),
                "name": "PMKK Bhubaneswar - Apparel & Textile Design Centre",
                "code": "OD-BBI-0342",
                "state": "Odisha",
                "district": "Khordha",
                "latitude": 20.2961,
                "longitude": 85.8245,
                "has_mismatch": True,  # DELIBERATE MISMATCH: Ghost attendance
                "enrolled": 35,
                "cameras": [
                    {"name": "Industrial Stitching & Sewing Bay", "rtsp": "rtsp://cctv-bbi.internal/live/ch1", "loc": "Block B, Large Hall"},
                ],
                "inventory": [
                    ("industrial_sewing_machine", 35),
                    ("cutting_table", 8),
                    ("steam_iron_station", 6),
                ],
            },
            {
                "id": uuid.UUID("a4000000-0000-4000-8000-000000000004"),
                "name": "PMKK Jaipur - Precision Automotive Academy",
                "code": "RJ-JPR-0418",
                "state": "Rajasthan",
                "district": "Jaipur",
                "latitude": 26.9124,
                "longitude": 75.7873,
                "has_mismatch": False,
                "enrolled": 25,
                "cameras": [
                    {"name": "Automotive Assembly & Welding Bay", "rtsp": "rtsp://cctv-jpr.internal/live/ch1", "loc": "Heavy Workshop Floor"},
                ],
                "inventory": [
                    ("welding_booth", 12),
                    ("four_stroke_engine_rig", 4),
                    ("automotive_lift", 2),
                    ("mechanic_tool_cabinet", 15),
                ],
            },
            {
                "id": uuid.UUID("a5000000-0000-4000-8000-000000000005"),
                "name": "PMKK Varanasi - Heritage Handloom & Digital Crafts",
                "code": "UP-VNS-0581",
                "state": "Uttar Pradesh",
                "district": "Varanasi",
                "latitude": 25.3176,
                "longitude": 82.9739,
                "has_mismatch": True,  # DELIBERATE MISMATCH: Ghost attendance
                "enrolled": 30,
                "cameras": [
                    {"name": "Digital Weaving & CAD Design Studio", "rtsp": "rtsp://cctv-vns.internal/live/ch1", "loc": "East Wing, Room 302"},
                ],
                "inventory": [
                    ("desktop_computer", 20),
                    ("jacquard_loom", 12),
                    ("digital_design_tablet", 20),
                ],
            },
        ]

        device_keys_summary = []
        today = datetime.now(timezone.utc).date()

        for cdata in centres_data:
            centre = Centre(
                id=cdata["id"],
                name=cdata["name"],
                code=cdata["code"],
                state=cdata["state"],
                district=cdata["district"],
                latitude=cdata["latitude"],
                longitude=cdata["longitude"],
                is_active=True,
            )
            session.add(centre)

            # Sanctioned Inventory
            for item_type, qty in cdata["inventory"]:
                inv = SanctionedInventory(
                    centre_id=centre.id,
                    item_type=item_type,
                    sanctioned_quantity=qty,
                    last_verified_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 10)),
                )
                session.add(inv)

            # Cameras & Device Keys
            cameras_created = []
            for cam_info in cdata["cameras"]:
                cam = Camera(
                    centre_id=centre.id,
                    name=cam_info["name"],
                    rtsp_url=cam_info["rtsp"],
                    location_description=cam_info["loc"],
                    is_active=True,
                )
                session.add(cam)
                session.flush()
                session.refresh(cam)
                cameras_created.append(cam)

                # Provision Device Key for this camera
                raw_key = generate_raw_device_key()
                dev_key = DeviceKey(
                    key_hash=hash_device_key(raw_key),
                    name=f"Gateway for {cam.name}",
                    centre_id=centre.id,
                    camera_id=cam.id,
                    is_active=True,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=365),
                )
                session.add(dev_key)

                device_keys_summary.append({
                    "centre_code": centre.code,
                    "centre_name": centre.name,
                    "centre_id": str(centre.id),
                    "camera_id": str(cam.id),
                    "camera_name": cam.name,
                    "plaintext_key": raw_key,
                })

            # 14 days of Attendance Records and Readings
            for day_offset in range(14, -1, -1):
                rec_date = today - timedelta(days=day_offset)
                enrolled = cdata["enrolled"]

                if cdata["has_mismatch"]:
                    # Deliberate ghost attendance mismatch:
                    # Official portal reports high attendance (e.g. 90-95%)
                    # CCTV edge count sees only a fraction (4-9 persons)
                    official_present = int(enrolled * random.uniform(0.90, 0.98))
                    cctv_base_count = random.randint(4, 8)
                else:
                    # Genuine centre:
                    # CCTV matches official attendance closely (+/- 1-2 persons)
                    official_present = int(enrolled * random.uniform(0.82, 0.92))
                    cctv_base_count = max(0, official_present - random.randint(-1, 2))

                att = AttendanceRecord(
                    centre_id=centre.id,
                    date=rec_date,
                    enrolled_count=enrolled,
                    official_present_count=official_present,
                    source="skill_india_biometric_portal",
                )
                session.add(att)

                # Seed sample readings during training hours (09:00, 11:30, 14:00, 16:30 UTC)
                for cam in cameras_created:
                    for hour, minute in [(9, 0), (11, 30), (14, 0), (16, 30)]:
                        # Fluctuate slightly around base count
                        sample_count = max(0, cctv_base_count + random.choice([-1, 0, 1]))
                        raw_sample = sample_count + random.choice([0, 1])  # Raw might catch a passerby
                        reading_dt = datetime(
                            rec_date.year, rec_date.month, rec_date.day,
                            hour, minute, 0, tzinfo=timezone.utc
                        )
                        reading = Reading(
                            centre_id=centre.id,
                            camera_id=cam.id,
                            timestamp=reading_dt,
                            raw_count=raw_sample,
                            stable_count=sample_count,
                            equipment={"workstations_active": min(sample_count, 20)},
                            frame_quality=round(random.uniform(0.78, 0.96), 2),
                        )
                        session.add(reading)

        session.commit()
        logger.info("Database seeding complete!")

        # Print formatted summary table for developer verification
        print("\n" + "=" * 95)
        print(" POP SEED DATA GENERATION COMPLETE")
        print("=" * 95)
        print("\n1. USER CREDENTIALS:")
        print("   - Super Admin : admin@pop.gov.in       / AdminSecret123!")
        print("   - Inspector   : inspector.verma@gov.in / InspectorSecret123!")
        print("   - Viewer      : viewer.sharma@gov.in   / ViewerSecret123!")

        print("\n2. SEEDED CENTRES & ANOMALY SCENARIOS:")
        for c in centres_data:
            status_desc = "🚨 DELIBERATE GHOST ATTENDANCE MISMATCH" if c["has_mismatch"] else "✅ Normal (CCTV matches portal)"
            print(f"   - [{c['code']}] {c['name']}")
            print(f"     ID: {c['id']} | State: {c['state']} | Status: {status_desc}")

        print("\n3. PROVISIONED EDGE CAMERA DEVICE KEYS (Copy to config.yaml):")
        print("-" * 95)
        for dk in device_keys_summary:
            print(f" Centre : {dk['centre_code']} ({dk['centre_name']})")
            print(f" Centre ID: {dk['centre_id']}")
            print(f" Camera ID: {dk['camera_id']} ({dk['camera_name']})")
            print(f" X-Device-Key: {dk['plaintext_key']}")
            print("-" * 95)
        print("\n" + "=" * 95 + "\n")


if __name__ == "__main__":
    seed_database()
