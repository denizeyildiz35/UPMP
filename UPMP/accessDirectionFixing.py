_DIRECTIONS = ("N", "E", "S", "W")
_STEP_DELTA = {"N": (0, -1), "S": (0, 1), "W": (1, 0), "E": (-1, 0)}


def _direct_blocking_count(cell):
    items = [int(x) for x in cell if int(x) != 0]
    if not items:
        return 0

    min_p = min(items)
    blocking = len(items) - 1 - items[::-1].index(min_p)
    while blocking > 0 and items[blocking - 1] == min_p:
        blocking -= 1
    return blocking


def _direct_access_costs(width, length, doors, priorities):
    costs = {}
    if doors.get("N", False):
        y = length - 1
        for x in range(width):
            costs[("N", (x, y))] = _direct_blocking_count(priorities[x][y])
    if doors.get("S", False):
        y = 0
        for x in range(width):
            costs[("S", (x, y))] = _direct_blocking_count(priorities[x][y])
    if doors.get("E", False):
        x = width - 1
        for y in range(length):
            costs[("E", (x, y))] = _direct_blocking_count(priorities[x][y])
    if doors.get("W", False):
        x = 0
        for y in range(length):
            costs[("W", (x, y))] = _direct_blocking_count(priorities[x][y])
    return costs


def _lane_block_cost(seq):
    if not seq:
        return 0

    min_right = seq[-1]
    for i in range(len(seq) - 2, -1, -1):
        value = seq[i]
        if value > min_right:
            return i + 1
        if value < min_right:
            min_right = value
    return 0


def _inner_lanes(direction, width, length, doors):
    lanes = []
    if direction == "E":
        y_start = 0 if not doors.get("S", False) else 1
        y_end = length if not doors.get("N", False) else length - 1
        for y in range(y_start, y_end):
            lanes.append([(x, y) for x in range(width - 1, -1, -1)])
    elif direction == "W":
        y_start = 0 if not doors.get("S", False) else 1
        y_end = length if not doors.get("N", False) else length - 1
        for y in range(y_start, y_end):
            lanes.append([(x, y) for x in range(width)])
    elif direction == "N":
        x_start = 0 if not doors.get("W", False) else 1
        x_end = width if not doors.get("E", False) else width - 1
        for x in range(x_start, x_end):
            lanes.append([(x, y) for y in range(length - 1, -1, -1)])
    elif direction == "S":
        x_start = 0 if not doors.get("W", False) else 1
        x_end = width if not doors.get("E", False) else width - 1
        for x in range(x_start, x_end):
            lanes.append([(x, y) for y in range(length)])
    else:
        raise ValueError("direction must be one of N, E, S, W")
    return lanes


def _access_costs_for_direction(direction, priorities, width, length, direct_costs, doors):
    edge_costs = {}
    for lane in _inner_lanes(direction, width, length, doors):
        seq = []
        prev_node = None
        prev_cost = None

        for node in lane:
            x, y = node
            for priority in priorities[x][y]:
                if int(priority) != 0:
                    seq.append(int(priority))

            current_cost = _lane_block_cost(seq)
            if prev_node is not None:
                edge_costs[(prev_node, node)] = max(0, current_cost - prev_cost)
            elif (direction, node) not in direct_costs:
                direct_costs[(direction, node)] = current_cost

            prev_node = node
            prev_cost = current_cost
    return edge_costs


def _should_cut_border_edge(u, v, width, length, doors):
    common_sides = []
    if u[0] == 0 and v[0] == 0:
        common_sides.append("W")
    if u[0] == width - 1 and v[0] == width - 1:
        common_sides.append("E")
    if u[1] == 0 and v[1] == 0:
        common_sides.append("S")
    if u[1] == length - 1 and v[1] == length - 1:
        common_sides.append("N")
    return bool(common_sides) and any(doors.get(side, False) for side in common_sides)


def _build_vertices(width, length, doors):
    vertices = ["O"]
    for direction in _DIRECTIONS:
        if doors.get(direction, False):
            vertices.append(direction)
    for x in range(width):
        for y in range(length):
            vertices.append((x, y))
    return vertices


def _build_edges(width, length, doors):
    edges = []
    for direction in _DIRECTIONS:
        if doors.get(direction, False):
            edges.append(("O", direction))

    if doors.get("E", False):
        for y in range(length):
            edges.append(("E", (width - 1, y)))
    if doors.get("W", False):
        for y in range(length):
            edges.append(("W", (0, y)))
    if doors.get("N", False):
        for x in range(width):
            edges.append(("N", (x, length - 1)))
    if doors.get("S", False):
        for x in range(width):
            edges.append(("S", (x, 0)))

    if doors.get("E", False):
        for x in range(width - 1, 0, -1):
            for y in range(length):
                u, v = (x, y), (x - 1, y)
                if _should_cut_border_edge(u, v, width, length, doors):
                    continue
                edges.append((u, v))
    if doors.get("W", False):
        for x in range(width - 1):
            for y in range(length):
                u, v = (x, y), (x + 1, y)
                if _should_cut_border_edge(u, v, width, length, doors):
                    continue
                edges.append((u, v))
    if doors.get("N", False):
        for y in range(length - 1, 0, -1):
            for x in range(width):
                u, v = (x, y), (x, y - 1)
                if _should_cut_border_edge(u, v, width, length, doors):
                    continue
                edges.append((u, v))
    if doors.get("S", False):
        for y in range(length - 1):
            for x in range(width):
                u, v = (x, y), (x, y + 1)
                if _should_cut_border_edge(u, v, width, length, doors):
                    continue
                edges.append((u, v))
    return edges


