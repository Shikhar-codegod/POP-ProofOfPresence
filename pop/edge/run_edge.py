"""Main edge video analytics execution loop for ProofOfPresence (POP).

Processes video files, executes YOLO person detection, applies trainer exclusion,
computes smoothed rolling median headcount, measures image quality scores,
writes telemetry logs, and generates timeline visualizations.
"""

import argparse
import csv
from datetime import datetime, timezone
import logging
import os
import sys
from typing import Any, Dict, List, Optional
import cv2
import matplotlib.pyplot as plt
import numpy as np
import yaml

from capture import sample_video_frames
from client import EdgeBackendClient
from counter import RollingMedianFilter, compute_headcount, is_point_in_zone, get_box_center
from detector import YOLO11nDetector
from quality import compute_frame_quality

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pop.edge.runner")


def load_config(config_path: str) -> Dict[str, Any]:
    """Load and parse YAML edge configuration file."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found at: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    logger.info(f"Loaded edge configuration from: {config_path}")
    return config


def generate_timeline_plot(
    records: List[Dict[str, Any]],
    output_path: str,
) -> None:
    """Generate and save matplotlib timeline plot comparing raw vs rolling median headcount.

    Args:
        records: List of sample dictionary rows.
        output_path: Destination PNG image path.
    """
    if not records:
        logger.warning("No telemetry samples to plot.")
        return

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    times = [r["video_time_sec"] for r in records]
    raw_counts = [r["raw_count"] for r in records]
    stable_counts = [r["stable_count"] for r in records]

    plt.figure(figsize=(10, 5), dpi=150)
    plt.plot(times, raw_counts, label="Raw Detection Count", color="#94a3b8", linestyle="--", marker="o", alpha=0.7)
    plt.plot(times, stable_counts, label="Stable Median Count", color="#2563eb", linewidth=2.5, marker="s")

    plt.title("POP Edge Attendance Verification Timeline", fontsize=14, fontweight="bold", pad=12)
    plt.xlabel("Video Timeline (Seconds)", fontsize=11)
    plt.ylabel("Observed Persons", fontsize=11)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend(loc="upper right", frameon=True)
    plt.tight_layout()

    plt.savefig(output_path)
    plt.close()
    logger.info(f"Generated headcount timeline plot saved to: '{output_path}'")


def write_readings_csv(
    records: List[Dict[str, Any]],
    output_path: str,
) -> None:
    """Write telemetry samples to CSV file."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    fields = ["timestamp", "video_time_sec", "raw_count", "stable_count", "frame_quality"]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in records:
            writer.writerow({
                "timestamp": r["timestamp"].isoformat(),
                "video_time_sec": round(r["video_time_sec"], 2),
                "raw_count": r["raw_count"],
                "stable_count": r["stable_count"],
                "frame_quality": r["frame_quality"],
            })

    logger.info(f"Wrote {len(records)} telemetry records to CSV: '{output_path}'")


