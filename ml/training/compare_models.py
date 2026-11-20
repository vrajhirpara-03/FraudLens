"""Compare logistic regression and gradient boosting at fixed false-alarm budgets.

Uses training (chronological folds) and validation only. The test partition is
never scored. The deployed baseline artifact and its threshold are read, not changed.
"""
import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from scipy.special import expit
from scipy.stats import binomtest
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ml.data.validate import FEATURES, validate

BUDGETS = [3, 10, 25]
SEED = 42
# Small grid; chosen by mean average precision over chronological training folds.
HGB_GRID = [dict(learning_rate=lr, class_weight=cw) for lr in (0.05, 0.1) for cw in (None, 'balanced')]


def time_cuts(times, fractions):
    """Cut a time-sorted series at row fractions; equal timestamps stay together."""
    return [times.iloc[int(len(times) * f)] for f in fractions]


def split_by_cuts(frame, cuts):
    edges = [-np.inf, *cuts, np.inf]
    return [frame[(frame.Time >= lo) & (frame.Time < hi)] for lo, hi in zip(edges[:-1], edges[1:])]


def make_lr():
    return make_pipeline(StandardScaler(), LogisticRegression(class_weight='balanced', max_iter=2000, random_state=SEED))


def make_hgb(learning_rate, class_weight):
    # Early stopping off: its internal holdout is a random (non-chronological) split.
    return HistGradientBoostingClassifier(learning_rate=learning_rate, class_weight=class_weight, max_iter=300,
                                          max_leaf_nodes=31, min_samples_leaf=20, l2_regularization=1.0,
                                          early_stopping=False, random_state=SEED)


def fit(model, part):
    model.fit(part[FEATURES], part.Class)
    lr = model[-1] if hasattr(model, 'steps') else None
    if lr is not None and lr.n_iter_.max() >= lr.max_iter:
        raise RuntimeError('Logistic regression did not converge')
    return model


def scores(model, part):
    # Log-odds rank identically to probabilities but do not saturate at 1.0,
    # which matters at thresholds like 0.99999.
    return model.decision_function(part[FEATURES])


def best_at_budget(y, s, budget):
    """Lowest cutoff (predict s >= cutoff) whose false alarms stay within budget."""
    order = np.argsort(-s, kind='stable')
    ys, ss = y[order], s[order]
    group_end = np.r_[np.flatnonzero(np.diff(ss) != 0), len(ss) - 1]  # tied scores share a cutoff
    tp = np.cumsum(ys)[group_end]
    fp = group_end + 1 - tp
    ok = np.flatnonzero(fp <= budget)
    if len(ok) == 0:
        return dict(cutoff=np.inf, tp=0, fp=0)
    i = ok[-1]
    return dict(cutoff=float(ss[group_end[i]]), tp=int(tp[i]), fp=int(fp[i]))


def report_at_budget(y, s, budget):
    best = best_at_budget(y, s, budget)
    tp, fp, fraud = best['tp'], best['fp'], int(y.sum())
    ci = binomtest(tp, fraud).proportion_ci(method='wilson') if fraud else None
    return dict(budget=budget, fraud_caught=tp, fraud_missed=fraud - tp, false_alarms=fp,
                precision=tp / (tp + fp) if tp + fp else 0., recall=tp / fraud,
                recall_95ci_wilson=[float(ci.low), float(ci.high)],
                threshold_log_odds=best['cutoff'], threshold_probability=float(expit(best['cutoff'])))


def chronological_folds(train, n_blocks=5):
    """Forward chaining: fit on blocks [0..k-1], evaluate on block k."""
    blocks = split_by_cuts(train, time_cuts(train.Time, [i / n_blocks for i in range(1, n_blocks)]))
    for k in range(1, n_blocks):
        fit_part, eval_part = pd.concat(blocks[:k]), blocks[k]
        if fit_part.Class.nunique() != 2 or eval_part.Class.nunique() != 2:
            raise ValueError(f'Fold {k} lacks both classes')
        yield k, fit_part, eval_part


def paired_bootstrap(y, s_a, s_b, budgets, n_boot, rng):
    """Stratified resampling of validation rows; thresholds re-chosen inside each resample."""
    pos, neg = np.flatnonzero(y == 1), np.flatnonzero(y == 0)
    diffs = {b: [] for b in budgets}
    for _ in range(n_boot):
        idx = np.r_[rng.choice(pos, len(pos)), rng.choice(neg, len(neg))]
        for b in budgets:
            diffs[b].append(best_at_budget(y[idx], s_b[idx], b)['tp'] - best_at_budget(y[idx], s_a[idx], b)['tp'])
    out = {}
    for b, d in diffs.items():
        d = np.array(d)
        out[str(b)] = dict(mean_extra_caught=float(d.mean()), ci95=[float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))],
                           share_resamples_hgb_better=float((d > 0).mean()), share_tied=float((d == 0).mean()))
    return out


