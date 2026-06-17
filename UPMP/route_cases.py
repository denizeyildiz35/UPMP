import random
from typing import Optional, Tuple


Cell = Tuple[int, int]


def _compress_lane(lane):
    out = []
    for c in lane or []:
        cc = (int(c[0]), int(c[1]))
        if not out or out[-1] != cc:
            out.append(cc)
    return out


def _ensure_lane_len2(lane, dx, dy, inside_fn):
    ln = _compress_lane(lane)
    if len(ln) >= 2:
        return ln
    if len(ln) == 1:
        c = (int(ln[0][0]) + int(dx), int(ln[0][1]) + int(dy))
        if inside_fn(c):
            return [ln[0], c]
    return ln


def validate_route(route, node_frozen):
    if not node_frozen:
        return {"ok": False, "reason": "empty_grid", "at": None, "index": None}

    w = len(node_frozen)
    l = len(node_frozen[0]) if w > 0 else 0
    if w <= 0 or l <= 0:
        return {"ok": False, "reason": "invalid_grid_shape", "at": None, "index": None}

    cells = []
    for c in route or []:
        if isinstance(c, (list, tuple)) and len(c) >= 2:
            cells.append((int(c[0]), int(c[1])))

    if len(cells) < 2:
        return {"ok": False, "reason": "route_too_short", "at": None, "index": None}

    def _inside(c):
        return 0 <= int(c[0]) < w and 0 <= int(c[1]) < l

    def _blocked(c):
        if not _inside(c):
            return True
        cell = node_frozen[int(c[0])][int(c[1])]
        if isinstance(cell, (list, tuple)):
            return any(int(v) != 0 for v in cell)
        try:
            return int(cell) != 0
        except Exception:
            return False

    for i, c in enumerate(cells):
        if not _inside(c):
            return {"ok": False, "reason": "out_of_bounds", "at": c, "index": i}
        if _blocked(c):
            return {"ok": False, "reason": "occupied_cell", "at": c, "index": i}
        if i > 0:
            p = cells[i - 1]
            if abs(int(c[0]) - int(p[0])) + abs(int(c[1]) - int(p[1])) != 1:
                return {"ok": False, "reason": "non_stepwise", "at": c, "index": i}

    return {"ok": True, "reason": "ok", "at": None, "index": None}