def _solve_ortools(vertices, edges, cost, supply, stack_vertices, backend, time_limit_s):
    try:
        from ortools.linear_solver import pywraplp
    except ImportError as exc:
        raise ImportError(
            "OR-Tools is required for accessDirectionFixing. Install the package with "
            "`pip install UPMP` or install `ortools>=9.12,<10`."
        ) from exc

    preferred = str(backend or "SCIP").upper()
    if preferred not in ("SCIP", "CBC", "SAT"):
        raise ValueError("backend must be one of SCIP, CBC, SAT")

    solver = None
    solver_name = preferred
    for candidate in [preferred] + [b for b in ("SCIP", "CBC", "SAT") if b != preferred]:
        solver = pywraplp.Solver.CreateSolver(candidate)
        if solver is not None:
            solver_name = candidate
            break
    if solver is None:
        return None, "NO_SOLVER", None

    if float(time_limit_s or 0.0) > 0:
        solver.SetTimeLimit(int(float(time_limit_s) * 1000))

    p_count = len(stack_vertices)
    out_arcs = {v: [] for v in vertices}
    in_arcs = {v: [] for v in vertices}
    for edge in edges:
        u, v = edge
        out_arcs[u].append(edge)
        in_arcs[v].append(edge)

    x_var = {}
    f_var = {}
    for edge in edges:
        x_var[edge] = solver.IntVar(0, 1, f"x_{edge[0]}_{edge[1]}")
        f_var[edge] = solver.NumVar(0.0, float(p_count), f"f_{edge[0]}_{edge[1]}")
        solver.Add(f_var[edge] <= float(p_count) * x_var[edge])

    for vertex in vertices:
        if vertex == "O":
            continue
        solver.Add(
            solver.Sum(f_var[arc] for arc in out_arcs.get(vertex, []))
            - solver.Sum(f_var[arc] for arc in in_arcs.get(vertex, []))
            == float(supply.get(vertex, 0))
        )

    solver.Add(solver.Sum(f_var[arc] for arc in out_arcs.get("O", [])) == float(p_count))

    width = max(x for x, _ in stack_vertices) + 1
    length = max(y for _, y in stack_vertices) + 1
    inner_vertices = [
        s for s in stack_vertices
        if 0 < s[0] < width - 1 and 0 < s[1] < length - 1
    ]

    def in_neighbor(cell, direction):
        x, y = cell
        if direction == "N":
            return (x, y + 1)
        if direction == "S":
            return (x, y - 1)
        if direction == "E":
            return (x + 1, y)
        if direction == "W":
            return (x - 1, y)
        return None

    def orthogonal_out_neighbors(cell, direction):
        x, y = cell
        out = []
        if direction in ("N", "S"):
            if x - 1 >= 0:
                out.append((x - 1, y))
            if x + 1 < width:
                out.append((x + 1, y))
        else:
            if y - 1 >= 0:
                out.append((x, y - 1))
            if y + 1 < length:
                out.append((x, y + 1))
        return out

    for cell in inner_vertices:
        for direction in _DIRECTIONS:
            parent = in_neighbor(cell, direction)
            if parent is None or (parent, cell) not in x_var:
                continue
            for child in orthogonal_out_neighbors(cell, direction):
                if (cell, child) in x_var:
                    solver.Add(x_var[(parent, cell)] + x_var[(cell, child)] <= 1)

    objective = solver.Objective()
    for edge in edges:
        objective.SetCoefficient(x_var[edge], float(cost.get(edge, 999999.0)))
        objective.SetCoefficient(f_var[edge], 1e-6)
    objective.SetMinimization()

    status = solver.Solve()
    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        return None, f"{solver_name}:{status}", None

    flow_used = []
    for edge in edges:
        flow_value = f_var[edge].solution_value()
        active_value = x_var[edge].solution_value()
        if flow_value > 1e-6 or active_value > 0.5:
            flow_used.append((edge, flow_value))

    return objective.Value(), f"{solver_name}:{status}", flow_used


def _build_access_lists_from_flow(flow_used, open_dirs):
    out_from = {}
    for (u, v), flow in flow_used:
        if flow > 1e-6:
            out_from.setdefault(u, []).append(v)

    result = {direction: [] for direction in open_dirs}
    for direction in open_dirs:
        dx, dy = _STEP_DELTA[direction]
        for start in out_from.get(direction, []):
            if not isinstance(start, tuple):
                continue
            path = [(direction, start)]
            x, y = start
            while True:
                next_cell = (x + dx, y + dy)
                neighbors = out_from.get((x, y))
                if neighbors and next_cell in neighbors:
                    path.append(((x, y), next_cell))
                    x, y = next_cell
                else:
                    break
            result[direction].append(path)
    return result


