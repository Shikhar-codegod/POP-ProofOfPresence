# POP Phase 1 Accuracy Baseline

**MAE: PENDING - human ground-truth labelling required**

**Percentage within +/-1: PENDING - human ground-truth labelling required**

No ground-truth counts have been guessed or calculated from detector output. Fill
`pop/ml/ground_truth.csv` with manually observed counts before running the evaluator.

## Run settings

| Setting | MAE | % within +/-1 | Notes |
|---|---:|---:|---|
| Default | PENDING | PENDING | |
| imgsz 960 | PENDING | PENDING | |
| conf 0.15 | PENDING | PENDING | |

## Per-scenario table

| Scenario | Samples | MAE | % within +/-1 | Failure notes |
|---|---:|---:|---:|---|
| baseline | PENDING | PENDING | PENDING | |
| trainer movement | PENDING | PENDING | PENDING | |
| partial occlusion | PENDING | PENDING | PENDING | |
| transient passersby | PENDING | PENDING | PENDING | |
| lighting variation | PENDING | PENDING | PENDING | |

## Evaluation command

```powershell
pop\edge\.venv\Scripts\python.exe pop\edge\evaluate.py `
  --predictions pop\edge\output\readings.csv `
  --ground-truth pop\ml\ground_truth.csv
```
