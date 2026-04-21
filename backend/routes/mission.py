from fastapi import APIRouter

from backend.models.schemas import MissionResponse
from backend.services.mission_service import get_mission_state

router = APIRouter(prefix='/api/mission', tags=['mission'])


@router.get('', response_model=MissionResponse)
def mission():
    return get_mission_state()