def annotate_frame(
    frame: np.ndarray,
    boxes: List[Any],
    zone: Optional[Dict[str, float]],
    raw_count: int,
    stable_count: int,
    quality_score: float,
    video_sec: float,
) -> np.ndarray:
    """Render detection boxes, trainer exclusion zone, and counts onto frame image."""
    annotated = frame.copy()
    h, w = annotated.shape[:2]

    # Draw trainer exclusion zone if configured
    if zone:
        zx1, zy1 = int(zone["x_min"] * w), int(zone["y_min"] * h)
        zx2, zy2 = int(zone["x_max"] * w), int(zone["y_max"] * h)
        cv2.rectangle(annotated, (zx1, zy1), (zx2, zy2), (0, 200, 255), 2)
        cv2.putText(
            annotated,
            "TRAINER EXCLUSION ZONE",
            (zx1 + 8, zy1 + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 200, 255),
            1,
        )

    # Draw person bounding boxes
    for b in boxes:
        x1, y1, x2, y2, conf = b
        px1, py1 = int(x1 * w), int(y1 * h)
        px2, py2 = int(x2 * w), int(y2 * h)
        cx, cy = get_box_center(b)
        in_zone = zone and is_point_in_zone((cx, cy), zone)

        color = (0, 165, 255) if in_zone else (0, 220, 0)
        label = f"Trainer ({conf:.2f})" if in_zone else f"Person ({conf:.2f})"

        cv2.rectangle(annotated, (px1, py1), (px2, py2), color, 2)
        cv2.putText(annotated, label, (px1, max(15, py1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

    # Overlay stats HUD bar
    hud_bg = np.zeros((70, w, 3), dtype=np.uint8)
    annotated[0:70, 0:w] = cv2.addWeighted(annotated[0:70, 0:w], 0.3, hud_bg, 0.7, 0)

    hud_text = (
        f"POP EDGE | Time: {video_sec:05.1f}s | Raw: {raw_count} | "
        f"Stable: {stable_count} | Quality: {quality_score:.2f}"
    )
    cv2.putText(annotated, hud_text, (15, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

    return annotated


def run_pipeline(
    config_path: str = "pop/edge/config.yaml",
    video_path: Optional[str] = None,
    no_post: bool = True,
    save_video_override: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """Execute complete edge person detection and counting pipeline.

    Args:
        config_path: YAML configuration file path.
        video_path: Input video file path (overrides config if provided).
        no_post: If True, skips HTTP POST ingestion to backend.
        save_video_override: Optional override for saving annotated preview video.

    Returns:
        List[Dict[str, Any]]: Array of processed sample records.
    """
    config = load_config(config_path)

    # Resolve video path
    if not video_path:
        video_path = config.get("video_path", "pop/ml/sample_classroom.mp4")

    # If test video doesn't exist yet, generate it automatically
    if not os.path.exists(video_path):
        logger.info(f"Input video '{video_path}' does not exist. Auto-generating synthetic test clip...")
        from pop.ml.generate_test_video import generate_classroom_clip
        generate_classroom_clip(output_path=video_path, duration_sec=14)

    # Initialize YOLO detector
    det_cfg = config.get("detection", {})
    detector = YOLO11nDetector(
        model_path=det_cfg.get("model_path", "yolo11n.pt"),
        confidence_threshold=det_cfg.get("confidence_threshold", 0.35),
        target_class_id=det_cfg.get("target_class_id", 0),
    )

    # Initialize Counter and Rolling Filter
    cnt_cfg = config.get("counting", {})
    window_k = cnt_cfg.get("rolling_window_k", 5)
    exclusion_mode = cnt_cfg.get("trainer_exclusion_mode", "zone")
    trainer_zone = cnt_cfg.get("trainer_zone", None)
    median_filter = RollingMedianFilter(window_k=window_k)

    # Sampling setup
    smp_cfg = config.get("sampling", {})
    interval_sec = smp_cfg.get("interval_sec", 2.0)
    max_frames = smp_cfg.get("max_frames", None)

    # Output paths
    out_cfg = config.get("output", {})
    csv_path = out_cfg.get("csv_path", "pop/edge/output/readings.csv")
    plot_path = out_cfg.get("plot_path", "pop/edge/output/count_timeline.png")
    save_video = save_video_override if save_video_override is not None else out_cfg.get("save_annotated_video", False)
    annotated_path = out_cfg.get("annotated_video_path", "pop/edge/output/annotated.mp4")

    # Backend client setup
    backend_client = None
    if not no_post:
        b_cfg = config.get("backend", {})
        backend_client = EdgeBackendClient(
            backend_url=b_cfg.get("url", "http://localhost:8000/api/v1/readings"),
            device_key=b_cfg.get("device_key", ""),
            centre_id=b_cfg.get("centre_id", ""),
            camera_id=b_cfg.get("camera_id", ""),
            max_retries=b_cfg.get("max_retries", 4),
            backoff_factor=b_cfg.get("backoff_factor", 1.5),
        )
        logger.info(f"Initialized EdgeBackendClient pointing to: {backend_client.backend_url}")

    video_writer = None
    processed_records: List[Dict[str, Any]] = []

    logger.info("==========================================================")
    logger.info(" STARTING POP EDGE COUNTING PIPELINE")
    logger.info(f" - Video Source     : {video_path}")
    logger.info(f" - Sampling Interval: {interval_sec}s")
    logger.info(f" - Rolling Window K : {window_k}")
    logger.info(f" - Trainer Policy   : {exclusion_mode}")
    logger.info(f" - Ingest to Backend: {'Disabled (--no-post)' if no_post else 'Enabled'}")
    logger.info("==========================================================")

    for sample_time, frame, video_sec in sample_video_frames(
        video_path=video_path,
        interval_sec=interval_sec,
        max_frames=max_frames,
    ):
        # 1. Compute frame quality metrics
        quality_score, brightness, sharpness = compute_frame_quality(frame)

        # 2. Run YOLO person detection
        boxes = detector.detect(frame)
        raw_count = len(boxes)

        # 3. Apply trainer exclusion policy
        effective_count = compute_headcount(boxes, mode=exclusion_mode, zone=trainer_zone)

        # 4. Smooth count via rolling median filter
        stable_count = median_filter.update(effective_count)

        logger.info(
            f"Frame @ {video_sec:05.1f}s | Raw Detections: {raw_count:2d} | "
            f"After Exclusion: {effective_count:2d} | Stable Count: {stable_count:2d} | "
            f"Quality: {quality_score:.2f}"
        )

        # 5. Ingest telemetry reading to backend if enabled
        posted_reading = None
        if backend_client is not None:
            posted_reading = backend_client.post_reading(
                timestamp=sample_time,
                raw_count=raw_count,
                stable_count=stable_count,
                frame_quality=quality_score,
            )

        record = {
            "timestamp": sample_time,
            "video_time_sec": video_sec,
            "raw_count": raw_count,
            "effective_count": effective_count,
            "stable_count": stable_count,
            "frame_quality": quality_score,
            "brightness": brightness,
            "sharpness": sharpness,
            "posted_to_backend": bool(posted_reading),
        }
        processed_records.append(record)

        # 5. Handle video annotation output
        if save_video:
            h, w = frame.shape[:2]
            if video_writer is None:
                os.makedirs(os.path.dirname(os.path.abspath(annotated_path)), exist_ok=True)
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                fps = int(1.0 / interval_sec) if interval_sec <= 1.0 else 2
                video_writer = cv2.VideoWriter(annotated_path, fourcc, fps, (w, h))

            annotated = annotate_frame(
                frame=frame,
                boxes=boxes,
                zone=trainer_zone if exclusion_mode == "zone" else None,
                raw_count=raw_count,
                stable_count=stable_count,
                quality_score=quality_score,
                video_sec=video_sec,
            )
            video_writer.write(annotated)

    if video_writer:
        video_writer.release()
        logger.info(f"Saved annotated preview video to: '{annotated_path}'")

    # Write output artifacts
    write_readings_csv(processed_records, csv_path)
    generate_timeline_plot(processed_records, plot_path)

    logger.info("==========================================================")
    logger.info(f" PIPELINE COMPLETE: Processed {len(processed_records)} frames successfully.")
    logger.info("==========================================================")

    return processed_records


def main() -> None:
    """CLI entrypoint for run_edge.py."""
    parser = argparse.ArgumentParser(description="ProofOfPresence (POP) Edge Analytics Runner")
    parser.add_argument("--config", default="pop/edge/config.yaml", help="Path to config.yaml")
    parser.add_argument("--video", default=None, help="Input video file path")
    parser.add_argument("--no-post", action="store_true", default=False, help="Disable backend HTTP ingestion (offline mode)")
    parser.add_argument("--save-video", action="store_true", default=False, help="Render annotated output video")

    args = parser.parse_args()
    run_pipeline(
        config_path=args.config,
        video_path=args.video,
        no_post=args.no_post,
        save_video_override=args.save_video,
    )


if __name__ == "__main__":
    main()
