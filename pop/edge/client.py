"""HTTP telemetry client for edge gateways to transmit readings to POP backend with backoff retries."""

from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, Optional
import requests

logger = logging.getLogger("pop.edge.client")


class EdgeBackendClient:
    """HTTP client responsible for dispatching aggregated telemetry to the central POP API.

    Features:
    - Custom X-Device-Key authentication header.
    - Idempotent request dispatch.
    - Exponential backoff retry policy on transient connection failures and 5xx errors.
    - Graceful non-blocking error recovery when network is unavailable.
    """

    def __init__(
        self,
        backend_url: str,
        device_key: str,
        centre_id: str,
        camera_id: str,
        max_retries: int = 4,
        backoff_factor: float = 1.5,
        timeout_sec: float = 8.0,
    ) -> None:
        """Initialize the edge HTTP client.

        Args:
            backend_url: Ingestion endpoint URL (e.g. 'http://localhost:8000/api/v1/readings').
            device_key: Plaintext cryptographic device key provisioned for this edge node.
            centre_id: Target facility UUID string.
            camera_id: Target CCTV camera UUID string.
            max_retries: Maximum consecutive attempts on transient failures.
            backoff_factor: Multiplier for exponential backoff delay.
            timeout_sec: Socket connect and read timeout in seconds.
        """
        self.backend_url = backend_url.rstrip("/")
        self.device_key = device_key.strip()
        self.centre_id = centre_id.strip()
        self.camera_id = camera_id.strip()
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.timeout_sec = timeout_sec

        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "POP-EdgeGateway/1.0.0",
            "X-Device-Key": self.device_key,
        })

    def build_reading_payload(
        self,
        timestamp: datetime,
        raw_count: int,
        stable_count: int,
        frame_quality: float,
        equipment: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Construct validated JSON payload conforming to POP API Contract v1.0."""
        # Ensure UTC timezone formatting
        if timestamp.tzinfo is None:
            ts_utc = timestamp.replace(tzinfo=timezone.utc)
        else:
            ts_utc = timestamp.astimezone(timezone.utc)

        return {
            "centre_id": self.centre_id,
            "camera_id": self.camera_id,
            "timestamp": ts_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "raw_count": int(raw_count),
            "stable_count": int(stable_count),
            "equipment": equipment or {},
            "frame_quality": float(round(frame_quality, 3)),
        }

    def post_reading(
        self,
        timestamp: datetime,
        raw_count: int,
        stable_count: int,
        frame_quality: float,
        equipment: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Dispatch reading payload to backend with exponential backoff retry.

        Args:
            timestamp: Sample UTC datetime.
            raw_count: Unfiltered person detections.
            stable_count: Trainer-excluded rolling median headcount.
            frame_quality: Normalized image quality score (0.0 to 1.0).
            equipment: Optional active infrastructure breakdown.

        Returns:
            Optional[Dict[str, Any]]: Persisted reading object from backend, or None on failure.
        """
        payload = self.build_reading_payload(
            timestamp=timestamp,
            raw_count=raw_count,
            stable_count=stable_count,
            frame_quality=frame_quality,
            equipment=equipment,
        )

        delay = 1.0
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._session.post(
                    self.backend_url,
                    json=payload,
                    timeout=self.timeout_sec,
                )

                # HTTP 201 Created (new) or HTTP 200 OK (idempotent duplicate)
                if response.status_code in (200, 201):
                    res_json = response.json()
                    status_text = "created" if response.status_code == 201 else "idempotent match"
                    logger.debug(
                        f"Successfully posted reading ({status_text}) for camera {self.camera_id} "
                        f"@ {payload['timestamp']}"
                    )
                    return res_json

                # Client-side 4xx errors (authentication, validation, bad uuid) - do not retry
                if 400 <= response.status_code < 500:
                    logger.error(
                        f"Non-retryable client error {response.status_code} from {self.backend_url}: "
                        f"{response.text}"
                    )
                    return None

                # Server-side 5xx errors - transient, proceed to backoff
                logger.warning(
                    f"Server returned HTTP {response.status_code} on attempt {attempt}/{self.max_retries}. "
                    f"Retrying in {delay:.1f}s..."
                )

            except (requests.ConnectionError, requests.Timeout) as exc:
                logger.warning(
                    f"Network connection error on attempt {attempt}/{self.max_retries}: {exc}. "
                    f"Retrying in {delay:.1f}s..."
                )
            except Exception as exc:
                logger.error(f"Unexpected error posting reading on attempt {attempt}: {exc}")
                return None

            if attempt < self.max_retries:
                time.sleep(delay)
                delay *= self.backoff_factor

        # -------------------------------------------------------------------------
        # TODO: Phase 4 - Offline local SQLite disk buffer for intermittent rural connectivity.
        # When all retries fail, persist payload locally into an on-device SQLite spool
        # queue (`pop/edge/spool.db`) to replay upon network restoration.
        # -------------------------------------------------------------------------
        logger.error(
            f"Failed to transmit reading after {self.max_retries} attempts for timestamp "
            f"{payload['timestamp']}. Telemetry sample skipped (Phase 4 offline queue will buffer this)."
        )
        return None
