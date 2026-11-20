"""Load only the trusted, locally trained artifact at startup."""
import json
import math
from pathlib import Path

from ml.data.validate import FEATURES

ROOT = Path(__file__).resolve().parents[3]


class ModelService:
    def __init__(self):
        self.artifact = None
        self.report = None
        self.status = 'unavailable'

    def load(self):
        try:
            import joblib
            artifact = joblib.load(ROOT / 'models/baseline.joblib')
            report = json.loads((ROOT / 'reports/baseline_metrics.json').read_text())
            if artifact['features'] != FEATURES:
                raise ValueError('Feature schema mismatch')
            if artifact['dataset_sha256'] != report['dataset']['sha256']:
                raise ValueError('Dataset identity mismatch')
            threshold = artifact['threshold']
            if not math.isfinite(threshold) or not 0 <= threshold <= 1 or threshold != report['threshold']:
                raise ValueError('Threshold mismatch')
            if list(artifact['pipeline'].feature_names_in_) != FEATURES:
                raise ValueError('Pipeline schema mismatch')
            self.artifact, self.report, self.status = artifact, report, 'ready'
        except Exception:
            import logging
            logging.getLogger(__name__).exception('Model unavailable; check local artifact and dependencies')
            self.artifact, self.report, self.status = None, None, 'unavailable'

    def predict(self, rows):
        import pandas as pd
        scores = self.artifact['pipeline'].predict_proba(pd.DataFrame(rows, columns=FEATURES))[:, 1]
        threshold = self.artifact['threshold']
        return {'threshold': threshold, 'score_note': 'Uncalibrated model score, not a verified fraud probability.',
                'results': [{'row': i+1, 'model_score': float(score), 'flagged_for_review': bool(score >= threshold)}
                            for i, score in enumerate(scores)]}