def same(vehicle_cell: Optional[Cell], from_cell: Cell, to_cell: Cell, from_access_dir: str, to_access_dir: str, node_frozen=None, ignore_to_block_for_egress: bool = False):
    _ = (vehicle_cell, ignore_to_block_for_egress)
    if not node_frozen:
        return None
    w = len(node_frozen)
    l = len(node_frozen[0]) if w > 0 else 0
    if w <= 0 or l <= 0:
        return None
    dirs = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}
    fdx, fdy = dirs.get(str(from_access_dir or "").strip().upper(), (0, 0))
    tdx, tdy = dirs.get(str(to_access_dir or "").strip().upper(), (0, 0))
    if (fdx, fdy) == (0, 0) or (tdx, tdy) == (0, 0) or (fdx, fdy) != (tdx, tdy):
        return None

    def _inside(c):
        return 0 <= int(c[0]) < w and 0 <= int(c[1]) < l

    def _blocked(c):
        if not _inside(c):
            return True
        cell = node_frozen[int(c[0])][int(c[1])]
        if isinstance(cell, (list, tuple)):
            return any(int(v) != 0 for v in cell)
        try:
            return int(cell) != 0
        except Exception:
            return False

    def _ray_from(start, dx, dy):
        out = []
        cur = (int(start[0]), int(start[1]))
        while _inside(cur):
            out.append(cur)
            cur = (int(cur[0]) + int(dx), int(cur[1]) + int(dy))
        return out

    def _make_from_front_3(seed_shift):
        out = []
        for k in (1, 2, 3):
            c = (int(from_cell[0]) + int(fdx) * (int(seed_shift) + k), int(from_cell[1]) + int(fdy) * (int(seed_shift) + k))
            if not _inside(c):
                return []
            out.append(c)
        return out

    def _bridge_along_dir(start, end, dx, dy):
        out = [(int(start[0]), int(start[1]))]
        cur = (int(start[0]), int(start[1]))
        tgt = (int(end[0]), int(end[1]))
        while cur != tgt:
            cur = (int(cur[0]) + int(dx), int(cur[1]) + int(dy))
            if (not _inside(cur)) or _blocked(cur):
                return []
            out.append(cur)
        return out

    from_seed = 0
    band = _make_from_front_3(from_seed)
    from_front_3_initial = list(band)
    to_access_line = _ray_from(to_cell, tdx, tdy)
    to_front_3 = []
    for k in (1, 2, 3):
        c = (int(to_cell[0]) + int(tdx) * k, int(to_cell[1]) + int(tdy) * k)
        if not _inside(c):
            return None
        to_front_3.append(c)
    if not band or not to_access_line or len(to_front_3) != 3:
        return None

    if (fdx, fdy) in ((0, 1), (0, -1)):
        target_axis = int(to_cell[0])

        def _aligned(b):
            return len(b) == 3 and all(int(c[0]) == target_axis for c in b)

        def _side_step(b):
            cx = int(b[1][0])
            if cx == target_axis:
                return (0, 0)
            return (1, 0) if target_axis > cx else (-1, 0)
    else:
        target_axis = int(to_cell[1])

        def _aligned(b):
            return len(b) == 3 and all(int(c[1]) == target_axis for c in b)

        def _side_step(b):
            cy = int(b[1][1])
            if cy == target_axis:
                return (0, 0)
            return (0, 1) if target_axis > cy else (0, -1)

    history = [list(band)]
    while True:
        if _aligned(band):
            lanes = [[], [], []]
            for b in history:
                if len(b) == 3:
                    lanes[0].append((int(b[0][0]), int(b[0][1])))
                    lanes[1].append((int(b[1][0]), int(b[1][1])))
                    lanes[2].append((int(b[2][0]), int(b[2][1])))

            for i in range(3):
                if not lanes[i]:
                    return None
                pre = _bridge_along_dir((int(from_front_3_initial[i][0]), int(from_front_3_initial[i][1])), (int(history[0][i][0]), int(history[0][i][1])), int(fdx), int(fdy))
                if not pre:
                    return None
                lanes[i] = _compress_lane(list(pre) + list(lanes[i]))

            completion_failed = False
            for i in range(3):
                if not lanes[i]:
                    return None
                cur = (int(lanes[i][-1][0]), int(lanes[i][-1][1]))
                end = (int(to_front_3[i][0]), int(to_front_3[i][1]))
                if cur == end:
                    continue
                if int(cur[0]) != int(end[0]):
                    sx = 1 if int(end[0]) > int(cur[0]) else -1
                    sy = 0
                else:
                    sx = 0
                    sy = 1 if int(end[1]) > int(cur[1]) else -1
                while cur != end:
                    cur = (int(cur[0]) + int(sx), int(cur[1]) + int(sy))
                    if (not _inside(cur)) or _blocked(cur):
                        completion_failed = True
                        break
                    lanes[i].append(cur)
                if completion_failed:
                    break

            if completion_failed:
                from_seed += 1
                band = _make_from_front_3(from_seed)
                if not band:
                    return None
                history = [list(band)]
                continue

            lanes = [_ensure_lane_len2(ln, fdx, fdy, _inside) for ln in lanes]
            return {
                "carry_parallel_lanes": lanes,
                "carry_main_route": list(lanes[1]) if len(lanes) >= 2 else [],
                "from_front_3_initial": from_front_3_initial,
                "from_front_3_aligned": list(band),
                "to_front_3": to_front_3,
                "to_access_line": to_access_line,
                "from_front_3_history": history,
            }

        sdx, sdy = _side_step(band)
        shifted = [(int(c[0]) + int(sdx), int(c[1]) + int(sdy)) for c in band]
        if not all(_inside(c) for c in shifted) or any(_blocked(c) for c in shifted):
            from_seed += 1
            band = _make_from_front_3(from_seed)
            if not band:
                return None
            history = [list(band)]
            continue
        band = shifted
        history.append(list(band))


