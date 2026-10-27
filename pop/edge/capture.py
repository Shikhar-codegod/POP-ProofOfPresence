"""Video ingestion and sampling generator operating strictly in video-timeline seconds."""

from datetime import datetime, timedelta, timezone
import logging
from typing import Generator, Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger("pop.edge.capture")


def sample_video_frames(
    video_path: str,
    interval_sec: float = 2.0,
    base_timestamp: Optional[datetime] = None,
    max_frames: Optional[int] = None,
) -> Generator[Tuple[datetime, np.ndarray, float], None, None]:
    """Sample video frames at fixed intervals of VIDEO time (not wall-clock time).

    Args:
        video_path: Path to the recorded MP4/AVI video file.
        interval_sec: Interval in seconds of video playback between samples.
        base_timestamp: Starting UTC timestamp assigned to video timestamp t=0.
                        Defaults to current UTC time if not supplied.
        max_frames: Optional upper limit on sampled frames for testing.

    Yields:
        Tuple[datetime, np.ndarray, float]:
            - Sample UTC timestamp (base_timestamp + video_time_sec).
            - Decoded BGR frame image array.
            - Video time elapsed in seconds from start of file.

    Raises:
        FileNotFoundError: If the video file cannot be opened.
        RuntimeError: If video properties (FPS) cannot be resolved.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Failed to open video file at: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or np.isnan(fps):
        logger.warning("Video FPS could not be reliably determined. Falling back to 25.0 FPS.")
        fps = 25.0

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / fps if fps > 0 else 0.0

    if base_timestamp is None:
        base_timestamp = datetime.now(timezone.utc)
    elif base_timestamp.tzinfo is None:
        base_timestamp = base_timestamp.replace(tzinfo=timezone.utc)

    logger.info(
        f"Initialized video capture: '{video_path}' | FPS: {fps:.2f} | "
        f"Total Frames: {total_frames} | Duration: {duration_sec:.1f}s | "
        f"Sampling interval: {interval_sec}s"
    )

    current_video_sec = 0.0
    sampled_count = 0

    try:
        while True:
            if max_frames is not None and sampled_count >= max_frames:
                logger.info(f"Reached configured max_frames limit: {max_frames}")
                break

            target_frame_idx = int(round(current_video_sec * fps))
            if target_frame_idx >= total_frames and total_frames > 0:
                logger.info("Reached end of video file timeline.")
                break

            # Seek directly to target frame in video timeline
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame_idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                logger.info(f"Video stream terminated at video time {current_video_sec:.2f}s.")
                break

            sample_time = base_timestamp + timedelta(seconds=current_video_sec)
            yield sample_time, frame, current_video_sec

            sampled_count += 1
            current_video_sec += interval_sec

    finally:
        cap.release()
        logger.info(f"Released video capture. Total frames yielded: {sampled_count}")


def sample_rtsp_stream(
    rtsp_url: str,
    interval_sec: float = 2.0,
) -> Generator[Tuple[datetime, np.ndarray, float], None, None]:
    """Stubbed RTSP live streaming capture for Phase 1.

    Raises:
        NotImplementedError: Unconditionally with clear phase roadmap message.
    """
    raise NotImplementedError(
        f"RTSP live streaming capture ('{rtsp_url}') is stubbed for Phase 1. "
        "Live network RTSP streaming is scheduled for Phase 3 edge daemon release. "
        "Please provide a local MP4/AVI video file path to 'sample_video_frames'."
    )
