# Architecture and milestones

The React dashboard calls the FastAPI backend. At startup, the backend loads the preprocessing and model pipeline trained offline by `ml/training/train.py`. Training never runs inside a prediction request.

```
data/raw/creditcard.csv ──► ml/data/validate.py ──► ml/training/train.py ──► models/baseline.joblib
                                                            │                        │
                                                            ▼                        ▼
                                                 reports/*.json  ◄────── backend/app (FastAPI) ◄── frontend (React)
```

The statement review is separate from the model. The backend reads the `.xlsx` cell values, and the browser applies simple rules (possible duplicates, debits at least five times the sheet median).

## Milestone 1 — Foundation (done)

Dashboard, health endpoint, explicit untrained status, configurable local CORS, backend tests, and setup documentation.

## Milestone 2 — Data and baseline (done)

ULB dataset validated (schema, finite values, conflicting duplicate labels) and fingerprinted with SHA-256. 1,081 exact duplicates removed. Chronological 60/20/20 split with equal timestamps kept together. Dummy and logistic regression baselines, with the scaler fitted on training data only.

## Milestone 3 — Evaluation (done)

Threshold chosen on validation (maximum F1) and test evaluated once. Precision, recall, average precision, confusion matrix, and alert rate reported. Validation-only experiments:
- `compare_thresholds.py`: recall targets versus false-alarm cost.
- `compare_models.py`: gradient boosting versus logistic regression at 3, 10 and 25 false alarms, using chronological training folds and paired significance checks. No improvement found; baseline kept.

## Milestone 4 — Inference (done)

Validated single and batch scoring, trusted local artifact loading, model metadata, CSV size and row limits, dashboard results, and Excel statement review. Uploaded serialized models are never accepted.

## Milestone 5 — Portfolio release (in progress)

Done: README with measured results and limitations, license. Remaining: screenshots, pinned dependency versions, model card, deployment configuration.
