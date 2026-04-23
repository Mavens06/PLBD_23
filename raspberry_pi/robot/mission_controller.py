from raspberry_pi.robot.motors import MotorDriver
from raspberry_pi.robot.navigation import next_point, len_points
from raspberry_pi.robot.safety import check_safety

class MissionController:
    def __init__(self):
        self._idx = 0
        self._motors = MotorDriver()
        self.total_points = len_points()

    @property
    def motors(self) -> MotorDriver:
        return self._motors

    def current_point(self) -> str:
        return next_point(self._idx)

    def advance(self) -> str:
        if not check_safety():
            raise RuntimeError('Safety condition not met')
        self._idx += 1
        target = self.current_point()
        self._motors.move_to(target)
        return target

    def is_finished(self) -> bool:
        return self._idx >= self.total_points
