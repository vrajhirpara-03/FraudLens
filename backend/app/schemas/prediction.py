from pydantic import ConfigDict, Field, FiniteFloat, create_model
from ml.data.validate import FEATURES

Transaction = create_model(
    'Transaction', __config__=ConfigDict(extra='forbid'),
    **{name: (FiniteFloat, Field(ge=0) if name in ('Time', 'Amount') else Field()) for name in FEATURES},
)
