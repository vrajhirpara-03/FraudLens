"""Compare recall targets on validation only; do not alter deployed artifacts."""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, precision_recall_curve

from ml.data.validate import FEATURES, validate


def main():
    identity = validate('data/raw/creditcard.csv')
    artifact = joblib.load('models/baseline.joblib')
    if identity['sha256'] != artifact['dataset_sha256'] or artifact['features'] != FEATURES:
        raise ValueError('Model and dataset identity/schema do not match')
    frame = pd.read_csv('data/raw/creditcard.csv').drop_duplicates(subset=FEATURES).sort_values('Time', kind='stable')
    cut1 = frame.Time.iloc[int(len(frame)*.6)]
    cut2 = frame.Time.iloc[int(len(frame)*.8)]
    val = frame[(frame.Time >= cut1) & (frame.Time < cut2)]
    scores = artifact['pipeline'].predict_proba(val[FEATURES])[:, 1]
    precision, recall, thresholds = precision_recall_curve(val.Class, scores)

    def measure(label, threshold):
        tn, fp, fn, tp = confusion_matrix(val.Class, scores >= threshold, labels=[0, 1]).ravel()
        return dict(policy=label, threshold=float(threshold), recall=float(tp/(tp+fn)),
                    precision=float(tp/(tp+fp)) if tp+fp else 0.,
                    detected=int(tp), missed=int(fn), false_alarms=int(fp),
                    alerts=int(tp+fp), alerts_per_1000=float((tp+fp)/len(val)*1000))

    rows = [measure('Saved F1 baseline', artifact['threshold'])]
    for target in [.8, .9, .95]:
        eligible = np.flatnonzero(recall[:-1] >= target)
        # Highest cutoff meeting target minimizes alerts for this fixed model.
        threshold = thresholds[eligible[-1]]
        rows.append(measure(f'At least {target:.0%} validation recall', threshold))
    report = dict(partition='validation only', rows=len(val), fraud=int(val.Class.sum()),
                  dataset_sha256=identity['sha256'], comparison=rows,
                  note='Exploratory validation estimates, not guarantees. No test predictions computed. Saved model and threshold unchanged.')
    Path('reports/threshold_comparison.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
