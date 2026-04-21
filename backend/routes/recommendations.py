from fastapi import APIRouter

from backend.models.schemas import RecommendationsResponse
from backend.services.recommendation_service import get_recommendations

router = APIRouter(prefix='/api/recommendations', tags=['recommendations'])


@router.get('', response_model=RecommendationsResponse)
def recommendations():
    return get_recommendations()
