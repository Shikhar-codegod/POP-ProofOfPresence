"""Tests for edge configuration path resolution."""

from pathlib import Path

import pytest
import yaml
from run_edge import (
    DEFAULT_CONFIG_PATH,
    deep_merge,
    load_config,
    run_pipeline,
)


def test_default_config_is_script_relative() -> None:
    assert DEFAULT_CONFIG_PATH == Path(__file__).resolve().parents[1] / "config.yaml"


def test_relative_config_paths_resolve_from_config_directory(tmp_path: Path) -> None:
    config_dir = tmp_path / "edge"
    config_dir.mkdir()
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        yaml.safe_dump({
            "detection": {"model_path": "weights/yolo.pt"},
            "sampling": {"video_path": "../ml/test.mp4"},
            "output": {
                "csv_path": "output/readings.csv",
                "plot_path": "output/count_timeline.png",
                "annotated_video_path": "output/annotated.mp4",
            },
        }),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config["detection"]["model_path"] == str(config_dir / "weights/yolo.pt")
    assert config["sampling"]["video_path"] == str((config_dir / "../ml/test.mp4").resolve())
    assert config["output"]["csv_path"] == str(config_dir / "output/readings.csv")


def test_local_config_overrides_and_device_key_environment_takes_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_dir = tmp_path / "edge"
    config_dir.mkdir()
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        yaml.safe_dump({
            "backend": {"device_key": "file-key", "centre_id": "base-centre"},
        }),
        encoding="utf-8",
    )
    (config_dir / "config.local.yaml").write_text(
        yaml.safe_dump({"backend": {"centre_id": "local-centre"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("POP_DEVICE_KEY", "environment-key")

    config = load_config(config_path)

    assert config["backend"]["device_key"] == "environment-key"
    assert config["backend"]["centre_id"] == "local-centre"


def test_missing_config_lists_searched_path(tmp_path: Path) -> None:
    missing = tmp_path / "missing.yaml"

    with pytest.raises(FileNotFoundError, match="Searched path") as exc_info:
        load_config(missing)

    assert str(missing) in str(exc_info.value)


def test_deep_merge() -> None:
    assert deep_merge(
        {"backend": {"device_key": "a", "centre_id": "b"}},
        {"backend": {"device_key": "c"}},
    ) == {"backend": {"device_key": "c", "centre_id": "b"}}


def test_missing_video_error_lists_absolute_path_and_generate_command(tmp_path: Path) -> None:
    config_dir = tmp_path / "edge"
    config_dir.mkdir()
    missing_video = tmp_path / "missing.mp4"
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        yaml.safe_dump({
            "sampling": {"video_path": str(missing_video)},
            "detection": {"model_path": "yolo11n.pt"},
        }),
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError) as exc_info:
        run_pipeline(config_path=config_path, no_post=True)

    message = str(exc_info.value)
    assert str(missing_video) in message
    assert "generate_test_video.py" in message
