"""Unit tests for frame quality scoring, RTSP capture stub, and evaluation metrics."""

import numpy as np
import pytest

from capture import sample_rtsp_stream
from evaluate import compute_metrics, compute_scenario_breakdown, join_by_nearest_timestamp
from quality import compute_frame_quality


def test_compute_frame_quality_bounds_and_contrast() -> None:
    """Sharp mid-tone image should score higher than pitch-dark or empty frames."""
    # Empty frame
    comp_empty, b_empty, s_empty = compute_frame_quality(np.array([], dtype=np.uint8))
    assert (comp_empty, b_empty, s_empty) == (0.0, 0.0, 0.0)

    # Pitch-black uniform frame
    dark_frame = np.zeros((240, 320, 3), dtype=np.uint8)
    comp_dark, _, _ = compute_frame_quality(dark_frame)
    assert 0.0 <= comp_dark < 0.2

    # High-contrast checkerboard with mid luminance
    sharp_frame = np.full((240, 320, 3), 128, dtype=np.uint8)
    sharp_frame[::2, ::2] = 200
    sharp_frame[1::2, 1::2] = 60
    comp_sharp, b_sharp, s_sharp = compute_frame_quality(sharp_frame)
    assert 0.8 <= comp_sharp <= 1.0
    assert 0.9 <= b_sharp <= 1.0
    assert s_sharp > 0.8


def test_rtsp_stream_stub_raises_not_implemented() -> None:
    """Phase 1 RTSP stub should clearly raise NotImplementedError."""
    with pytest.raises(NotImplementedError, match="Phase 1"):
        sample_rtsp_stream("rtsp://example.local:554/stream")


def test_evaluate_join_and_metrics() -> None:
    """Verify nearest-timestamp join, MAE, +/-1 percentage, and scenario breakdown."""
    gt = [
        {"video_id": "v1", "timestamp_sec": 0.0, "true_count": 10, "scenario": "baseline", "notes": ""},
        {"video_id": "v1", "timestamp_sec": 2.0, "true_count": 10, "scenario": "baseline", "notes": ""},
        {"video_id": "v1", "timestamp_sec": 4.0, "true_count": 12, "scenario": "occlusion", "notes": ""},
    ]
    preds = [
        {"video_time_sec": 0.1, "raw_count": 11, "stable_count": 10, "frame_quality": 0.9},
        {"video_time_sec": 2.0, "raw_count": 12, "stable_count": 11, "frame_quality": 0.9},
        {"video_time_sec": 4.2, "raw_count": 10, "stable_count": 10, "frame_quality": 0.85},
    ]

    matched = join_by_nearest_timestamp(gt, preds, max_tolerance_sec=1.0)
    assert len(matched) == 3

    overall = compute_metrics(matched)
    # Errors for stable: |10-10|=0, |11-10|=1, |10-12|=2 -> MAE = 1.0
    assert overall["mae_stable"] == pytest.approx(1.0)
    # Within +/-1: 2 of 3 (66.7%)
    assert overall["pct_within_one"] == pytest.approx(66.7)
    assert overall["pct_exact"] == pytest.approx(33.3)

    breakdown = compute_scenario_breakdown(matched)
    assert breakdown["baseline"]["mae_stable"] == pytest.approx(0.5)
    assert breakdown["baseline"]["pct_within_one"] == pytest.approx(100.0)
    assert breakdown["occlusion"]["mae_stable"] == pytest.approx(2.0)
