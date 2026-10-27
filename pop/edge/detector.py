"""Person detection engine wrapping YOLO nano with swappable detector interface."""

from abc import ABC, abstractmethod
import logging
from typing import List, Tuple
import numpy as np

logger = logging.getLogger("pop.edge.detector")

# Type alias: (x1_norm, y1_norm, x2_norm, y2_norm, confidence)
# All coordinates are normalized in range [0.0, 1.0] relative to frame dimensions.
NormalizedBBox = Tuple[float, float, float, float, float]


class BasePersonDetector(ABC):
    """Abstract interface for edge person detectors.

    Enables drop-in replacement with ONNX Runtime, TensorRT, or OpenVINO in future phases.
    """

    @abstractmethod
    def detect(self, frame: np.ndarray) -> List[NormalizedBBox]:
        """Detect persons in the given video frame.

        Args:
            frame: OpenCV BGR image array.

        Returns:
            List[NormalizedBBox]: List of normalized person bounding boxes
            `(x1, y1, x2, y2, confidence)` with values in [0.0, 1.0].
        """
        pass


class YOLO11nDetector(BasePersonDetector):
    """Ultralytics YOLO11 nano model wrapper restricted strictly to person class (COCO index 0)."""

    def __init__(
        self,
        model_path: str = "yolo11n.pt",
        confidence_threshold: float = 0.35,
        target_class_id: int = 0,
    ) -> None:
        """Initialize YOLO11n detector.

        Args:
            model_path: Path to weights file or Ultralytics model tag.
            confidence_threshold: Minimum detection confidence score.
            target_class_id: Class ID to filter (0 = 'person' in standard COCO).
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.target_class_id = target_class_id
        self._model = None
        self._load_model()

    def _load_model(self) -> None:
        """Load YOLO model weights into memory."""
        try:
            from ultralytics import YOLO
            logger.info(f"Loading YOLO model from: {self.model_path}")
            self._model = YOLO(self.model_path)
            logger.info("YOLO model successfully loaded.")
        except Exception as exc:
            logger.error(f"Failed to load YOLO model: {exc}")
            raise

    def detect(self, frame: np.ndarray) -> List[NormalizedBBox]:
        """Execute inference on frame and extract normalized person bounding boxes."""
        if frame is None or frame.size == 0:
            return []

        h, w = frame.shape[:2]
        if h == 0 or w == 0:
            return []

        # Run inference filtering only for target person class
        results = self._model(
            frame,
            conf=self.confidence_threshold,
            classes=[self.target_class_id],
            verbose=False,
        )

        detected_boxes: List[NormalizedBBox] = []
        if not results or len(results) == 0:
            return detected_boxes

        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            return detected_boxes

        # Convert xyxy tensor to CPU numpy array
        coords = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy()

        for (x1, y1, x2, y2), conf in zip(coords, confs):
            # Clamp and normalize coordinates between 0.0 and 1.0
            x1_norm = max(0.0, min(1.0, float(x1) / w))
            y1_norm = max(0.0, min(1.0, float(y1) / h))
            x2_norm = max(0.0, min(1.0, float(x2) / w))
            y2_norm = max(0.0, min(1.0, float(y2) / h))
            detected_boxes.append((x1_norm, y1_norm, x2_norm, y2_norm, float(conf)))

        return detected_boxes