def _extract_lane_specs(matrix):
    specs = []
    for paths in matrix:
        for path in paths:
            if not path:
                continue
            first = path[0]
            if not (isinstance(first, tuple) and len(first) == 2 and isinstance(first[0], str)):
                continue
            direction = first[0]
            cells = [first[1]]
            prev = first[1]
            for segment in path[1:]:
                if not (isinstance(segment, tuple) and len(segment) == 2):
                    continue
                nxt = segment[1]
                if nxt != prev:
                    cells.append(nxt)
                    prev = nxt
            specs.append((direction, tuple(cells)))
    return tuple(specs)


def _public_lanes_from_specs(lane_specs):
    return [
        {"direction": direction, "cells": list(cells)}
        for direction, cells in lane_specs
        if cells
    ]


def _resolve_height(depo, width, length):
    for key in ("max_floor", "height"):
        value = depo.get(key)
        if value is not None:
            height = int(value)
            if height > 0:
                return height

    capacity_matrix = depo.get("capacity_matrix")
    if isinstance(capacity_matrix, list) and len(capacity_matrix) == width:
        for row in capacity_matrix:
            if isinstance(row, list) and len(row) == length:
                for value in row:
                    height = int(value)
                    if height > 0:
                        return height

    raise ValueError("depo must contain positive max_floor, height, or capacity_matrix")


def _virtual_lanes_raw_from_specs(lane_specs, priorities, height):
    raw_lanes = []
    for _direction, cells in lane_specs:
        lane = []
        for x, y in cells:
            cell = [int(priority) for priority in priorities[x][y]][:height]
            lane.extend(cell)
            lane.extend([0] * (height - len(cell)))
        raw_lanes.append(lane)
    return raw_lanes


def accessDirectionFixing(depo, backend="SCIP", time_limit_s=0.0, return_details=False):
    if not isinstance(depo, dict):
        raise ValueError("depo must be a dictionary")

    size = depo.get("size") or {}
    width = int(size.get("width", 0))
    length = int(size.get("length", 0))
    if width <= 0 or length <= 0:
        raise ValueError("depo['size'] must contain positive width and length")

    doors = {direction: bool((depo.get("doors") or {}).get(direction, False)) for direction in _DIRECTIONS}
    if not any(doors.values()):
        raise ValueError("at least one access direction must be open")

    priorities = depo.get("priorities")
    if not isinstance(priorities, list) or len(priorities) != width:
        raise ValueError("depo['priorities'] shape must match width")
    for row in priorities:
        if not isinstance(row, list) or len(row) != length:
            raise ValueError("depo['priorities'] shape must match length")
    height = _resolve_height(depo, width, length)

    vertices = _build_vertices(width, length, doors)
    stack_vertices = [v for v in vertices if isinstance(v, tuple)]
    edges = _build_edges(width, length, doors)

    supply = {node: 0 for node in vertices}
    supply["O"] = len(stack_vertices)
    for node in stack_vertices:
        supply[node] = -1

    cost = {edge: 999999.0 for edge in edges}
    for direction in _DIRECTIONS:
        if doors.get(direction, False):
            cost[("O", direction)] = 0.0

    direct_costs = _direct_access_costs(width, length, doors, priorities)
    cost.update(direct_costs)
    for direction in _DIRECTIONS:
        if doors.get(direction, False):
            cost.update(_access_costs_for_direction(direction, priorities, width, length, direct_costs, doors))

    total_cost, status, flow_used = _solve_ortools(
        vertices,
        edges,
        cost,
        supply,
        stack_vertices,
        backend=backend,
        time_limit_s=time_limit_s,
    )
    if flow_used is None:
        raise RuntimeError(f"access direction fixing failed: {status}")

    open_dirs = [direction for direction in _DIRECTIONS if doors.get(direction, False)]
    access_paths = _build_access_lists_from_flow(flow_used, open_dirs)
    matrix = [access_paths[direction] for direction in open_dirs]
    lane_specs = _extract_lane_specs(matrix)
    lanes = _public_lanes_from_specs(lane_specs)
    lane_matrix = _virtual_lanes_raw_from_specs(lane_specs, priorities, height)

    expected_slots = width * length * height
    actual_slots = sum(len(lane) for lane in lane_matrix)
    if actual_slots != expected_slots:
        raise RuntimeError(
            "access direction fixing produced an incomplete lane matrix: "
            f"{actual_slots} slots, expected {expected_slots}"
        )

    if not return_details:
        return lanes, lane_matrix

    details = {
        "lanes": lanes,
        "lane_matrix": lane_matrix,
        "height": height,
        "total_cost": total_cost,
        "status": status,
        "flow_used": flow_used,
        "access_paths": access_paths,
        "matrix": matrix,
        "lane_specs": lane_specs,
    }
    return details, lane_matrix
