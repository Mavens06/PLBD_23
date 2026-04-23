from fastapi import APIRouter
from backend.models.state import ROBOT_STATE
from backend.models.schemas import MissionResponse, RobotStateUpdate
from backend.services.mission_service import get_mission_state

router = APIRouter(prefix='/api/mission', tags=['mission'])

@router.post('/upload')
def upload_mission_state(state: RobotStateUpdate):
    ROBOT_STATE['status'] = state.status
    ROBOT_STATE['active_point'] = state.active_point
    ROBOT_STATE['progress_pct'] = state.progress_pct
    ROBOT_STATE['measured_points'] = state.measured_points
    return {'success': True}

@router.get('', response_model=MissionResponse)
def mission():
    return get_mission_state()
