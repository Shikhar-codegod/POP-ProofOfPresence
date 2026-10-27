"""Synthetic CCTV video generator for testing and evaluating edge counting pipelines.

Renders an annotated classroom environment with:
- Front podium / trainer exclusion zone
- Stationary seated students
- A stationary instructor at the podium
- An occasional moving attendee entering and leaving
- Timestamps rendered in top corner
"""

import argparse
from datetime import datetime, timezone
import logging
import os
import cv2
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pop.ml.synthetic")


def draw_human_figure(
    img: np.ndarray,
    center_x: int,
    center_y: int,
    scale: float = 1.0,
    color: tuple = (60, 60, 200),
    is_seated: bool = True,
) -> None:
    """Draw a simplified stylized person figure (head, torso, arms) in OpenCV."""
    # Head
    head_radius = int(14 * scale)
    head_center = (center_x, center_y - int(32 * scale))
    cv2.circle(img, head_center, head_radius, (220, 190, 170), -1)
    cv2.circle(img, head_center, head_radius, (50, 50, 50), 2)

    # Torso
    torso_w = int(24 * scale)
    torso_h = int(36 * scale) if is_seated else int(48 * scale)
    torso_top_left = (center_x - torso_w // 2, center_y - int(18 * scale))
    torso_bottom_right = (center_x + torso_w // 2, center_y - int(18 * scale) + torso_h)
    cv2.rectangle(img, torso_top_left, torso_bottom_right, color, -1)
    cv2.rectangle(img, torso_top_left, torso_bottom_right, (40, 40, 40), 2)

    # Shoulders
    cv2.circle(img, (center_x - torso_w // 2, center_y - int(14 * scale)), int(6 * scale), color, -1)
    cv2.circle(img, (center_x + torso_w // 2, center_y - int(14 * scale)), int(6 * scale), color, -1)


def generate_classroom_clip(
    output_path: str = "pop/ml/sample_classroom.mp4",
    duration_sec: int = 14,
    fps: int = 25,
    width: int = 640,
    height: int = 480,
    num_students: int = 12,
) -> str:
    """Generate a deterministic synthetic classroom CCTV video clip.

    Args:
        output_path: Destination MP4 file path.
        duration_sec: Total length of generated video in seconds.
        fps: Frames per second.
        width: Video frame width in pixels.
        height: Video frame height in pixels.
        num_students: Number of stationary students seated at desks.

    Returns:
        str: Absolute path to the generated MP4 file.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    if not out.isOpened():
        raise RuntimeError(f"Could not open VideoWriter at {output_path}")

    total_frames = duration_sec * fps
    logger.info(f"Generating synthetic video: '{output_path}' ({duration_sec}s, {fps} FPS, {width}x{height})")

    # Desk positions: 3 rows of 4 columns on the right half
    student_positions = []
    cols, rows = 4, 3
    col_spacing = int((width * 0.55) / cols)
    row_spacing = int((height * 0.55) / rows)
    start_x = int(width * 0.40)
    start_y = int(height * 0.35)

    count = 0
    for r in range(rows):
        for c in range(cols):
            if count >= num_students:
                break
            sx = start_x + c * col_spacing + 20
            sy = start_y + r * row_spacing + 30
            student_positions.append((sx, sy))
            count += 1

    # Trainer position: front podium area (normalized ~ x: 0.18, y: 0.25)
    trainer_x = int(width * 0.18)
    trainer_y = int(height * 0.28)

    for frame_idx in range(total_frames):
        video_time_sec = frame_idx / fps

        # 1. Background classroom canvas (cream walls, gray tiled floor)
        frame = np.ones((height, width, 3), dtype=np.uint8) * 230
        cv2.rectangle(frame, (0, int(height * 0.3)), (width, height), (200, 205, 210), -1)

        # Floor tile grid
        for gy in range(int(height * 0.3), height, 40):
            cv2.line(frame, (0, gy), (width, gy), (180, 185, 190), 1)

        # 2. Draw front podium / trainer exclusion zone box
        podium_rect = (10, 10, int(width * 0.35), int(height * 0.50))
        cv2.rectangle(
            frame,
            (podium_rect[0], podium_rect[1]),
            (podium_rect[2], podium_rect[3]),
            (180, 220, 180),
            1,
        )
        cv2.putText(
            frame,
            "TRAINER ZONE",
            (podium_rect[0] + 10, podium_rect[1] + 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (60, 120, 60),
            1,
        )

        # 3. Draw Trainer (standing at podium, moving slightly left/right)
        trainer_sway = int(6 * np.sin(video_time_sec * 1.5))
        draw_human_figure(
            frame,
            center_x=trainer_x + trainer_sway,
            center_y=trainer_y,
            scale=1.1,
            color=(180, 80, 50),
            is_seated=False,
        )

        # 4. Draw Student desks and students
        for sx, sy in student_positions:
            # Desk surface
            cv2.rectangle(frame, (sx - 24, sy - 5), (sx + 24, sy + 18), (140, 110, 80), -1)
            cv2.rectangle(frame, (sx - 24, sy - 5), (sx + 24, sy + 18), (80, 60, 40), 1)
            # Student figure
            draw_human_figure(frame, sx, sy, scale=0.9, color=(50, 100, 160), is_seated=True)

        # 5. Transient attendee: enters at t=4s, leaves at t=10s
        if 4.0 <= video_time_sec <= 10.0:
            walk_progress = (video_time_sec - 4.0) / 6.0
            # Walks down the middle corridor
            walk_x = int(width * 0.36)
            walk_y = int(height * 0.4 + walk_progress * (height * 0.45))
            draw_human_figure(frame, walk_x, walk_y, scale=1.0, color=(120, 60, 140), is_seated=False)

        # 6. Render CCTV Timestamp overlay
        timestamp_str = f"CCTV-01 [POP-EDGE] | REC 2026-10-27 10:00:{int(video_time_sec):02d} UTC"
        cv2.putText(
            frame,
            timestamp_str,
            (15, height - 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (40, 40, 40),
            1,
        )

        out.write(frame)

    out.release()
    logger.info(f"Synthetic video successfully generated: '{output_path}'")
    return os.path.abspath(output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic CCTV classroom video fixture")
    parser.add_argument("--output", default="pop/ml/sample_classroom.mp4", help="Output MP4 path")
    parser.add_argument("--duration", type=int, default=14, help="Duration in seconds")
    args = parser.parse_args()
    generate_classroom_clip(output_path=args.output, duration_sec=args.duration)
