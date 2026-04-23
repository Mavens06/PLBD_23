from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import requests

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from raspberry_pi.robot.mission_controller import MissionController
from raspberry_pi.sensors.acquisition_manager import AcquisitionManager
from raspberry_pi.storage.session_logger import SessionLogger

BACKEND_API = os.getenv('BACKEND_API', 'http://127.0.0.1:8000/api').rstrip('/')
MEASUREMENTS_UPLOAD_URL = f'{BACKEND_API}/measurements/upload'
MISSION_UPLOAD_URL = f'{BACKEND_API}/mission/upload'
MISSION_START_URL = f'{BACKEND_API}/mission/start'
MISSION_END_URL = f'{BACKEND_API}/mission/end'
RECOMMEND_URL = f'{BACKEND_API}/recommend'


def load_scenario(scenario_file: str | None) -> dict:
    if not scenario_file:
        return {}
    try:
        with open(scenario_file, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError('Scenario JSON must be an object')
        return data
    except Exception as exc:
        print(f'[SCENARIO] Invalid scenario file {scenario_file}: {exc}')
        return {}


def parse_points(raw_points: str | None) -> list[str] | None:
    if not raw_points:
        return None
    points = [point.strip().upper() for point in raw_points.split(',') if point.strip()]
    return points or None


def post_json(url: str, payload: dict) -> dict | None:
    try:
        resp = requests.post(url, json=payload, timeout=5)
        if resp.ok:
            return resp.json() if resp.content else {}
        print(f'[NETWORK ERROR] POST {url} failed ({resp.status_code}): {resp.text}')
    except requests.RequestException as exc:
        print(f'[NETWORK ERROR] POST {url} failed: {exc}')
    return None


def send_mission_update(status: str, active_point: str, progress_pct: int, measured_points: int) -> None:
    post_json(
        MISSION_UPLOAD_URL,
        {
            'status': status,
            'active_point': active_point,
            'progress_pct': progress_pct,
            'measured_points': measured_points,
        },
    )


def send_measurement(raw_measurement: dict) -> dict:
    flat_data = {
        'humidity': raw_measurement['humidity']['value'],
        'ph': raw_measurement['ph']['value'],
        'ec': raw_measurement['ec']['value'],
        'temp': raw_measurement['temp']['value'],
        'quality': 'good' if raw_measurement['humidity']['value'] >= 40 else 'warning',
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }
    post_json(MEASUREMENTS_UPLOAD_URL, flat_data)
    return flat_data


def run_decision_pipeline(measurement_payload: dict) -> None:
    recommendation = post_json(RECOMMEND_URL, measurement_payload) or {}
    result = recommendation.get('recommendation', {})
    top_crops = [item.get('name') for item in result.get('top_crops', []) if isinstance(item, dict)]
    if top_crops:
        print(f"[DECISION] Top cultures recommandees: {', '.join(top_crops[:3])}")
    else:
        print('[DECISION] Recommandation traitee (aucune culture explicite retournee).')


def run_mission(
    points: list[str] | None = None,
    stabilization_seconds: int = 3,
    read_count: int = 10,
    mission_name: str = 'Simulation autonome',
):
    mission = MissionController(route_points=points)
    acquisition = AcquisitionManager(stabilization_seconds=stabilization_seconds, read_count=read_count)
    logger = SessionLogger()

    total_points = mission.total_points
    if total_points <= 0:
        print('[MISSION] Aucun point configure.')
        return 'NO_POINTS'

    print(f'=== STARTING ROBOT MISSION: {mission_name} ({total_points} points) ===')
    post_json(MISSION_START_URL, {})

    first_point = mission.current_point()
    mission.motors.move_to(first_point)
    points_measured = 0

    while points_measured < total_points:
        point = mission.current_point()
        progress_pct = int((points_measured / total_points) * 100)
        print(f'\n--- Point {point} ---')
        send_mission_update(f'En transit / Mesure ({mission_name})', point, progress_pct, points_measured)

        mission.motors.lower_arm()
        print(f'[SENSOR] Stabilisation ({acquisition.stabilization_seconds}s) and acquisition at {point}')
        raw_measurement = acquisition.acquire(point)
        logger.log(point=point, measurement=raw_measurement)
        mission.motors.raise_arm()

        measurement_payload = send_measurement(raw_measurement)
        run_decision_pipeline(measurement_payload)

        points_measured += 1
        progress_pct = int((points_measured / total_points) * 100)
        send_mission_update(f'Traitement decision termine ({mission_name})', point, progress_pct, points_measured)

        if points_measured < total_points:
            print('[MISSION] Going to next point...')
            mission.advance()
        else:
            break

    send_mission_update('Termine', mission.current_point(), 100, points_measured)
    post_json(MISSION_END_URL, {})
    print('=== MISSION COMPLETE ===')
    return 'OK'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Agri-Botics mission simulator')
    parser.add_argument(
        '--points',
        type=str,
        default=None,
        help='Comma separated mission points (example: A1,B2,C3)',
    )
    parser.add_argument(
        '--stabilization',
        type=int,
        default=3,
        help='Stabilization seconds before acquisition (3-5)',
    )
    parser.add_argument(
        '--read-count',
        type=int,
        default=10,
        help='Number of reads per sensor point (min 10)',
    )
    parser.add_argument(
        '--scenario-file',
        type=str,
        default=None,
        help='Path to scenario JSON file',
    )
    args = parser.parse_args()

    scenario = load_scenario(args.scenario_file)
    scenario_points = scenario.get('points') if isinstance(scenario.get('points'), list) else None
    route_points = parse_points(args.points) or scenario_points
    scenario_stabilization = int(scenario.get('stabilization_seconds', args.stabilization))
    scenario_read_count = int(scenario.get('read_count', args.read_count))
    mission_name = str(scenario.get('mission_name', 'Simulation autonome'))

    run_mission(
        points=route_points,
        stabilization_seconds=scenario_stabilization,
        read_count=scenario_read_count,
        mission_name=mission_name,
    )