"""Accuracy evaluation suite for POP edge video analytics against ground truth annotations.

Computes:
- Mean Absolute Error (MAE) for raw and stable counts
- Percentage of observations within +/- 1 person tolerance
- Exact match accuracy percentage
- Per-scenario breakdown (e.g. baseline, trainer movement, occlusion, transient passersby)
- Markdown report table generation
"""

import argparse
import csv
from datetime import datetime, timezone
import logging
import math
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pop.edge.evaluate")


def load_ground_truth(csv_path: str) -> List[Dict[str, Any]]:
    """Load ground truth annotations from CSV."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Ground truth file not found at: {csv_path}")

    records = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                records.append({
                    "video_id": row.get("video_id", "unknown").strip(),
                    "timestamp_sec": float(row["timestamp_sec"]),
                    "true_count": int(row["true_count"]),
                    "scenario": row.get("scenario", "default").strip(),
                    "notes": row.get("notes", "").strip(),
                })
            except (ValueError, KeyError) as exc:
                logger.warning(f"Skipping malformed ground truth row {row}: {exc}")

    logger.info(f"Loaded {len(records)} ground truth samples from '{csv_path}'")
    return records


def load_predictions(csv_path: str) -> List[Dict[str, Any]]:
    """Load edge inference predictions from CSV."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Predictions CSV not found at: {csv_path}")

    records = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                records.append({
                    "timestamp": row.get("timestamp", ""),
                    "video_time_sec": float(row["video_time_sec"]),
                    "raw_count": int(row["raw_count"]),
                    "stable_count": int(row["stable_count"]),
                    "frame_quality": float(row.get("frame_quality", 1.0)),
                })
            except (ValueError, KeyError) as exc:
                logger.warning(f"Skipping malformed prediction row {row}: {exc}")

    logger.info(f"Loaded {len(records)} edge prediction samples from '{csv_path}'")
    return records


