"""Unit tests for edge counting, trainer exclusion, and rolling median filtering."""

import pytest
from counter import (
    RollingMedianFilter,
    compute_headcount,
    compute_rolling_median,
    filter_trainer_boxes,
    get_box_center,
    is_point_in_zone,
)


@pytest.fixture
def trainer_zone() -> dict[str, float]:
    """Standard podium/lecture exclusion zone fixture."""
    return {
        "x_min": 0.0,
        "y_min": 0.0,
        "x_max": 0.35,
        "y_max": 0.50,
    }


@pytest.fixture
def sample_boxes() -> list[tuple[float, float, float, float, float]]:
    """Sample bounding boxes: 1 trainer at podium, 3 seated students."""
    return [
        (0.10, 0.15, 0.20, 0.35, 0.88),  # Center: (0.15, 0.25) -> Inside trainer zone
        (0.45, 0.35, 0.55, 0.65, 0.82),  # Center: (0.50, 0.50) -> Outside trainer zone
        (0.65, 0.40, 0.75, 0.70, 0.91),  # Center: (0.70, 0.55) -> Outside trainer zone
        (0.70, 0.45, 0.80, 0.75, 0.79),  # Center: (0.75, 0.60) -> Outside trainer zone
    ]


def test_get_box_center():
    """Verify normalized center coordinate calculation."""
    bbox = (0.2, 0.4, 0.6, 0.8, 0.95)
    cx, cy = get_box_center(bbox)
    assert pytest.approx(cx) == 0.4
    assert pytest.approx(cy) == 0.6


def test_is_point_in_zone(trainer_zone):
    """Verify rectangular boundary membership checking."""
    # Inside
    assert is_point_in_zone((0.15, 0.25), trainer_zone) is True
    # Outside
    assert is_point_in_zone((0.50, 0.50), trainer_zone) is False
    # Exact Boundary
    assert is_point_in_zone((0.0, 0.0), trainer_zone) is True
    assert is_point_in_zone((0.35, 0.50), trainer_zone) is True
    # Out of bounds
    assert is_point_in_zone((-0.01, 0.25), trainer_zone) is False
    assert is_point_in_zone((0.36, 0.25), trainer_zone) is False


def test_filter_trainer_boxes_zone_mode(sample_boxes, trainer_zone):
    """Verify zone-based exclusion removes instructor and keeps students."""
    filtered = filter_trainer_boxes(sample_boxes, mode="zone", zone=trainer_zone)
    assert len(filtered) == 3
    # Ensure trainer box was filtered out
    for b in filtered:
        assert not is_point_in_zone(get_box_center(b), trainer_zone)


def test_filter_trainer_boxes_subtract_one_mode(sample_boxes):
    """In subtract_one mode, filter_trainer_boxes preserves all boxes."""
    filtered = filter_trainer_boxes(sample_boxes, mode="subtract_one")
    assert len(filtered) == len(sample_boxes)


def test_filter_trainer_boxes_none_mode(sample_boxes):
    """In none mode, filter_trainer_boxes preserves all boxes."""
    filtered = filter_trainer_boxes(sample_boxes, mode="none")
    assert len(filtered) == len(sample_boxes)


def test_filter_trainer_boxes_invalid_mode(sample_boxes):
    """Verify unsupported mode raises ValueError."""
    with pytest.raises(ValueError, match="Invalid trainer exclusion mode"):
        filter_trainer_boxes(sample_boxes, mode="invalid_mode")


def test_compute_headcount_zone_mode(sample_boxes, trainer_zone):
    """compute_headcount in zone mode returns attendee count excluding podium."""
    count = compute_headcount(sample_boxes, mode="zone", zone=trainer_zone)
    assert count == 3


def test_compute_headcount_subtract_one_mode(sample_boxes):
    """compute_headcount in subtract_one mode subtracts 1 from raw detections."""
    count = compute_headcount(sample_boxes, mode="subtract_one")
    assert count == 3  # 4 raw - 1 = 3

    # Zero bound test
    assert compute_headcount([], mode="subtract_one") == 0


def test_compute_headcount_none_mode(sample_boxes):
    """compute_headcount in none mode returns raw detection count."""
    count = compute_headcount(sample_boxes, mode="none")
    assert count == 4


def test_compute_rolling_median_odd_window():
    """Verify median calculation for odd window length."""
    history = [10, 11, 14, 12, 13]
    median = compute_rolling_median(history, window_k=5)
    assert median == 12


def test_compute_rolling_median_even_window():
    """Verify median calculation and rounding for even window length."""
    history = [10, 12, 14, 16]
    median = compute_rolling_median(history, window_k=4)
    # (12 + 14) / 2 = 13
    assert median == 13


def test_compute_rolling_median_empty():
    """Empty history yields 0."""
    assert compute_rolling_median([], window_k=5) == 0


def test_compute_rolling_median_invalid_k():
    """Invalid K <= 0 raises ValueError."""
    with pytest.raises(ValueError, match="window_k must be a positive integer"):
        compute_rolling_median([10, 12], window_k=0)


def test_rolling_median_filter_spike_noise_smoothing():
    """Verify that a transient outlier spike does not distort stable attendance count."""
    filter_k5 = RollingMedianFilter(window_k=5)

    # Establish baseline of 12 students
    for _ in range(4):
        filter_k5.update(12)

    assert filter_k5.current_median() == 12

    # A sudden noisy spike (e.g. YOLO hallucination / reflection)
    stable_on_spike = filter_k5.update(35)
    # Buffer is [12, 12, 12, 12, 35] -> Sorted: [12, 12, 12, 12, 35] -> Median is 12!
    assert stable_on_spike == 12

    # Next reading returns to normal
    stable_next = filter_k5.update(12)
    assert stable_next == 12


def test_rolling_median_filter_reset():
    """Verify filter reset restores state to zero."""
    filter_k3 = RollingMedianFilter(window_k=3)
    filter_k3.update(20)
    filter_k3.update(22)
    assert filter_k3.current_median() > 0

    filter_k3.reset()
    assert filter_k3.current_median() == 0
