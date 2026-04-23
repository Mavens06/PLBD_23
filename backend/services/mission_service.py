from backend.models.state import ROBOT_STATE

def get_mission_state():
    return {
        'robot': {
            'status': ROBOT_STATE.get('status', 'Actif'),
            'mission': ROBOT_STATE.get('mission', 'Cartographie'),
            'active_point': ROBOT_STATE.get('active_point', 'A1'),
            'progress_pct': ROBOT_STATE.get('progress_pct', 0),
        },
        'total_points': ROBOT_STATE.get('total_points', 9),
        'measured_points': ROBOT_STATE.get('measured_points', 0),
    }
