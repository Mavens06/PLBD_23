from fastapi import APIRouter

from backend.models.schemas import WeatherResponse
from backend.services.weather_service import get_weather

router = APIRouter(prefix='/api/weather', tags=['weather'])


@router.get('', response_model=WeatherResponse)
def weather():
    return get_weather()
