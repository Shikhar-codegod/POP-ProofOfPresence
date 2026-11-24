"""Tests for synthetic test-video output path resolution."""

from pathlib import Path

from generate_test_video import resolve_output_path


def test_default_output_is_script_relative(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    expected = Path(__file__).resolve().parent / "sample_classroom.mp4"
    assert resolve_output_path() == expected
