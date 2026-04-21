from fastapi import APIRouter, HTTPException, Query

from backend.models.schemas import MapResponse
from backend.services.map_service import get_map_points

router = APIRouter(prefix='/api/map', tags=['map'])


@router.get('', response_model=MapResponse)
def get_map(variable: str = Query('humidity')):
    if variable not in {'humidity', 'ph', 'ec', 'temp'}:
        raise HTTPException(status_code=400, detail='variable must be one of humidity, ph, ec, temp')
    return {'variable': variable, 'points': get_map_points(variable)}
