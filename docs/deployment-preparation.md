# Deployment preparation

This project contains two distinct workflows: an anonymized ULB ML benchmark and a **rule-based** ordinary bank statement review. Never market the latter as an ML fraud detector.

## Backend

- Install Python 3.12, then `pip install -e '.[ml]'` and start `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT` (set PORT using your host).
- The `/api/statement/workbook` route works without the trained model. To serve ML predictions, securely provide `models/baseline.joblib` and the corresponding `reports/baseline_metrics.json`. Do not fetch untrusted joblib files.
- Configure `FRAUDLENS_ALLOWED_ORIGINS` as JSON, e.g. `["https://your-frontend.example"]` (replace example). This controls browser CORS, **not** API authentication.
- Use TLS, request limits, rate limiting, and access controls before public availability. The current API is unauthenticated and is not a production fraud-detection service.

## Frontend

- Set `VITE_API_BASE_URL` **at build time** to the backend HTTPS origin, e.g. `https://your-api.example`.
- Build using `cd frontend && npm ci && npm run build`. Publish `frontend/dist/` to a static host.
- If frontend and backend share the same origin and `/api` is reverse-proxied, leave `VITE_API_BASE_URL` empty.
- Local Vite development uses `/api` proxy in `frontend/vite.config.js`.
- Use `frontend/public/sample-statement.xlsx` for a safe public demonstration. Never upload real bank/customer information to an unreviewed public host.

## Tests

`python -m pytest backend/tests/test_health.py backend/tests/test_statements.py ml/tests/test_validate.py` runs without the historical dataset/model.

`cd frontend && npm test && npm run build` checks statement rule regression cases and the build.

Prediction integration tests in `backend/tests/test_predictions.py` require the locally trained model, report, and dataset; the standard CI job intentionally does not claim to test the model.
