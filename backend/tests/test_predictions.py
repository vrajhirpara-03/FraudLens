import csv
import io
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from ml.data.validate import FEATURES
from backend.app.api.predictions import MAX_BYTES, MAX_ROWS

@pytest.fixture
def client():
    with TestClient(app) as client:
        assert client.get('/api/health').json()['model_status'] == 'ready'
        yield client


def test_single_and_csv_match(client):
    with open('data/raw/creditcard.csv') as stream:
        row = next(csv.DictReader(stream))
    row.pop('Class')
    transaction = {key: float(value) for key, value in row.items()}
    single = client.post('/api/predict', json=transaction)
    assert single.status_code == 200
    body = io.StringIO()
    writer = csv.DictWriter(body, fieldnames=FEATURES)
    writer.writeheader()
    writer.writerow(row)
    batch = client.post('/api/predict/csv', content=body.getvalue(), headers={'Content-Type': 'text/csv'})
    assert batch.status_code == 200
    assert single.json() == batch.json()
    result = single.json()
    assert result['results'][0]['flagged_for_review'] == (result['results'][0]['model_score'] >= result['threshold'])


def test_bad_input(client):
    assert client.post('/api/predict', json={'Amount': -1}).status_code == 422
    assert client.post('/api/predict/csv', content='Amount\n1', headers={'Content-Type':'text/csv'}).status_code == 422
    assert client.post('/api/predict/csv', content='x').status_code == 415
    assert client.post('/api/predict/csv', content='x'*1000001, headers={'Content-Type':'text/csv'}).status_code == 422


def test_unavailable_model(client):
    client.app.state.model.status = 'unavailable'
    assert client.get('/api/model').status_code == 503


def test_model_metrics(client):
    response = client.get('/api/model')
    assert response.status_code == 200
    assert response.json()['features'] == FEATURES

def test_new_upload_limits():
    assert MAX_BYTES == 200_000_000
    assert MAX_ROWS == 300_000
