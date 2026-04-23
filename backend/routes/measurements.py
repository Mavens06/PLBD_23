from fastapi import APIRouter
from backend.models.state import SENSOR_HISTORY
from backend.models.schemas import Measurement, MeasurementsResponse
from backend.services.sensor_service import get_measurements

router = APIRouter(prefix='/api/measurements', tags=['measurements'])

@router.post('/upload')
def upload_measurement(meas: Measurement):
    meas_dict = meas.model_dump()
    SENSOR_HISTORY.append(meas_dict)
    if len(SENSOR_HISTORY) > 50:
        SENSOR_HISTORY.pop(0)
    return meas

@router.get('', response_model=MeasurementsResponse)
def measurements():
    latest, history = get_measurements()
    return {'latest': latest, 'history': history[-10:]}


@router.get('/latest', response_model=Measurement)
def get_latest_measurement():
    latest, _ = get_measurements()
    return latest
