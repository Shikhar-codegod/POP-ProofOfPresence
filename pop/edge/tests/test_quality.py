"""Unit tests for edge CCTV image quality scoring."""

import numpy as np
from quality import compute_frame_quality


def test_compute_frame_quality_normal_frame():
    """Verify composite, brightness, and sharpness metrics for a synthetic frame."""
    # Create 480x640 mock frame with some texture
    frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
    # Add high-contrast lines for sharpness variance
    frame[100:200, 100:200] = 0
    frame[300:400, 300:400] = 255

    composite, brightness, sharpness = compute_frame_quality(frame)

    assert 0.0 <= composite <= 1.0
    assert 0.0 <= brightness <= 1.0
    assert 0.0 <= sharpness <= 1.0
    assert composite == round(0.4 * brightness + 0.6 * sharpness, 3)


def test_compute_frame_quality_empty_frame():
    """Empty or None image returns zero quality scores."""
    assert compute_frame_quality(None) == (0.0, 0.0, 0.0)
    assert compute_frame_quality(np.array([])) == (0.0, 0.0, 0.0)
