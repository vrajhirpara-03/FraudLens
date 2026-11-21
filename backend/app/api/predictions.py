import csv
import io
from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError
from backend.app.schemas.prediction import Transaction
from ml.data.validate import FEATURES

router = APIRouter()
MAX_BYTES = 200_000_000
MAX_ROWS = 300_000


def ready(request):
    service = request.app.state.model
    if service.status != 'ready':
        raise HTTPException(503, 'Model unavailable. Check backend startup logs.')
    return service


@router.get('/model')
def model_info(request: Request):
    service = ready(request)
    return {'status': service.status, 'features': FEATURES, 'report': service.report,
            'score_note': 'Uncalibrated model score, not a verified fraud probability.'}


@router.post('/predict')
def predict(transaction: Transaction, request: Request):
    return ready(request).predict([transaction.model_dump()])


@router.post('/predict/csv')
async def predict_csv(request: Request):
    service = ready(request)
    if request.headers.get('content-type', '').split(';')[0] != 'text/csv':
        raise HTTPException(415, 'Send the CSV as text/csv.')
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BYTES:
            raise HTTPException(413, 'CSV must be at most 1 MB.')
    try:
        reader = csv.DictReader(io.StringIO(body.decode('utf-8-sig')), strict=True)
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)) or set(headers) not in (set(FEATURES), set(FEATURES + ['Class'])):
            raise ValueError('CSV must have Time, V1–V28, Amount, and optional Class; no extra columns.')
        rows = []
        for number, row in enumerate(reader, 1):
            if number > MAX_ROWS:
                raise HTTPException(413, 'CSV must contain at most 1,000 transactions.')
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f'Wrong number of fields in transaction {number}.')
            if 'Class' in row and row.pop('Class') not in ('0', '1'):
                raise ValueError(f'Invalid optional Class in transaction {number}.')
            try:
                rows.append(Transaction.model_validate(row).model_dump())
            except ValidationError:
                raise ValueError(f'Transaction {number} requires finite numeric features and nonnegative Time and Amount.')
        if not rows:
            raise ValueError('CSV has no transactions.')
    except (UnicodeError, csv.Error, ValueError) as error:
        raise HTTPException(422, str(error)) from error
    return service.predict(rows)
