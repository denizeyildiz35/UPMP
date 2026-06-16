import random


_DIRECTIONS = ("N", "E", "S", "W")


def _parse_access(access):
    if isinstance(access, dict):
        unknown = set(access) - set(_DIRECTIONS)
        if unknown:
            raise ValueError(f"Unknown access direction(s): {sorted(unknown)}")
        return {d: bool(access.get(d, False)) for d in _DIRECTIONS}

    access_text = str(access or "").upper().strip()
    unknown = set(access_text) - set(_DIRECTIONS)
    if unknown:
        raise ValueError(f"Unknown access direction(s): {sorted(unknown)}")
    return {d: d in access_text for d in _DIRECTIONS}


def _distance_score(x, y, width, length, doors):
    big_m = width + length + 1
    access = [1 if doors[d] else 0 for d in _DIRECTIONS]
    candidates = [
        length - y + big_m * (1 - access[0]),
        width - x + big_m * (1 - access[1]),
        y + big_m * (1 - access[2]),
        x + big_m * (1 - access[3]),
    ]
    return int(min(candidates))


def _validate_positive_int(name, value):
    try:
        parsed = int(value)
    except Exception as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def stackAreaGenerator(
    width,
    length,
    height,
    fill_pct=60,
    access="NSWE",
    max_priority=5,
    seed=None,
    name=None,
):
    width = _validate_positive_int("width", width)
    length = _validate_positive_int("length", length)
    height = _validate_positive_int("height", height)
    max_priority = _validate_positive_int("max_priority", max_priority)

    try:
        fill_pct = float(fill_pct)
    except Exception as exc:
        raise ValueError("fill_pct must be numeric") from exc
    if not 0 <= fill_pct <= 100:
        raise ValueError("fill_pct must be between 0 and 100")

    doors = _parse_access(access)
    rng = random.Random(seed)

    total_capacity = width * length * height
    block_count = int(round(total_capacity * fill_pct / 100.0))

    layout = [[[] for _ in range(length)] for _ in range(width)]
    priorities = [[[] for _ in range(length)] for _ in range(width)]
    capacity_matrix = [[height for _ in range(length)] for _ in range(width)]

    score_groups = {}
    for x in range(width):
        for y in range(length):
            score = _distance_score(x, y, width, length, doors)
            score_groups.setdefault(score, []).append((x, y))

    score_buckets = [
        [score, cells]
        for score, cells in sorted(score_groups.items(), key=lambda item: -item[0])
    ]

    cell_pos = {}
    for bucket_index, (_score, cells) in enumerate(score_buckets):
        for cell_index, xy in enumerate(cells):
            cell_pos[xy] = (bucket_index, cell_index)

    def remove_cell(xy):
        bucket_index, cell_index = cell_pos.pop(xy)
        cells = score_buckets[bucket_index][1]
        last = cells.pop()
        if last != xy:
            cells[cell_index] = last
            cell_pos[last] = (bucket_index, cell_index)

    for block_index in range(block_count):
        chosen = None
        for _score, cells in score_buckets:
            if cells:
                chosen = rng.choice(cells)
                break
        if chosen is None:
            break

        x, y = chosen
        job_name = f"J{block_index + 1}"
        priority = rng.randint(1, max_priority)

        layout[x][y].append(job_name)
        priorities[x][y].append(priority)

        if len(priorities[x][y]) >= height:
            remove_cell(chosen)

    access_label = "".join(d for d in _DIRECTIONS if doors[d]) or "none"
    generated_name = name or f"Generated_{width}x{length}x{height}_Fill{int(fill_pct)}_{access_label}"

    return {
        "coords": {"x1": 0, "x2": width, "y1": 0, "y2": length},
        "size": {"width": width, "length": length},
        "max_floor": height,
        "doors": doors,
        "capacity_matrix": capacity_matrix,
        "layout": layout,
        "priorities": priorities,
        "name": generated_name,
        "meta": {
            "fill_pct": fill_pct,
            "seed": seed,
            "max_priority": max_priority,
            "block_count": sum(len(cell) for row in priorities for cell in row),
            "total_capacity": total_capacity,
            "access": access_label,
        },
    }
