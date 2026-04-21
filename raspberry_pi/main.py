from raspberry_pi.robot.mission_controller import MissionController
from raspberry_pi.sensors.acquisition_manager import AcquisitionManager
from raspberry_pi.storage.session_logger import SessionLogger


def run_once():
    mission = MissionController()
    acquisition = AcquisitionManager()
    logger = SessionLogger()

    point = mission.current_point()
    measurement = acquisition.acquire(point)
    logger.log(point=point, measurement=measurement)
    return {'point': point, 'measurement': measurement}


if __name__ == '__main__':
    print(run_once())
