from .chat import router as chat_router
from .map import router as map_router
from .measurements import router as measurements_router
from .mission import router as mission_router
from .recommendations import router as recommendations_router
from .weather import router as weather_router

__all__ = [
    'chat_router',
    'map_router',
    'measurements_router',
    'mission_router',
    'recommendations_router',
    'weather_router',
]
