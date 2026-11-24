"""Export one label-frame per second from a video clip."""

import argparse
from pathlib import Path

import cv2


def resolve_label_output_dir(output_dir: str | None = None) -> Path:
    """Resolve the default label directory relative to this script."""
    if output_dir is None:
        return Path(__file__).resolve().parent / "label_frames"
    path = Path(output_dir).expanduser()
    return path.resolve() if path.is_absolute() else (Path.cwd() / path).resolve()


def export_label_frames(video_path: str, output_dir: str | None = None, interval_sec: float = 1.0) -> list[Path]:
    """Write one frame per interval with the timestamp overlaid."""
    video = Path(video_path).expanduser().resolve()
    if not video.is_file():
        raise FileNotFoundError(f"Video not found. Searched path: {video}")

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        cap.release()
        raise RuntimeError(f"Could not determine FPS for video: {video}")

    destination = resolve_label_output_dir(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    exported: list[Path] = []
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    current_sec = 0.0
    try:
        while current_sec * fps < total_frames:
            frame_index = int(round(current_sec * fps))
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
            if not ok:
                break

            label = f"{video.stem} | {current_sec:.1f}s"
            cv2.putText(frame, label, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            frame_path = destination / f"{video.stem}_{current_sec:06.1f}s.jpg"
            cv2.imwrite(str(frame_path), frame)
            exported.append(frame_path)
            current_sec += interval_sec
    finally:
        cap.release()

    return exported


def main() -> None:
    parser = argparse.ArgumentParser(description="Export timestamped frames for ground-truth labelling")
    parser.add_argument("video", help="Input MP4/AVI video path")
    parser.add_argument("--output-dir", default=None, help="Output directory (default: pop/ml/label_frames)")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between exported frames")
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval must be greater than zero")
    frames = export_label_frames(args.video, args.output_dir, args.interval)
    print(f"Exported {len(frames)} frame(s) to {frames[0].parent if frames else Path(args.output_dir).resolve()}")


if __name__ == "__main__":
    main()
