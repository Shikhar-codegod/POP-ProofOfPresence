"""Unit tests for rolling median filtering and trainer exclusion policies in counter.py."""

import pytest

from counter import (
    RollingMedianFilter,
    compute_headcount,
    compute_rolling_median,
    filter_trainer_boxes,
    get_box_center,
    is_point_in_zone,
)


class TestRollingMedian:
    """Test suite for compute_rolling_median and RollingMedianFilter."""

    def test_odd_window_filters_transient_spike(self) -> None:
        """Odd-length window should ignore transient outlier spikes."""
        history = [12, 12, 19, 12, 13]
        assert compute_rolling_median(history, window_k=5) == 12

    def test_even_window_averages_and_rounds_middle_two(self) -> None:
        """Even-length window should average the two middle sorted values."""
        history = [10, 12, 14, 16]
        assert compute_rolling_median(history, window_k=4) == 13

    def test_uses_only_most_recent_k_samples(self) -> None:
        """Older observations outside the trailing K window must be ignored."""
        history = [30, 30, 30, 10, 11, 12]
        assert compute_rolling_median(history, window_k=3) == 11

    def test_empty_history_returns_zero(self) -> None:
        """Empty observation list should safely yield zero."""
        assert compute_rolling_median([], window_k=5) == 0

    def test_history_shorter_than_window(self) -> None:
        """Partial window should compute median over available samples."""
        assert compute_rolling_median([8, 12], window_k=5) == 10
        assert compute_rolling_median([7], window_k=5) == 7

    def test_invalid_window_size_raises(self) -> None:
        """Non-positive window_k should raise ValueError."""
        with pytest.raises(ValueError):
            compute_rolling_median([1, 2, 3], window_k=0)
        with pytest.raises(ValueError):
            RollingMedianFilter(window_k=0)

    def test_stateful_rolling_median_filter(self) -> None:
        """RollingMedianFilter should update smoothly, maintain max K, and reset cleanly."""
        flt = RollingMedianFilter(window_k=3)
        assert flt.current_median() == 0
        assert flt.update(10) == 10
        assert flt.update(20) == 15
        assert flt.update(10) == 10
        assert flt.update(11) == 11  # window: [20, 10, 11] -> sorted [10, 11, 20] -> 11
        assert flt.current_median() == 11

        flt.reset()
        assert flt.current_median() == 0


class TestTrainerExclusion:
    """Test suite for geometric zone and subtract_one trainer exclusion."""

    TRAINER_ZONE = {"x_min": 0.0, "y_min": 0.0, "x_max": 0.35, "y_max": 0.50}

    def test_box_center_calculation(self) -> None:
        """get_box_center should compute midpoint of normalized coordinates."""
        bbox = (0.1, 0.2, 0.3, 0.4, 0.9)
        cx, cy = get_box_center(bbox)
        assert cx == pytest.approx(0.2)
        assert cy == pytest.approx(0.3)

    def test_is_point_in_zone_inside_boundary_outside(self) -> None:
        """Points inside or on the rectangle border should return True; outside False."""
        assert is_point_in_zone((0.15, 0.25), self.TRAINER_ZONE) is True
        assert is_point_in_zone((0.35, 0.50), self.TRAINER_ZONE) is True  # boundary
        assert is_point_in_zone((0.50, 0.25), self.TRAINER_ZONE) is False
        assert is_point_in_zone((0.15, 0.70), self.TRAINER_ZONE) is False

    def test_zone_exclusion_removes_trainer_keeps_students(self) -> None:
        """Zone mode should exclude boxes centered inside the podium area."""
        boxes = [
            (0.10, 0.10, 0.24, 0.40, 0.92),  # center (0.17, 0.25) -> inside trainer zone
            (0.45, 0.40, 0.55, 0.70, 0.88),  # center (0.50, 0.55) -> student
            (0.60, 0.40, 0.70, 0.70, 0.85),  # center (0.65, 0.55) -> student
            (0.20, 0.60, 0.30, 0.90, 0.81),  # center (0.25, 0.75) -> student below zone
        ]

        kept = filter_trainer_boxes(boxes, mode="zone", zone=self.TRAINER_ZONE)
        assert len(kept) == 3
        assert compute_headcount(boxes, mode="zone", zone=self.TRAINER_ZONE) == 3

    def test_subtract_one_exclusion_mode(self) -> None:
        """subtract_one mode should decrement count by 1 and clamp at zero."""
        boxes = [
            (0.1, 0.1, 0.2, 0.2, 0.9),
            (0.5, 0.5, 0.6, 0.6, 0.9),
            (0.7, 0.7, 0.8, 0.8, 0.9),
        ]
        assert compute_headcount(boxes, mode="subtract_one") == 2
        assert compute_headcount([(0.1, 0.1, 0.2, 0.2, 0.9)], mode="subtract_one") == 0
        assert compute_headcount([], mode="subtract_one") == 0

    def test_none_mode_returns_raw_count(self) -> None:
        """none mode should return total detected boxes without subtraction."""
        boxes = [
            (0.1, 0.1, 0.2, 0.2, 0.9),
            (0.5, 0.5, 0.6, 0.6, 0.9),
        ]
        assert compute_headcount(boxes, mode="none") == 2

    def test_invalid_mode_raises_value_error(self) -> None:
        """Unsupported exclusion policy strings must raise ValueError."""
        with pytest.raises(ValueError):
            compute_headcount([], mode="unknown_policy")
        with pytest.raises(ValueError):
            filter_trainer_boxes([], mode="unknown_policy")