def join_by_nearest_timestamp(
    gt_records: List[Dict[str, Any]],
    pred_records: List[Dict[str, Any]],
    max_tolerance_sec: float = 2.0,
    video_id_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Join ground truth annotations with predicted stable counts by nearest video timestamp.

    Args:
        gt_records: List of ground truth dictionaries.
        pred_records: List of prediction dictionaries.
        max_tolerance_sec: Maximum tolerated time difference in seconds for a valid match.
        video_id_filter: Optional video ID to filter ground truth annotations.

    Returns:
        List[Dict[str, Any]]: Array of matched pairs containing ground truth and predicted counts.
    """
    if not pred_records:
        return []

    matched = []
    for gt in gt_records:
        if video_id_filter and gt["video_id"] != video_id_filter:
            continue

        gt_sec = gt["timestamp_sec"]

        # Find nearest prediction by video timeline second
        best_pred = min(pred_records, key=lambda p: abs(p["video_time_sec"] - gt_sec))
        time_diff = abs(best_pred["video_time_sec"] - gt_sec)

        if time_diff <= max_tolerance_sec:
            error_stable = best_pred["stable_count"] - gt["true_count"]
            error_raw = best_pred["raw_count"] - gt["true_count"]
            matched.append({
                "video_id": gt["video_id"],
                "gt_sec": gt_sec,
                "pred_sec": best_pred["video_time_sec"],
                "time_delta": round(time_diff, 2),
                "true_count": gt["true_count"],
                "raw_count": best_pred["raw_count"],
                "stable_count": best_pred["stable_count"],
                "frame_quality": best_pred["frame_quality"],
                "scenario": gt["scenario"],
                "notes": gt["notes"],
                "abs_error_stable": abs(error_stable),
                "abs_error_raw": abs(error_raw),
                "within_plus_minus_one": abs(error_stable) <= 1,
                "exact_match": error_stable == 0,
            })
        else:
            logger.warning(
                f"No prediction found within {max_tolerance_sec}s for GT @ {gt_sec:.1f}s "
                f"(Closest: {best_pred['video_time_sec']:.1f}s, Delta: {time_diff:.2f}s)"
            )

    logger.info(f"Matched {len(matched)} pairs between ground truth and edge predictions.")
    return matched


def compute_metrics(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute aggregated statistical metrics from joined evaluation samples."""
    n = len(samples)
    if n == 0:
        return {
            "total_samples": 0,
            "mae_stable": 0.0,
            "mae_raw": 0.0,
            "pct_within_one": 0.0,
            "pct_exact": 0.0,
            "mean_true": 0.0,
            "mean_stable": 0.0,
        }

    mae_stable = sum(s["abs_error_stable"] for s in samples) / n
    mae_raw = sum(s["abs_error_raw"] for s in samples) / n
    within_one = sum(1 for s in samples if s["within_plus_minus_one"])
    exact = sum(1 for s in samples if s["exact_match"])

    mean_true = sum(s["true_count"] for s in samples) / n
    mean_stable = sum(s["stable_count"] for s in samples) / n

    return {
        "total_samples": n,
        "mae_stable": round(mae_stable, 3),
        "mae_raw": round(mae_raw, 3),
        "pct_within_one": round((within_one / n) * 100.0, 1),
        "pct_exact": round((exact / n) * 100.0, 1),
        "mean_true": round(mean_true, 2),
        "mean_stable": round(mean_stable, 2),
    }


def compute_scenario_breakdown(samples: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Group evaluation records by scenario and compute subset metrics."""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for s in samples:
        sc = s["scenario"]
        groups.setdefault(sc, []).append(s)

    breakdown = {}
    for sc, group_samples in groups.items():
        breakdown[sc] = compute_metrics(group_samples)

    return breakdown


def format_markdown_report(
    overall: Dict[str, Any],
    breakdown: Dict[str, Dict[str, Any]],
    samples: List[Dict[str, Any]],
) -> str:
    """Render comprehensive markdown report table."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        "# POP Edge Analytics — Accuracy Evaluation Report",
        "",
        f"**Generated:** {now_str}  ",
        f"**Evaluated Samples:** {overall['total_samples']}  ",
        "",
        "---",
        "",
        "## 1. Overall Model Performance",
        "",
        "| Metric | Stable Count (Filtered) | Raw Detection | Target Benchmark |",
        "| :--- | :---: | :---: | :---: |",
        f"| **Mean Absolute Error (MAE)** | **{overall['mae_stable']:.2f}** | {overall['mae_raw']:.2f} | $\\le 1.0$ persons |",
        f"| **Accuracy within $\\pm 1$ Person** | **{overall['pct_within_one']:.1f}%** | — | $\\ge 90.0\\%$ |",
        f"| **Exact Match Rate** | **{overall['pct_exact']:.1f}%** | — | — |",
        f"| **Mean Observed Headcount** | {overall['mean_stable']:.2f} | — | True: {overall['mean_true']:.2f} |",
        "",
        "---",
        "",
        "## 2. Per-Scenario Accuracy Breakdown",
        "",
        "| Scenario | Samples | True Mean | Stable Mean | MAE | Within $\\pm 1$ (%) | Status |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for sc, m in sorted(breakdown.items()):
        status_badge = "✅ PASS" if m["mae_stable"] <= 1.0 and m["pct_within_one"] >= 80.0 else "⚠️ REVIEW"
        lines.append(
            f"| `{sc}` | {m['total_samples']} | {m['mean_true']} | "
            f"{m['mean_stable']} | **{m['mae_stable']:.2f}** | {m['pct_within_one']:.1f}% | {status_badge} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 3. Sample-by-Sample Verification Log",
        "",
        "| Video Time | Scenario | Ground Truth | Raw Det | Stable Count | Abs Error | Within $\\pm 1$ | Quality |",
        "| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ])

    for s in samples:
        pass_icon = "✅" if s["within_plus_minus_one"] else "❌"
        lines.append(
            f"| {s['gt_sec']:.1f}s | `{s['scenario']}` | {s['true_count']} | "
            f"{s['raw_count']} | **{s['stable_count']}** | {s['abs_error_stable']} | {pass_icon} | {s['frame_quality']:.2f} |"
        )

    lines.append("")
    return "\n".join(lines)


def evaluate(
    predictions_path: str,
    ground_truth_path: str,
    output_markdown_path: str,
    video_id_filter: Optional[str] = None,
) -> Tuple[Dict[str, Any], str]:
    """Execute evaluation comparison and generate markdown report."""
    gt_records = load_ground_truth(ground_truth_path)
    pred_records = load_predictions(predictions_path)

    matched = join_by_nearest_timestamp(
        gt_records=gt_records,
        pred_records=pred_records,
        video_id_filter=video_id_filter,
    )

    if not matched:
        logger.error("No valid timestamp matches found between predictions and ground truth.")
        sys.exit(1)

    overall = compute_metrics(matched)
    breakdown = compute_scenario_breakdown(matched)
    report_md = format_markdown_report(overall, breakdown, matched)

    os.makedirs(os.path.dirname(os.path.abspath(output_markdown_path)), exist_ok=True)
    with open(output_markdown_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    logger.info(f"Saved evaluation markdown report to: '{output_markdown_path}'")

    # Print summary to console
    print("\n" + "=" * 80)
    print(" POP EDGE EVALUATION BENCHMARK RESULTS")
    print("=" * 80)
    print(f" Samples Evaluated   : {overall['total_samples']}")
    print(f" Stable Count MAE    : {overall['mae_stable']:.2f} persons")
    print(f" Raw Count MAE       : {overall['mae_raw']:.2f} persons")
    print(f" Within +/- 1 Person : {overall['pct_within_one']:.1f}%")
    print(f" Exact Match Rate    : {overall['pct_exact']:.1f}%")
    print("-" * 80)
    print(f" {'SCENARIO':<22} | {'COUNT':<5} | {'TRUE':<5} | {'PRED':<5} | {'MAE':<6} | {'+/-1 (%)':<8}")
    print("-" * 80)
    for sc, m in sorted(breakdown.items()):
        print(f" {sc:<22} | {m['total_samples']:<5} | {m['mean_true']:<5.1f} | {m['mean_stable']:<5.1f} | {m['mae_stable']:<6.2f} | {m['pct_within_one']:<8.1f}%")
    print("=" * 80)
    print(f" Full Report Markdown saved to: {output_markdown_path}\n")

    return overall, report_md


def main() -> None:
    """CLI entrypoint for evaluate.py."""
    parser = argparse.ArgumentParser(description="Evaluate POP Edge Counting Accuracy")
    parser.add_argument("--predictions", default="pop/edge/output/readings.csv", help="Path to predicted readings CSV")
    parser.add_argument("--ground-truth", default="pop/ml/ground_truth_template.csv", help="Path to ground truth CSV")
    parser.add_argument("--output-markdown", default="pop/edge/output/evaluation_report.md", help="Destination markdown path")
    parser.add_argument("--video-id", default=None, help="Filter ground truth by video ID (e.g. sample_classroom_01)")

    args = parser.parse_args()
    evaluate(
        predictions_path=args.predictions,
        ground_truth_path=args.ground_truth,
        output_markdown_path=args.output_markdown,
        video_id_filter=args.video_id,
    )


if __name__ == "__main__":
    main()
