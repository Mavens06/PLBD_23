from raspberry_pi.robot.mission_controller import MissionController
from raspberry_pi.sensors.acquisition_manager import AcquisitionManager
from raspberry_pi.storage.session_logger import SessionLogger
import requests
import time
from datetime import datetime, timezone

BACKEND_URL_MEASURE = "http://127.0.0.1:8000/api/measurements/upload"
BACKEND_URL_MISSION = "http://127.0.0.1:8000/api/mission/upload"

def send_mission_update(status, point, progress, measured):
    try:
        requests.post(BACKEND_URL_MISSION, json={
            'status': status,
            'active_point': point,
            'progress_pct': progress,
            'measured_points': measured
        }, timeout=5)
    except Exception as e:
        print(f"Failed to post mission update: {e}")

def run_mission():
    mission = MissionController()
    acquisition = AcquisitionManager(stabilization_seconds=3)
    logger = SessionLogger()
    
    print("=== STARTING ROBOT MISSION ===")
    send_mission_update('Démarrage', mission.current_point(), 0, 0)
    
    # Simulate autonomous movement code parsing
    time.sleep(1)
    
    points_measured = 0
    total = mission.total_points
    
    # Go to first point
    first_point = mission.current_point()
    mission.motors.move_to(first_point)

    while not mission.is_finished():
        point = mission.current_point()
        pct = int((points_measured / total) * 100)
        
        print(f"\n--- Point {point} ---")
        send_mission_update('En transit / Mesure', point, pct, points_measured)
        
        # Lower arm
        mission.motors.lower_arm()
        
        # Read sensors (wait inside for stabilization)
        print(f"[SENSOR] Acquiring data at {point} (stabilization of {acquisition.stabilization_seconds}s)")
        raw_measurement = acquisition.acquire(point)
        logger.log(point=point, measurement=raw_measurement)
        
        # Bring arm up
        mission.motors.raise_arm()
        
        points_measured += 1
        pct = int((points_measured / total) * 100)
        
        # Flatten and send to backend
        flat_data = {
            'humidity': raw_measurement['humidity']['value'],
            'ph': raw_measurement['ph']['value'],
            'ec': raw_measurement['ec']['value'],
            'temp': raw_measurement['temp']['value'],
            'quality': 'good' if raw_measurement['humidity']['value'] > 40 else 'warning',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        try:
            requests.post(BACKEND_URL_MEASURE, json=flat_data, timeout=5)
            print(f"[NETWORK] Sent sensors datav to backend for point {point}")
        except Exception as e:
            print(f"[NETWORK ERROR] Failed to send data to backend: {e}")

        send_mission_update('Traitement ML terminé', point, pct, points_measured)

        # Go to next if not finished
        if points_measured < total:
            print("[MISSION] Going to next point...")
            mission.advance()
        else:
            break
            
    print("\n=== MISSION COMPLETE ===")
    send_mission_update('Terminé', point, 100, points_measured)
    return "OK"

if __name__ == '__main__':
    run_mission()
