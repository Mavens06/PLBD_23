from fastapi import APIRouter

from backend.models.schemas import MeasurementsResponse
from backend.services.sensor_service import get_measurements

router = APIRouter(prefix='/api/measurements', tags=['measurements'])


@router.get('', response_model=MeasurementsResponse)
def measurements():
    latest, history = get_measurements()
    return {'latest': latest, 'history': history[-10:]}
