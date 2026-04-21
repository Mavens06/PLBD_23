from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Measurement(BaseModel):
    humidity: float = Field(..., description='Soil humidity in %')
    ph: float = Field(..., description='Soil pH value')
    ec: float = Field(..., description='Electrical conductivity in mS/cm')
    temp: float = Field(..., description='Soil temperature in °C')
    timestamp: datetime
    quality: Literal['good', 'warning', 'critical'] = 'good'


class RobotState(BaseModel):
    status: str
    mission: str
    active_point: str
    progress_pct: int


class MissionResponse(BaseModel):
    robot: RobotState
    total_points: int
    measured_points: int


class MeasurementsResponse(BaseModel):
    latest: Measurement
    history: List[Measurement]


class MapResponse(BaseModel):
    variable: Literal['humidity', 'ph', 'ec', 'temp']
    points: List[Dict[str, object]]


class RecommendationItem(BaseModel):
    title: str
    detail: str
    priority: Literal['high', 'medium', 'low']


class RecommendationsResponse(BaseModel):
    actions: List[RecommendationItem]
    crops: List[str]


class WeatherResponse(BaseModel):
    temperature_c: float
    humidity_pct: float
    wind_kmh: float
    rain_mm_next_24h: float


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    message: str
    language: Literal['fr', 'ar', 'da'] = 'fr'
    sensor_data: Optional[Dict[str, float]] = None
    robot_state: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
