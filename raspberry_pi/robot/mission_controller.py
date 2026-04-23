from raspberry_pi.robot.motors import MotorDriver
from raspberry_pi.robot.navigation import len_points, next_point, normalize_route
from raspberry_pi.robot.safety import check_safety


class MissionController:
    def __init__(self, route_points: list[str] | None = None):
        self._idx = 0
        self._route = normalize_route(route_points)
        self._motors = MotorDriver()
        self.total_points = len_points(self._route)

    @property
    def motors(self) -> MotorDriver:
        return self._motors

    @property
    def route(self) -> list[str]:
        return self._route[:]

    def current_point(self) -> str:
        return next_point(self._route, self._idx)

    def has_next(self) -> bool:
        return (self._idx + 1) < self.total_points

    def advance(self) -> str:
        if not check_safety():
            raise RuntimeError('Safety condition not met')
        if not self.has_next():
            return self.current_point()
        self._idx += 1
        target = self.current_point()
        self._motors.move_to(target)
        return target

    def is_finished(self) -> bool:
        return self._idx >= self.total_points