def corner(
    vehicle_cell: Optional[Cell],
    from_cell: Cell,
    to_cell: Cell,
    from_access_dir: str,
    to_access_dir: str,
    node_frozen=None,
    ignore_to_block_for_egress: bool = False,
):
    _ = vehicle_cell

    if not node_frozen:
        return None
    w = len(node_frozen)
    l = len(node_frozen[0]) if w > 0 else 0
    if w <= 0 or l <= 0:
        return None

    dirs = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}
    fdx, fdy = dirs.get(str(from_access_dir or "").strip().upper(), (0, 0))
    tdx, tdy = dirs.get(str(to_access_dir or "").strip().upper(), (0, 0))
    if (fdx, fdy) == (0, 0) or (tdx, tdy) == (0, 0):
        return None

    _to_cell = (int(to_cell[0]), int(to_cell[1]))

    def _inside(c):
        return 0 <= int(c[0]) < w and 0 <= int(c[1]) < l

    def _blocked(c):
        if ignore_to_block_for_egress and (int(c[0]), int(c[1])) == _to_cell:
            return False
        if not _inside(c):
            return True
        cell = node_frozen[int(c[0])][int(c[1])]
        if isinstance(cell, (list, tuple)):
            return any(int(v) != 0 for v in cell)
        try:
            return int(cell) != 0
        except Exception:
            return False

    def _ray_from(start, dx, dy):
        out = []
        cur = (int(start[0]), int(start[1]))
        while _inside(cur):
            out.append(cur)
            cur = (int(cur[0]) + int(dx), int(cur[1]) + int(dy))
        return out

    def _front_3(start, dx, dy):
        out = []
        for k in (1, 2, 3):
            c = (int(start[0]) + int(dx) * k, int(start[1]) + int(dy) * k)
            if _inside(c):
                out.append(c)
        return out

    def _shift_points(points, dx, dy, step):
        shifted = []
        for p in points:
            c = (int(p[0]) + int(dx) * int(step), int(p[1]) + int(dy) * int(step))
            if not _inside(c):
                return []
            shifted.append(c)
        return shifted

    def _first_intersection(line_a, line_b):
        bset = set((int(c[0]), int(c[1])) for c in line_b)
        for c in line_a:
            cc = (int(c[0]), int(c[1]))
            if cc in bset:
                return cc
        return None

    def _build_three_lines(starts, dx, dy):
        lines = []
        for s in starts:
            ln = _ray_from(s, dx, dy)
            if not ln:
                return []
            lines.append(ln)
        return lines

    def _bridge_along_dir(start, end, dx, dy):
        out = [(int(start[0]), int(start[1]))]
        cur = (int(start[0]), int(start[1]))
        tgt = (int(end[0]), int(end[1]))
        while cur != tgt:
            cur = (int(cur[0]) + int(dx), int(cur[1]) + int(dy))
            if (not _inside(cur)) or _blocked(cur):
                return []
            out.append(cur)
        return out

    from_access_line = _ray_from(from_cell, fdx, fdy)
    to_access_line = _ray_from(to_cell, tdx, tdy)
    from_front_3 = _front_3(from_cell, fdx, fdy)
    to_front_3 = _front_3(to_cell, tdx, tdy)
    if not from_access_line or not to_access_line:
        return None

    to_set = set(to_access_line)
    intersection_cell = None
    for c in from_access_line:
        if c in to_set:
            intersection_cell = c
            break
    had_intersection = intersection_cell is not None

    if len(from_front_3) < 3 or len(to_front_3) < 3:
        return None

    max_shift = max(1, w + l)
    for d in range(0, max_shift + 1):
        for sf in range(d, -1, -1):
            st = d - sf

            from_shifted = _shift_points(from_front_3, fdx, fdy, sf)
            to_shifted = _shift_points(to_front_3, tdx, tdy, st)
            if len(from_shifted) != 3 or len(to_shifted) != 3:
                continue
            if any(_blocked(c) for c in from_shifted) or any(_blocked(c) for c in to_shifted):
                continue

            from_to_lines = _build_three_lines(from_shifted, tdx, tdy)
            to_from_lines = _build_three_lines(to_shifted, fdx, fdy)
            if len(from_to_lines) != 3 or len(to_from_lines) != 3:
                continue

            meet_cells = []
            ok = True
            for i in range(3):
                m = _first_intersection(from_to_lines[i], to_from_lines[i])
                if m is None:
                    ok = False
                    break
                meet_cells.append(m)

            if ok:
                carry_lanes = []
                for i in range(3):
                    meet = meet_cells[i]
                    a = from_to_lines[i]
                    b = to_from_lines[i]
                    ia = a.index(meet)
                    ib = b.index(meet)
                    core = list(a[: ia + 1]) + list(reversed(b[:ib]))
                    if any(_blocked(c) for c in core):
                        carry_lanes = []
                        break
                    pre = _bridge_along_dir(from_front_3[i], from_shifted[i], int(fdx), int(fdy))
                    post = _bridge_along_dir(to_shifted[i], to_front_3[i], -int(tdx), -int(tdy))
                    if not pre or not post:
                        carry_lanes = []
                        break
                    lane = list(pre) + list(core) + list(post)
                    carry_lanes.append(_compress_lane(lane))
                if len(carry_lanes) != 3:
                    continue
                return {
                    "carry_parallel_lanes": carry_lanes,
                    "carry_main_route": list(carry_lanes[1]),
                    "scenario": "intersecting" if had_intersection else "non_intersecting",
                    "from_access_line": from_access_line,
                    "to_access_line": to_access_line,
                    "from_front_3": from_front_3,
                    "to_front_3": to_front_3,
                    "is_intersecting": bool(had_intersection),
                    "intersection_cell": intersection_cell if had_intersection else None,
                    "from_shift": int(sf),
                    "to_shift": int(st),
                    "from_shifted_front_3": from_shifted,
                    "to_shifted_front_3": to_shifted,
                    "from_to_lines": from_to_lines,
                    "to_from_lines": to_from_lines,
                    "meet_cells": meet_cells,
                    "turn_pivot": meet_cells[1] if len(meet_cells) >= 2 else None,
                }

    return None


