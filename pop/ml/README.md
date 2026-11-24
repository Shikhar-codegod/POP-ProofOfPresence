# Machine Learning & Evaluation Assets

This directory houses evaluation artifacts, synthetic video generation scripts, and ground truth benchmark datasets for verifying the accuracy of the edge YOLO person detector.

## Files
- `ground_truth_template.csv`: Template schema for manually annotated ground truth counts per second across test video scenarios.
- `generate_test_video.py`: Deterministic synthetic video fixture generator for automated CI and accuracy regression testing.
- `make_label_sheet.py`: Exports timestamped frames for manual ground-truth counting.

## Recording and labeling clips

Mount a phone high in a classroom corner, with the full occupancy area visible and a fixed landscape
orientation. Keep the horizon stable and avoid zoom changes. Suggested scenarios:

- baseline occupied classroom
- trainer movement
- partial or full occlusion
- transient passersby
- lighting variation
- seated and standing occupants

Export frames:

```powershell
pop\edge\.venv\Scripts\python.exe pop\ml\make_label_sheet.py pop\ml\clips\classroom_cctv_360p.mp4 --interval 1
```

Frames are written to `pop/ml/label_frames/` by default and are git-ignored. Open each frame at a known
timestamp, count the people visible in that frame, and add a row to `ground_truth.csv` with
`video_id,timestamp_sec,true_count,scenario,notes`.
