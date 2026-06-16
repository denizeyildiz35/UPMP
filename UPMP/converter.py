import copy


_DIRECTIONS = {"N", "E", "S", "W"}


def _resolve_height(depo):
    try:
        height = int(depo.get("max_floor", 0))
    except Exception:
        height = 0
    if height > 0:
        return height

    capacity = depo.get("capacity_matrix")
    if isinstance(capacity, list):
        for row in capacity:
            if not isinstance(row, list):
                continue
            for value in row:
                try:
                    height = int(value)
                except Exception:
                    height = 0
                if height > 0:
                    return height

    raise ValueError("depo must contain a positive max_floor or capacity_matrix")


def _validate_depo(depo):
    if not isinstance(depo, dict):
        raise ValueError("depo must be a dictionary")

    size = depo.get("size") or {}
    try:
        width = int(size.get("width", 0))
        length = int(size.get("length", 0))
    except Exception as exc:
        raise ValueError("depo['size'] must contain numeric width and length") from exc
    if width <= 0 or length <= 0:
        raise ValueError("depo['size'] must contain positive width and length")

    priorities = depo.get("priorities")
    if not isinstance(priorities, list) or len(priorities) != width:
        raise ValueError("depo['priorities'] shape must match width")
    for row in priorities:
        if not isinstance(row, list) or len(row) != length:
            raise ValueError("depo['priorities'] shape must match length")

    height = _resolve_height(depo)
    for x, row in enumerate(priorities):
        for y, stack in enumerate(row):
            if not isinstance(stack, list):
                raise ValueError(f"depo['priorities'][{x}][{y}] must be a list")
            if len(stack) > height:
                raise ValueError(f"stack at ({x}, {y}) exceeds height {height}")

    return width, length, height, priorities


def _normalize_lanes(lanes, width, length):
    if not isinstance(lanes, (list, tuple)):
        raise ValueError("lanes must be a list")

    normalized = []
    seen_cells = set()
    for lane_index, lane in enumerate(lanes):
        if not isinstance(lane, dict):
            raise ValueError(f"lanes[{lane_index}] must be a dictionary")
        direction = str(lane.get("direction", "")).upper()
        if direction not in _DIRECTIONS:
            raise ValueError(f"lanes[{lane_index}]['direction'] must be one of N/E/S/W")
        cells_raw = lane.get("cells")
        if not isinstance(cells_raw, (list, tuple)) or not cells_raw:
            raise ValueError(f"lanes[{lane_index}]['cells'] must be a non-empty list")

        cells = []
        for cell in cells_raw:
            if not isinstance(cell, (list, tuple)) or len(cell) < 2:
                raise ValueError(f"invalid cell in lanes[{lane_index}]")
            x, y = int(cell[0]), int(cell[1])
            if not (0 <= x < width and 0 <= y < length):
                raise ValueError(f"cell ({x}, {y}) in lanes[{lane_index}] is outside depo size")
            cells.append((x, y))
            seen_cells.add((x, y))

        normalized.append({"direction": direction, "cells": cells})

    expected_cells = width * length
    if len(seen_cells) != expected_cells:
        raise ValueError(
            "lanes must cover every depo cell exactly once for animation conversion"
        )

    return normalized


def _slot_to_cell(lanes, height, lane_index, slot):
    if lane_index < 0 or lane_index >= len(lanes):
        raise ValueError(f"lane index out of range: {lane_index}")
    if slot < 0:
        raise ValueError(f"slot index must be non-negative: {slot}")

    lane = lanes[lane_index]
    cell_index = slot // height
    z_index = slot % height
    cells = lane["cells"]
    if cell_index >= len(cells):
        raise ValueError(
            f"slot {slot} is outside lane {lane_index} capacity {len(cells) * height}"
        )
    x, y = cells[cell_index]
    return x, y, z_index, lane["direction"]


def _freeze_state(state):
    return tuple(tuple(tuple(int(v) for v in cell) for cell in row) for row in state)


def _padded_initial_state(priorities, height):
    state = []
    for row in priorities:
        out_row = []
        for stack in row:
            values = [int(v) for v in stack[:height]]
            values.extend([0] * (height - len(values)))
            out_row.append(values)
        state.append(out_row)
    return state


def convert_ida_result_to_animation_data(ida_result, depo, lanes, lane_matrix=None):
    """Convert C++ IDA* lane/slot moves into physical animation data.

    Returns a dictionary with physical moves, move directions, and frozen states.
    It does not create any GUI objects.
    """
    if not isinstance(ida_result, dict):
        raise ValueError("ida_result must be a dictionary")

    width, length, height, priorities = _validate_depo(depo)
    normalized_lanes = _normalize_lanes(lanes, width, length)

    if lane_matrix is not None:
        if not isinstance(lane_matrix, list) or len(lane_matrix) != len(normalized_lanes):
            raise ValueError("lane_matrix length must match lanes length")
        for idx, lane_values in enumerate(lane_matrix):
            expected = len(normalized_lanes[idx]["cells"]) * height
            if len(lane_values) != expected:
                raise ValueError(
                    f"lane_matrix[{idx}] has {len(lane_values)} slots, expected {expected}"
                )

    state = _padded_initial_state(priorities, height)
    states_frozen = [_freeze_state(state)]
    physical_moves = []
    move_directions = []

    for move_index, raw_move in enumerate(list(ida_result.get("moves", []))):
        if not isinstance(raw_move, (list, tuple)) or len(raw_move) < 5:
            raise ValueError(f"ida_result['moves'][{move_index}] must contain at least 5 values")

        src_lane = int(raw_move[0])
        src_slot = int(raw_move[1])
        dst_lane = int(raw_move[2])
        dst_slot = int(raw_move[3])
        item = int(raw_move[4])

        sw, sl, sh, src_dir = _slot_to_cell(normalized_lanes, height, src_lane, src_slot)
        tw, tl, th, dst_dir = _slot_to_cell(normalized_lanes, height, dst_lane, dst_slot)

        if int(state[sw][sl][sh]) != item:
            raise ValueError(
                "ida_result move does not match current state: "
                f"move {move_index}, expected item {item} at ({sw}, {sl}, {sh}), "
                f"found {state[sw][sl][sh]}"
            )
        if int(state[tw][tl][th]) != 0:
            raise ValueError(
                "ida_result destination slot is not empty: "
                f"move {move_index}, target ({tw}, {tl}, {th}) contains {state[tw][tl][th]}"
            )

        state[sw][sl][sh] = 0
        state[tw][tl][th] = item

        physical_moves.append((sw, sl, tw, tl, item))
        move_directions.append(
            {
                "pick_direction": src_dir,
                "place_direction": dst_dir,
                "pick_cell": (sw, sl),
                "place_cell": (tw, tl),
                "pick_height": sh,
                "place_height": th,
            }
        )
        states_frozen.append(_freeze_state(state))

    return {
        "width": width,
        "length": length,
        "height": height,
        "initial_state": _padded_initial_state(priorities, height),
        "final_state": copy.deepcopy(state),
        "states_frozen": states_frozen,
        "moves": physical_moves,
        "move_directions": move_directions,
        "lanes": normalized_lanes,
        "num_moves": len(physical_moves),
    }