def opposite(
    vehicle_cell: Optional[Cell],
    from_cell: Cell,
    to_cell: Cell,
    from_access_dir: str,
    to_access_dir: str,
    node_frozen=None,
    ignore_to_block_for_egress: bool = False,
):
    _ = (vehicle_cell, from_cell, to_cell, ignore_to_block_for_egress)

    if not node_frozen:
        return None
    w = len(node_frozen)
    l = len(node_frozen[0]) if w > 0 else 0
    if w <= 0 or l <= 0:
        return None

    dirs = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}
    fdx, fdy = dirs.get(str(from_access_dir or "").strip().upper(), (0, 0))
    tdx, tdy = dirs.get(str(to_access_dir or "").strip().upper(), (0, 0))
    if (fdx, fdy) == (0, 0) or (tdx, tdy) == (0, 0):
        return None

    if int(fdx) != -int(tdx) or int(fdy) != -int(tdy):
        return None

    def _inside(c):
        return 0 <= int(c[0]) < w and 0 <= int(c[1]) < l

    def _blocked(x, y):
        cell = node_frozen[int(x)][int(y)]
        if isinstance(cell, (list, tuple)):
            return any(int(v) != 0 for v in cell)
        try:
            return int(cell) != 0
        except Exception:
            return False

    def _front_3(start, dx, dy, seed_shift=0):
        out = []
        for k in (1, 2, 3):
            c = (int(start[0]) + int(dx) * (int(seed_shift) + k), int(start[1]) + int(dy) * (int(seed_shift) + k))
            if _inside(c):
                out.append(c)
        return out

    def _side_window_ok(band, side_dir, orientation):
        if side_dir == (0, 0):
            return True
        mid = band[1]
        if orientation == "vertical":
            sx = int(side_dir[0])
            ys = [int(c[1]) for c in band]
            xs = [int(mid[0]) + sx, int(mid[0]) + 2 * sx]
            cells = [(x, y) for x in xs for y in ys]
        else:
            sy = int(side_dir[1])
            xs = [int(c[0]) for c in band]
            ys = [int(mid[1]) + sy, int(mid[1]) + 2 * sy]
            cells = [(x, y) for y in ys for x in xs]
        return all(_inside(c) and (not _blocked(c[0], c[1])) for c in cells)

    def _align_to_strip(start_cell, dx, dy, axis, orientation, require_side_window):
        seed = 0
        band = _front_3(start_cell, dx, dy, seed)
        if len(band) < 3:
            return None, [], (0, 0)
        history = [list(band)]
        last_side = (0, 0)

        while True:
            if orientation == "vertical":
                if all(int(c[0]) == int(axis) for c in band):
                    if not require_side_window:
                        return band, history, last_side
                    if last_side == (0, 0):
                        for s in ((1, 0), (-1, 0)):
                            if _side_window_ok(band, s, orientation):
                                return band, history, s
                        return None, history, (0, 0)
                    if _side_window_ok(band, last_side, orientation):
                        return band, history, last_side
                    seed += 1
                    band = _front_3(start_cell, dx, dy, seed)
                    if len(band) < 3:
                        return None, history, (0, 0)
                    history = [list(band)]
                    last_side = (0, 0)
                    continue
                mid = int(band[1][0])
                step = 1 if int(axis) > mid else -1
                shifted = [(int(c[0]) + step, int(c[1])) for c in band]
                side_dir = (step, 0)
            else:
                if all(int(c[1]) == int(axis) for c in band):
                    if not require_side_window:
                        return band, history, last_side
                    if last_side == (0, 0):
                        for s in ((0, 1), (0, -1)):
                            if _side_window_ok(band, s, orientation):
                                return band, history, s
                        return None, history, (0, 0)
                    if _side_window_ok(band, last_side, orientation):
                        return band, history, last_side
                    seed += 1
                    band = _front_3(start_cell, dx, dy, seed)
                    if len(band) < 3:
                        return None, history, (0, 0)
                    history = [list(band)]
                    last_side = (0, 0)
                    continue
                mid = int(band[1][1])
                step = 1 if int(axis) > mid else -1
                shifted = [(int(c[0]), int(c[1]) + step) for c in band]
                side_dir = (0, step)

            if not all(_inside(c) for c in shifted) or any(_blocked(c[0], c[1]) for c in shifted):
                seed += 1
                band = _front_3(start_cell, dx, dy, seed)
                if len(band) < 3:
                    return None, history, (0, 0)
                history = [list(band)]
                last_side = (0, 0)
                continue

            band = shifted
            history.append(list(band))
            last_side = side_dir

    def _bridge_along_dir(start, end, dx, dy):
        out = [(int(start[0]), int(start[1]))]
        cur = (int(start[0]), int(start[1]))
        tgt = (int(end[0]), int(end[1]))
        while cur != tgt:
            cur = (int(cur[0]) + int(dx), int(cur[1]) + int(dy))
            if (not _inside(cur)) or _blocked(cur[0], cur[1]):
                return []
            out.append(cur)
        return out

    def _lane_trace_from_history(initial_cell, history, dx, dy, lane_idx):
        if not history:
            return []
        first_band = history[0]
        if lane_idx >= len(first_band):
            return []
        first_cell = (int(first_band[lane_idx][0]), int(first_band[lane_idx][1]))
        pre = _bridge_along_dir(initial_cell, first_cell, int(dx), int(dy))
        if not pre:
            return []
        out = list(pre)
        for band in history:
            if lane_idx >= len(band):
                return []
            c = (int(band[lane_idx][0]), int(band[lane_idx][1]))
            out.append(c)
        return _compress_lane(out)

    def _nearest_axis_order(size, ref_axis):
        if size <= 0:
            return []
        r = int(ref_axis)
        if r < 0:
            r = 0
        if r >= int(size):
            r = int(size) - 1
        out = []
        used = set()
        max_d = max(r, int(size) - 1 - r)
        for d in range(0, int(max_d) + 1):
            a = r - d
            b = r + d
            if 0 <= a < int(size) and a not in used:
                out.append(a)
                used.add(a)
            if 0 <= b < int(size) and b not in used:
                out.append(b)
                used.add(b)
        return out

    from_front_3_initial = _front_3(from_cell, fdx, fdy, 0)
    to_front_3_initial = _front_3(to_cell, tdx, tdy, 0)

    if int(fdx) == 0:
        x_ref = int(round((int(from_cell[0]) + int(to_cell[0])) / 2.0))
        scan_order = _nearest_axis_order(w, x_ref)
        for x in scan_order:
            if all(not _blocked(x, y) for y in range(0, l)):
                strip = [(int(x), int(y)) for y in range(0, l)]
                from_front_3, from_history, from_last_side = _align_to_strip(from_cell, fdx, fdy, int(x), "vertical", True)
                if from_front_3 is None:
                    continue
                to_front_3, to_history, _ = _align_to_strip(to_cell, tdx, tdy, int(x), "vertical", False)
                if to_front_3 is None:
                    continue
                to_by_y = {int(c[1]): c for c in to_front_3}
                from_traces = []
                for i in range(3):
                    tr = _lane_trace_from_history((int(from_front_3_initial[i][0]), int(from_front_3_initial[i][1])), from_history, int(fdx), int(fdy), i)
                    if not tr:
                        from_traces = []
                        break
                    from_traces.append(tr)
                if len(from_traces) != 3:
                    continue
                to_traces_by_y = {}
                ok_to_traces = True
                for i in range(3):
                    tr = _lane_trace_from_history((int(to_front_3_initial[i][0]), int(to_front_3_initial[i][1])), to_history, int(tdx), int(tdy), i)
                    if not tr:
                        ok_to_traces = False
                        break
                    ky = int(to_front_3[i][1])
                    to_traces_by_y[ky] = tr
                if not ok_to_traces:
                    continue
                carry_lanes = []
                for i, fc in enumerate(from_front_3):
                    tc = to_by_y.get(int(fc[1]), to_front_3[i])
                    y0, y1 = int(fc[1]), int(tc[1])
                    step = 1 if y1 >= y0 else -1
                    core = [(int(x), yy) for yy in range(y0, y1 + step, step)]
                    pre = from_traces[i]
                    post_src = to_traces_by_y.get(int(tc[1]), [])
                    post = list(reversed(post_src)) if post_src else []
                    if not pre or not post:
                        carry_lanes = []
                        break
                    lane = _compress_lane(list(pre) + list(core) + list(post))
                    lane = _ensure_lane_len2(lane, tdx, tdy, _inside)
                    carry_lanes.append(lane)
                if len(carry_lanes) != 3:
                    continue
                return {
                    "carry_parallel_lanes": carry_lanes,
                    "carry_main_route": list(carry_lanes[1]),
                    "orientation": "vertical",
                    "strip_axis_x": int(x),
                    "strip_line": strip,
                    "from_front_3_initial": from_front_3_initial,
                    "from_front_3": from_front_3,
                    "from_front_3_history": from_history,
                    "to_front_3": to_front_3,
                    "to_front_3_initial": to_front_3_initial,
                    "to_front_3_history": to_history,
                    "turn_pivot": from_front_3[1] if len(from_front_3) >= 2 else None,
                    "from_approach_side": from_last_side,
                }
        return None

    y_ref = int(round((int(from_cell[1]) + int(to_cell[1])) / 2.0))
    scan_order = _nearest_axis_order(l, y_ref)
    for y in scan_order:
        if all(not _blocked(x, y) for x in range(0, w)):
            strip = [(int(x), int(y)) for x in range(0, w)]
            from_front_3, from_history, from_last_side = _align_to_strip(from_cell, fdx, fdy, int(y), "horizontal", True)
            if from_front_3 is None:
                continue
            to_front_3, to_history, _ = _align_to_strip(to_cell, tdx, tdy, int(y), "horizontal", False)
            if to_front_3 is None:
                continue
            to_by_x = {int(c[0]): c for c in to_front_3}
            from_traces = []
            for i in range(3):
                tr = _lane_trace_from_history((int(from_front_3_initial[i][0]), int(from_front_3_initial[i][1])), from_history, int(fdx), int(fdy), i)
                if not tr:
                    from_traces = []
                    break
                from_traces.append(tr)
            if len(from_traces) != 3:
                continue
            to_traces_by_x = {}
            ok_to_traces = True
            for i in range(3):
                tr = _lane_trace_from_history((int(to_front_3_initial[i][0]), int(to_front_3_initial[i][1])), to_history, int(tdx), int(tdy), i)
                if not tr:
                    ok_to_traces = False
                    break
                kx = int(to_front_3[i][0])
                to_traces_by_x[kx] = tr
            if not ok_to_traces:
                continue
            carry_lanes = []
            for i, fc in enumerate(from_front_3):
                tc = to_by_x.get(int(fc[0]), to_front_3[i])
                x0, x1 = int(fc[0]), int(tc[0])
                step = 1 if x1 >= x0 else -1
                core = [(xx, int(y)) for xx in range(x0, x1 + step, step)]
                pre = from_traces[i]
                post_src = to_traces_by_x.get(int(tc[0]), [])
                post = list(reversed(post_src)) if post_src else []
                if not pre or not post:
                    carry_lanes = []
                    break
                lane = _compress_lane(list(pre) + list(core) + list(post))
                lane = _ensure_lane_len2(lane, tdx, tdy, _inside)
                carry_lanes.append(lane)
            if len(carry_lanes) != 3:
                continue
            return {
                "carry_parallel_lanes": carry_lanes,
                "carry_main_route": list(carry_lanes[1]),
                "orientation": "horizontal",
                "strip_axis_y": int(y),
                "strip_line": strip,
                "from_front_3_initial": from_front_3_initial,
                "from_front_3": from_front_3,
                "from_front_3_history": from_history,
                "to_front_3": to_front_3,
                "to_front_3_initial": to_front_3_initial,
                "to_front_3_history": to_history,
                "turn_pivot": from_front_3[1] if len(from_front_3) >= 2 else None,
                "from_approach_side": from_last_side,
            }
    return None
