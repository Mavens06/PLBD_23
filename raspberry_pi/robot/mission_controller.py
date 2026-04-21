from raspberry_pi.robot.motors import MotorDriver
from raspberry_pi.robot.navigation import next_point
from raspberry_pi.robot.safety import check_safety


class MissionController:
    def __init__(self):
        self._idx = 0
        self._motors = MotorDriver()

    def current_point(self) -> str:
        return next_point(self._idx)

    def advance(self) -> str:
        if not check_safety():
            raise RuntimeError('Safety condition not met')
        self._idx += 1
        target = next_point(self._idx)
        self._motors.move_to(target)
        return target
