"""Train and evaluate a chronological logistic regression baseline."""
import argparse
import json
from pathlib import Path

from ml.data.validate import FEATURES, validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=Path('data/raw/creditcard.csv'))
    parser.add_argument('--output', type=Path, default=Path('reports/baseline_metrics.json'))
    args = parser.parse_args()
    validation = validate(args.data)
    import joblib
    import numpy as np
    import pandas as pd
    import sklearn
    from sklearn.dummy import DummyClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score, confusion_matrix, precision_recall_curve, precision_score, recall_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    frame = pd.read_csv(args.data).drop_duplicates(subset=FEATURES).sort_values('Time', kind='stable')
    # Keep equal timestamps together at partition boundaries.
    times = frame.Time
    cut1, cut2 = times.iloc[int(len(frame)*.6)], times.iloc[int(len(frame)*.8)]
    partitions = [frame[times < cut1], frame[(times >= cut1) & (times < cut2)], frame[times >= cut2]]
    if any(part.Class.nunique() != 2 for part in partitions):
        raise ValueError('Each chronological partition must contain both classes')
    train, val, test = partitions
    model = make_pipeline(StandardScaler(), LogisticRegression(class_weight='balanced', max_iter=2000, random_state=42))
    model.fit(train[FEATURES], train.Class)
    if model[-1].n_iter_.max() >= 2000:
        raise RuntimeError('Optimizer did not converge; baseline not saved')
    val_scores = model.predict_proba(val[FEATURES])[:, 1]
    precision, recall, thresholds = precision_recall_curve(val.Class, val_scores)
    f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-15)
    threshold = float(thresholds[np.argmax(f1)])

    def metrics(part, scores, cutoff):
        predictions = scores >= cutoff
        tn, fp, fn, tp = confusion_matrix(part.Class, predictions, labels=[0, 1]).ravel()
        return dict(average_precision=float(average_precision_score(part.Class, scores)),
                    precision=float(precision_score(part.Class, predictions, zero_division=0)),
                    recall=float(recall_score(part.Class, predictions, zero_division=0)),
                    false_positive_rate=float(fp/(fp+tn)),
                    alerts_per_1000=float(predictions.mean()*1000),
                    confusion_matrix={'tn':int(tn), 'fp':int(fp), 'fn':int(fn), 'tp':int(tp)})

    dummy = DummyClassifier(strategy='prior').fit(train[FEATURES], train.Class)
    report = dict(dataset=validation, sklearn_version=sklearn.__version__, seed=42,
                  split_method='chronological 60/20/20; identical timestamps kept together; duplicate features removed',
                  splits={name:dict(rows=len(part), fraud=int(part.Class.sum()), time_min=float(part.Time.min()), time_max=float(part.Time.max())) for name, part in zip(['train','validation','test'], partitions)},
                  threshold=threshold, threshold_selection='maximum F1 on validation only; not a business cost optimum',
                  validation=metrics(val, val_scores, threshold),
                  test=metrics(test, model.predict_proba(test[FEATURES])[:,1], threshold),
                  dummy_test=metrics(test, dummy.predict_proba(test[FEATURES])[:,1], .5),
                  limitations=['Two-day anonymized historical benchmark; no production generalization claim.', 'Upstream PCA provenance cannot be revalidated from this CSV.', 'No customer identifiers: customer-level split isolation cannot be verified.'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    Path('models').mkdir(exist_ok=True)
    joblib.dump(dict(pipeline=model, features=FEATURES, threshold=threshold, dataset_sha256=validation['sha256']), 'models/baseline.joblib')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
