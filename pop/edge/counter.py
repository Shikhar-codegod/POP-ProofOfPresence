"""Pure functional counting module for trainer exclusion and rolling median smoothing."""

from collections import deque
import math
from typing import Dict, List, Optional, Tuple

# Type aliases:
# NormalizedBBox: (x1, y1, x2, y2, confidence)
NormalizedBBox = Tuple[float, float, float, float, float]
ZoneRect = Dict[str, float]


def get_box_center(bbox: NormalizedBBox) -> Tuple[float, float]:
    """Calculate the normalized (cx, cy) center coordinates of a bounding box."""
    x1, y1, x2, y2, _ = bbox
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def is_point_in_zone(point: Tuple[float, float], zone: ZoneRect) -> bool:
    """Determine whether a 2D normalized point (cx, cy) falls within a rectangular zone.

    Args:
        point: Tuple of (x, y) coordinates in [0.0, 1.0].
        zone: Dict specifying keys 'x_min', 'y_min', 'x_max', 'y_max'.

    Returns:
        bool: True if point is inside or on the boundary of the zone.
    """
    x, y = point
    return (
        zone["x_min"] <= x <= zone["x_max"]
        and zone["y_min"] <= y <= zone["y_max"]
    )


def filter_trainer_boxes(
    boxes: List[NormalizedBBox],
    mode: str = "zone",
    zone: Optional[ZoneRect] = None,
) -> List[NormalizedBBox]:
    """Filter out trainer detections according to the chosen exclusion policy.

    Args:
        boxes: List of detected person bounding boxes.
        mode: Exclusion mode: "zone", "subtract_one", or "none".
        zone: Rectangular bounds required if mode == "zone".

    Returns:
        List[NormalizedBBox]: Candidate attendee boxes after exclusion.

    Raises:
        ValueError: If mode is not one of ('zone', 'subtract_one', 'none').
    """
    if mode == "none" or mode == "subtract_one":
        return list(boxes)

    if mode == "zone":
        if not zone:
            return list(boxes)
        return [b for b in boxes if not is_point_in_zone(get_box_center(b), zone)]

    raise ValueError(f"Invalid trainer exclusion mode: '{mode}'. Allowed: 'zone', 'subtract_one', 'none'")


def compute_headcount(
    boxes: List[NormalizedBBox],
    mode: str = "zone",
    zone: Optional[ZoneRect] = None,
) -> int:
    """Calculate instantaneous headcount after applying trainer exclusion policy.

    Args:
        boxes: List of person detections.
        mode: Exclusion mode ("zone", "subtract_one", "none").
        zone: Normalized rectangle coordinates for "zone" mode.

    Returns:
        int: Non-negative integer headcount.
    """
    if mode == "none":
        return len(boxes)

    if mode == "zone":
        filtered = filter_trainer_boxes(boxes, mode="zone", zone=zone)
        return len(filtered)

    if mode == "subtract_one":
        return max(0, len(boxes) - 1)

    raise ValueError(f"Invalid trainer exclusion mode: '{mode}'. Allowed: 'zone', 'subtract_one', 'none'")


def compute_rolling_median(history: List[int], window_k: int) -> int:
    """Calculate the integer median count across the most recent K elements.

    Args:
        history: Sequence of observed integer counts.
        window_k: Window size K (must be >= 1).

    Returns:
        int: Median value, rounded to nearest integer.
    """
    if not history:
        return 0

    if window_k <= 0:
        raise ValueError("window_k must be a positive integer >= 1")

    window = history[-window_k:]
    sorted_window = sorted(window)
    n = len(sorted_window)

    if n % 2 == 1:
        return sorted_window[n // 2]

    # For even length, take the mathematical mean and round
    mid1 = sorted_window[n // 2 - 1]
    mid2 = sorted_window[n // 2]
    return int(round((mid1 + mid2) / 2.0))


class RollingMedianFilter:
    """Stateful sliding window median filter for streaming edge counts."""

    def __init__(self, window_k: int = 5) -> None:
        """Initialize filter with fixed capacity K.

        Args:
            window_k: Rolling history window size.
        """
        if window_k < 1:
            raise ValueError("window_k must be at least 1")
        self.window_k = window_k
        self._buffer: deque[int] = deque(maxlen=window_k)

    def update(self, count: int) -> int:
        """Append count to window and return updated stable median.

        Args:
            count: Instantaneous headcount.

        Returns:
            int: Smoothed rolling median count.
        """
        self._buffer.append(count)
        return compute_rolling_median(list(self._buffer), self.window_k)

    def current_median(self) -> int:
        """Return the current rolling median without adding a new sample."""
        return compute_rolling_median(list(self._buffer), self.window_k)

    def reset(self) -> None:
        """Clear filter history."""
        self._buffer.clear()
