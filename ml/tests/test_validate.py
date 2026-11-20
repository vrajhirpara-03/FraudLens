import csv
import pytest
from ml.data.validate import COLUMNS, validate


def write_data(tmp_path, rows):
    path = tmp_path / 'data.csv'
    with path.open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    return path


def test_duplicate_accounting(tmp_path):
    a, b = [0]*30 + [0], [1]*30 + [1]
    report = validate(write_data(tmp_path, [a, a, b]))
    assert report['rows'] == 3
    assert report['fraud'] == 1
    assert report['duplicate_feature_rows'] == 1


def test_conflicting_labels_rejected(tmp_path):
    with pytest.raises(ValueError, match='Conflicting labels'):
        validate(write_data(tmp_path, [[0]*30+[0], [0]*30+[1]]))


def test_nonfinite_rejected(tmp_path):
    with pytest.raises(ValueError, match='Non-finite'):
        validate(write_data(tmp_path, [[float('nan')]*30+[0]]))


def test_schema_rejected(tmp_path):
    path = tmp_path / 'bad.csv'
    path.write_text('Amount,Class\n1,0\n')
    with pytest.raises(ValueError, match='Expected columns'):
        validate(path)
