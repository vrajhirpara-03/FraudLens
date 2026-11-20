from fastapi import APIRouter, Request

router = APIRouter()


@router.get('/health')
def health(request: Request):
    service = getattr(request.app.state, 'model', None)
    return {'status': 'ok', 'service': 'FraudLens', 'model_status': service.status if service else 'unavailable'}
