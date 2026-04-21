GRID_POINTS = ['A1', 'A2', 'A3', 'B1', 'B2', 'B3', 'C1', 'C2', 'C3']


def next_point(current_idx: int) -> str:
    return GRID_POINTS[current_idx % len(GRID_POINTS)]
