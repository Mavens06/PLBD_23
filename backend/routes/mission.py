from fastapi import APIRouter

from backend.models.schemas import MissionResponse, RobotStateUpdate
from backend.models.state import ROBOT_STATE
from backend.services.mission_service import get_mission_state

router = APIRouter(prefix='/api/mission', tags=['mission'])


@router.post('/upload')
def upload_mission_state(state: RobotStateUpdate):
    ROBOT_STATE['status'] = state.status
    ROBOT_STATE['active_point'] = state.active_point
    ROBOT_STATE['progress_pct'] = state.progress_pct
    ROBOT_STATE['measured_points'] = state.measured_points
    ROBOT_STATE['mission_active'] = state.status not in ('Termine', 'Terminee', 'Terminé', 'Terminée', 'Idle')
    return {'success': True}


@router.get('', response_model=MissionResponse)
def mission():
    return get_mission_state()


@router.post('/start')
def start_mission():
    ROBOT_STATE['mission_active'] = True
    ROBOT_STATE['status'] = 'Demarrage'
    ROBOT_STATE['progress_pct'] = 0
    ROBOT_STATE['measured_points'] = 0
    ROBOT_STATE['active_point'] = ROBOT_STATE.get('active_point', 'A1')
    return {'status': 'started'}


@router.post('/end')
def end_mission():
    ROBOT_STATE['mission_active'] = False
    ROBOT_STATE['status'] = 'Termine'
    ROBOT_STATE['progress_pct'] = 100
    return {'status': 'ended'}


@router.get('/status')
def get_status():
    return {
        'active': bool(ROBOT_STATE.get('mission_active', False)),
        'status': ROBOT_STATE.get('status', 'Idle'),
        'current_point': ROBOT_STATE.get('active_point'),
        'progress_pct': int(ROBOT_STATE.get('progress_pct', 0)),
        'measured_points': int(ROBOT_STATE.get('measured_points', 0)),
        'total_points': int(ROBOT_STATE.get('total_points', 0)),
    }