def mcnemar(y, s_a, s_b, budget):
    """Exact test on fraud cases caught by exactly one model at its own budget cutoff."""
    fraud = y == 1
    caught_a = s_a >= best_at_budget(y, s_a, budget)['cutoff']
    caught_b = s_b >= best_at_budget(y, s_b, budget)['cutoff']
    only_a, only_b = int((fraud & caught_a & ~caught_b).sum()), int((fraud & caught_b & ~caught_a).sum())
    p = binomtest(min(only_a, only_b), only_a + only_b).pvalue if only_a + only_b else 1.
    return dict(budget=budget, caught_by_both=int((fraud & caught_a & caught_b).sum()),
                only_logistic=only_a, only_hgb=only_b, exact_p_two_sided=float(p))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=Path('data/raw/creditcard.csv'))
    parser.add_argument('--output', type=Path, default=Path('reports/experiments/model_comparison.json'))
    parser.add_argument('--bootstrap', type=int, default=1000)
    args = parser.parse_args()

    identity = validate(args.data)
    artifact = joblib.load('models/baseline.joblib')
    if identity['sha256'] != artifact['dataset_sha256'] or artifact['features'] != FEATURES:
        raise ValueError('Model and dataset identity/schema do not match')
    frame = pd.read_csv(args.data).drop_duplicates(subset=FEATURES).sort_values('Time', kind='stable')
    train, val, _test = split_by_cuts(frame, time_cuts(frame.Time, [.6, .8]))  # _test is never scored
    y_val = val.Class.to_numpy()

    # 1. Chronological folds inside training: pick the HGB config, and see fold-to-fold spread.
    folds = []
    for k, fit_part, eval_part in chronological_folds(train):
        y = eval_part.Class.to_numpy()
        row = dict(fold=k, fit_rows=len(fit_part), fit_fraud=int(fit_part.Class.sum()),
                   eval_rows=len(eval_part), eval_fraud=int(y.sum()), models={})
        candidates = {'logistic': make_lr(), **{f'hgb_{i}': make_hgb(**cfg) for i, cfg in enumerate(HGB_GRID)}}
        for name, model in candidates.items():
            s = scores(fit(model, fit_part), eval_part)
            row['models'][name] = dict(average_precision=float(average_precision_score(y, s)),
                                       caught_at_budget={str(b): best_at_budget(y, s, b)['tp'] for b in BUDGETS})
        folds.append(row)
        print(f'fold {k}: eval fraud={row["eval_fraud"]} ' +
              ' '.join(f'{n}:AP={m["average_precision"]:.3f}' for n, m in row['models'].items()), flush=True)
    mean_ap = {f'hgb_{i}': float(np.mean([f['models'][f'hgb_{i}']['average_precision'] for f in folds]))
               for i in range(len(HGB_GRID))}
    chosen = max(mean_ap, key=mean_ap.get)
    chosen_cfg = HGB_GRID[int(chosen.split('_')[1])]

    # 2. Refit chosen HGB on all training data; score validation once per model.
    hgb = fit(make_hgb(**chosen_cfg), train)
    s_lr = scores(artifact['pipeline'], val)  # deployed baseline, unchanged
    s_hgb = scores(hgb, val)
    deployed_check = (expit(s_lr) >= artifact['threshold'])
    models = {}
    for name, s in [('logistic_regression_deployed', s_lr), ('hist_gradient_boosting', s_hgb)]:
        models[name] = dict(average_precision=float(average_precision_score(y_val, s)),
                            budgets=[report_at_budget(y_val, s, b) for b in BUDGETS])

    report = dict(
        partition='training folds + validation only; test never scored',
        dataset_sha256=identity['sha256'], sklearn_version=sklearn.__version__, seed=SEED,
        validation=dict(rows=len(val), fraud=int(y_val.sum())),
        deployed_threshold_check=dict(threshold=artifact['threshold'], caught=int((deployed_check & (y_val == 1)).sum()),
                                      false_alarms=int((deployed_check & (y_val == 0)).sum())),
        hgb_grid=HGB_GRID, hgb_fold_mean_average_precision=mean_ap, hgb_chosen=chosen_cfg,
        chronological_folds=folds,
        validation_results=models,
        paired_comparison=dict(mcnemar=[mcnemar(y_val, s_lr, s_hgb, b) for b in BUDGETS],
                               bootstrap=paired_bootstrap(y_val, s_lr, s_hgb, BUDGETS, args.bootstrap,
                                                          np.random.default_rng(SEED)),
                               bootstrap_resamples=args.bootstrap),
        notes=['Budget thresholds are chosen and measured on the same validation data, so absolute counts are optimistic '
               'for both models; the paired difference is the fairer signal.',
               'Transaction-level bootstrap ignores time clustering of fraud and likely understates uncertainty.',
               'Experimental budgets, not business requirements. No model saved; deployed artifact untouched.'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    for name, m in models.items():
        print(f'\n{name}  AP={m["average_precision"]:.4f}')
        for r in m['budgets']:
            print(f'  <= {r["budget"]:>2} FA: caught {r["fraud_caught"]}/{r["fraud_caught"] + r["fraud_missed"]}, '
                  f'FA {r["false_alarms"]}, precision {r["precision"]:.2%}, recall {r["recall"]:.2%}, '
                  f'p>={r["threshold_probability"]:.10f} (log-odds {r["threshold_log_odds"]:.3f})')
    print(json.dumps(report['paired_comparison'], indent=2))
    print(f'Wrote {args.output}')


if __name__ == '__main__':
    main()
