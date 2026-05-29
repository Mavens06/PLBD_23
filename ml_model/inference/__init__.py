"""
Compat shim — CLAUDE.md mentionne ml_model.inference.predict.
On expose les mêmes symboles que ml_model.predict pour rester compatible.
"""
from ..predict import predict_top_crops, explain  # noqa: F401
