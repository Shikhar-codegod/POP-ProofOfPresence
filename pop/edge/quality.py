"""Frame quality evaluation for edge CCTV camera feeds."""

import logging
from typing import Tuple
import cv2
import numpy as np

logger = logging.getLogger("pop.edge.quality")


def compute_frame_quality(frame: np.ndarray) -> Tuple[float, float, float]:
    """Compute normalized image quality metrics from brightness and blur variance.

    Args:
        frame: OpenCV BGR image array.

    Returns:
        Tuple[float, float, float]:
            - composite_quality: Float in range [0.0, 1.0].
            - brightness_score: Normalized brightness quality [0.0, 1.0].
            - sharpness_score: Normalized sharpness quality [0.0, 1.0].
    """
    if frame is None or frame.size == 0:
        return 0.0, 0.0, 0.0

    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # 1. Brightness Score
    # Optimal CCTV luminance is between 80 and 180 on a 0-255 scale.
    # We penalize both pitch darkness (< 30) and severe glare / overexposure (> 230).
    mean_luminance = float(np.mean(gray))
    # Gaussian bell curve centered at 128
    brightness_score = float(np.exp(-((mean_luminance - 128) ** 2) / (2 * (55 ** 2))))
    brightness_score = max(0.0, min(1.0, brightness_score))

    # 2. Sharpness / Blur Score via Laplacian Variance
    # Sharp CCTV frames typically have variance > 150; heavily blurred frames < 30.
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    sharpness_score = float(min(1.0, laplacian_var / 300.0))

    # 3. Composite Frame Quality Score
    composite_quality = round(0.4 * brightness_score + 0.6 * sharpness_score, 3)

    return composite_quality, brightness_score, sharpness_score
