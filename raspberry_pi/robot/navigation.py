DEFAULT_GRID_POINTS = ['A1', 'A2', 'A3', 'B1', 'B2', 'B3', 'C1', 'C2', 'C3']


def normalize_route(points: list[str] | None = None) -> list[str]:
    if not points:
        return DEFAULT_GRID_POINTS[:]
    normalized = [str(point).strip().upper() for point in points if str(point).strip()]
    return normalized or DEFAULT_GRID_POINTS[:]


def next_point(route: list[str], current_idx: int) -> str:
    if current_idx >= len(route):
        return route[-1]
    return route[current_idx]


def len_points(route: list[str]) -> int:
    return len(route)
