from fastapi import APIRouter
from backend.services.inference_service import get_crop_recommendation

router = APIRouter(prefix="/api/recommend", tags=["recommendations"])

@router.post("")
async def recommend(measurements: dict):
    # On récupère les 4 capteurs + météo
    result = get_crop_recommendation(measurements)
    return {"recommendation": result, "status": "success"}