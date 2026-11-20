"""Validate the ULB CSV without third-party dependencies."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

FEATURES = ['Time', *[f'V{i}' for i in range(1, 29)], 'Amount']
COLUMNS = [*FEATURES, 'Class']


def validate(path):
    rows = fraud = duplicates = 0
    seen = {}
    first_time, last_time = math.inf, -math.inf
    with Path(path).open(newline='') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != COLUMNS:
            raise ValueError(f'Expected columns in this order: {COLUMNS}')
        for line, row in enumerate(reader, start=2):
            if None in row or any(value is None or value == '' for value in row.values()):
                raise ValueError(f'Missing or extra fields at line {line}')
            values = tuple(float(row[name]) for name in FEATURES)
            if not all(math.isfinite(value) for value in values):
                raise ValueError(f'Non-finite feature at line {line}')
            if values[0] < 0 or values[-1] < 0 or row['Class'] not in ('0', '1'):
                raise ValueError(f'Invalid time, amount, or label at line {line}')
            label = int(row['Class'])
            if values in seen:
                if seen[values] != label:
                    raise ValueError(f'Conflicting labels for identical features at line {line}')
                duplicates += 1
            seen[values] = label
            rows += 1
            fraud += label
            first_time = min(first_time, values[0])
            last_time = max(last_time, values[0])
    if rows == 0 or fraud == 0 or fraud == rows:
        raise ValueError('Dataset must contain transactions from both classes')
    with Path(path).open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(rows=rows, fraud=fraud, legitimate=rows-fraud,
                fraud_rate=fraud/rows, duplicate_feature_rows=duplicates,
                time_range_seconds=[first_time, last_time], sha256=digest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=Path('data/raw/creditcard.csv'))
    parser.add_argument('--output', type=Path, default=Path('reports/data_validation.json'))
    args = parser.parse_args()
    report = validate(args.data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
