from backend.models.state import ROBOT_STATE


def get_mission_state():
    return {
        'robot': {
            'status': ROBOT_STATE['status'],
            'mission': ROBOT_STATE['mission'],
            'active_point': ROBOT_STATE['active_point'],
            'progress_pct': ROBOT_STATE['progress_pct'],
        },
        'total_points': ROBOT_STATE['total_points'],
        'measured_points': ROBOT_STATE['measured_points'],
    }
