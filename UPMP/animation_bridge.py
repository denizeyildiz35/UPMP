"""RouteAnimation icin ortak kopru helper'lari."""

from typing import Any, Dict, List, Optional, Sequence, Tuple


_TIME_PARAM_MAP: Dict[str, str] = {
    "duz": "time_per_grid_straight",
    "strafe": "time_per_grid_strafe",
    "donus(90)": "time_turn_90",
    "bos_catal_cikis": "time_fork_up_empty",
    "bos_catal_inis": "time_fork_down_empty",
    "catal_cikis": "time_fork_up_loaded",
    "catal_inis": "time_fork_down_loaded",
    "pick": "time_pick_insert",
    "place": "time_place_release",
}

_ANIM_DEFAULTS: Dict[str, float] = {
    "duz": 1.0,
    "strafe": 1.5,
    "donus(90)": 2.0,
    "bos_catal_cikis": 0.5,
    "bos_catal_inis": 0.4,
    "catal_cikis": 0.8,
    "catal_inis": 0.6,
    "pick": 2.0,
    "place": 2.0,
}


def apply_time_params(anim, time_params: Optional[Dict[str, Any]]) -> None:
    if anim is None:
        return
    tp = dict(time_params or {})
    new_params: Dict[str, float] = {}
    for anim_key, dialog_key in _TIME_PARAM_MAP.items():
        try:
            new_params[anim_key] = float(tp.get(dialog_key, _ANIM_DEFAULTS[anim_key]))
        except Exception:
            new_params[anim_key] = float(_ANIM_DEFAULTS[anim_key])
    anim.time_parameters = new_params


def _animation_time_params(time_params: Optional[Dict[str, Any]]) -> Dict[str, float]:
    tp = dict(time_params or {})
    out: Dict[str, float] = {}
    for anim_key, dialog_key in _TIME_PARAM_MAP.items():
        try:
            out[anim_key] = float(tp.get(dialog_key, _ANIM_DEFAULTS[anim_key]))
        except Exception:
            out[anim_key] = float(_ANIM_DEFAULTS[anim_key])
    return out


def _stack_height(states: Optional[Sequence], step_idx: int, cell: Optional[Tuple[int, int]]) -> int:
    if cell is None or not states or step_idx < 0 or step_idx >= len(states):
        return 0
    try:
        stack = states[step_idx][int(cell[0])][int(cell[1])]
        return int(len(stack))
    except Exception:
        return 0


def _to_cell(c) -> Optional[Tuple[int, int]]:
    if isinstance(c, (list, tuple)) and len(c) >= 2:
        try:
            return (int(c[0]), int(c[1]))
        except Exception:
            return None
    return None


def _normalize_lane_cells(raw_lane) -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    for c in raw_lane or []:
        cc = _to_cell(c)
        if cc is None:
            continue
        if not out or out[-1] != cc:
            out.append(cc)
    return out


def _is_stepwise_route(cells: Sequence[Tuple[int, int]]) -> bool:
    cells = list(cells or [])
    if len(cells) < 2:
        return False
    for i in range(1, len(cells)):
        if abs(int(cells[i][0]) - int(cells[i - 1][0])) + abs(int(cells[i][1]) - int(cells[i - 1][1])) != 1:
            return False
    return True


def _filter_stepwise_lanes(lanes) -> List[List[Tuple[int, int]]]:
    out: List[List[Tuple[int, int]]] = []
    for lane in lanes or []:
        ln = _normalize_lane_cells(lane or [])
        if len(ln) >= 2 and _is_stepwise_route(ln):
            out.append(ln)
    return out


def _normalize_key(v: Any) -> str:
    return str(v or "").strip().upper()


def _classify_route_relation(from_access_dir: str, to_access_dir: str) -> str:
    fd = _normalize_key(from_access_dir)
    td = _normalize_key(to_access_dir)
    valid = {"N", "E", "S", "W"}
    if fd not in valid or td not in valid:
        return "unknown"
    if fd == td:
        return "same"
    if (fd, td) in {("N", "S"), ("S", "N"), ("E", "W"), ("W", "E")}:
        return "opposite"
    return "corner"


def _route_case_handlers() -> Dict[str, object]:
    from .route_cases import corner, opposite, same

    return {"same": same, "corner": corner, "opposite": opposite}


def _normalize_route_case_output(raw_case) -> Dict:
    if not isinstance(raw_case, dict):
        return {
            "approach_parallel_lanes": [],
            "approach_main_route": [],
            "carry_parallel_lanes": [],
            "carry_main_route": [],
            "turn_pivot": None,
            "turn_side": None,
        }

    def _norm_lanes(value) -> List[List[Tuple[int, int]]]:
        out: List[List[Tuple[int, int]]] = []
        for lane in value or []:
            ln = _normalize_lane_cells(lane)
            if len(ln) >= 2:
                out.append(ln)
        return out

    ap_lanes = _norm_lanes(raw_case.get("approach_parallel_lanes", raw_case.get("approach_lanes", [])))
    cr_lanes = _norm_lanes(raw_case.get("carry_parallel_lanes", raw_case.get("carry_lanes", raw_case.get("lanes", []))))
    ap_main = _normalize_lane_cells(raw_case.get("approach_main_route", raw_case.get("approach_route", [])))
    cr_main = _normalize_lane_cells(raw_case.get("carry_main_route", raw_case.get("carry_route", raw_case.get("route", []))))

    if len(ap_main) < 2 and ap_lanes:
        ap_main = ap_lanes[len(ap_lanes) // 2]
    if len(cr_main) < 2 and cr_lanes:
        cr_main = cr_lanes[len(cr_lanes) // 2]

    return {
        "approach_parallel_lanes": ap_lanes,
        "approach_main_route": ap_main if len(ap_main) >= 2 else [],
        "carry_parallel_lanes": cr_lanes,
        "carry_main_route": cr_main if len(cr_main) >= 2 else [],
        "turn_pivot": (
            tuple(int(v) for v in raw_case.get("turn_pivot", ()))
            if isinstance(raw_case.get("turn_pivot"), (list, tuple)) and len(raw_case.get("turn_pivot", ())) >= 2
            else None
        ),
        "turn_side": (
            str(raw_case.get("turn_side")).strip().lower()
            if str(raw_case.get("turn_side", "")).strip().lower() in {"left", "right"}
            else None
        ),
        "from_approach_side": raw_case.get("from_approach_side"),
        "is_outer_fallback": bool(raw_case.get("is_outer_fallback", False)),
    }


def build_step_plans_from_playback(
    moves: Sequence,
    move_paths: Sequence,
    states: Optional[Sequence] = None,
) -> List[Dict]:
    out: List[Dict] = []
    for i, mp in enumerate(move_paths or []):
        if not isinstance(mp, dict):
            continue

        mv = moves[i] if (moves is not None and i < len(moves)) else None

        src = _to_cell(mp.get("source_cell"))
        if src is None and mv is not None and len(mv) >= 2:
            try:
                src = (int(mv[0]), int(mv[1]))
            except Exception:
                src = None

        dst = _to_cell(mp.get("target_cell"))
        if dst is None and mv is not None and len(mv) >= 4:
            try:
                dst = (int(mv[2]), int(mv[3]))
            except Exception:
                dst = None

        pick_h = int(mp.get("pick_height", 0) or 0)
        place_h = int(mp.get("place_height", 0) or 0)
        try:
            item = int(mv[4]) if mv is not None and len(mv) >= 5 else int(mp.get("item", 0) or 0)
        except Exception:
            item = int(mp.get("item", 0) or 0)
        src_h = _stack_height(states, i, src)
        dst_h = _stack_height(states, i, dst)
        pick_level = (src_h - pick_h) if src_h > 0 else pick_h
        place_level = (dst_h - place_h) if dst_h > 0 else place_h

        approach_main = _normalize_lane_cells(mp.get("approach_route", []) or [])
        if not _is_stepwise_route(approach_main):
            approach_main = []
        carry_main = _normalize_lane_cells(mp.get("route", []) or [])
        if not _is_stepwise_route(carry_main):
            carry_main = []

        approach_lanes = _filter_stepwise_lanes(mp.get("approach_rays", []) or [])
        carry_lanes = _filter_stepwise_lanes(mp.get("rays", []) or [])

        out.append({
            "relation": mp.get("relation"),
            "pick_direction": mp.get("pick_direction"),
            "place_direction": mp.get("place_direction"),
            "source": src,
            "target": dst,
            "item": item,
            "pick_height": pick_h,
            "place_height": place_h,
            "pick_level": int(pick_level),
            "place_level": int(place_level),
            "ok": bool(approach_main or carry_main),
            "approach_parallel_lanes": list(approach_lanes or []),
            "approach_main_route": list(approach_main or []),
            "turn_pivot": mp.get("turn_pivot"),
            "turn_side": mp.get("turn_side"),
            "from_approach_side": mp.get("from_approach_side"),
            "approach_turn_pivot": mp.get("approach_turn_pivot"),
            "approach_turn_side": mp.get("approach_turn_side"),
            "approach_from_dir": mp.get("approach_from_dir"),
            "approach_relation": mp.get("approach_relation"),
            "carry_parallel_lanes": list(carry_lanes or []),
            "carry_main_route": list(carry_main or []),
        })
    return out


def _move_tuple_and_meta(move, move_path=None, move_direction=None):
    if isinstance(move, dict):
        try:
            src = _to_cell(move.get("source"))
            dst = _to_cell(move.get("target"))
            item = int(move.get("item", 0) or 0)
            if src is None or dst is None:
                return None, {}
            sw, sl, tw, tl = src[0], src[1], dst[0], dst[1]
        except Exception:
            return None, {}
    else:
        try:
            sw, sl, tw, tl, item = move
        except Exception:
            return None, {}

    mp = move_path if isinstance(move_path, dict) else {}
    md = move_direction if isinstance(move_direction, dict) else {}
    mv_dict = move if isinstance(move, dict) else {}
    pick_dir = str(mp.get("pick_direction") or md.get("pick_direction") or mv_dict.get("pick_direction") or "N").strip().upper()
    place_dir = str(mp.get("place_direction") or md.get("place_direction") or mv_dict.get("place_direction") or "N").strip().upper()
    if pick_dir not in ("N", "E", "S", "W"):
        pick_dir = "N"
    if place_dir not in ("N", "E", "S", "W"):
        place_dir = "N"

    def _int_field(key, default=0):
        try:
            return int(mp.get(key, md.get(key, mv_dict.get(key, default))) or default)
        except Exception:
            return int(default)

    return (
        (int(sw), int(sl), int(tw), int(tl), int(item)),
        {
            "pick_direction": pick_dir,
            "place_direction": place_dir,
            "pick_height": _int_field("pick_height", 0),
            "place_height": _int_field("place_height", 0),
        },
    )


def rebuild_step_plans_like_pathfinding_deneme(
    moves: Sequence,
    states: Sequence,
    move_paths: Optional[Sequence] = None,
    move_directions: Optional[Sequence] = None,
) -> List[Dict]:
    if not moves or not states or len(states) < 2:
        return []

    handlers = _route_case_handlers()
    route_pad = 5
    plans: List[Dict] = []

    def _zero_stack_from_frozen(frozen):
        if not frozen:
            return ()
        h = len(frozen[0][0]) if frozen and frozen[0] else 0
        return tuple(0 for _ in range(h))

    def _freeze_state(state):
        return tuple(tuple(tuple(int(v) for v in cell) for cell in row) for row in state)

    def _pad_frozen(frozen, pad: int):
        if not frozen:
            return frozen
        ww = len(frozen)
        ll = len(frozen[0]) if ww > 0 else 0
        if ww <= 0 or ll <= 0:
            return frozen
        z = _zero_stack_from_frozen(frozen)
        out = []
        for x in range(ww + 2 * pad):
            row = []
            for y in range(ll + 2 * pad):
                sx = x - pad
                sy = y - pad
                if 0 <= sx < ww and 0 <= sy < ll:
                    row.append(tuple(int(v) for v in frozen[sx][sy]))
                else:
                    row.append(z)
            out.append(tuple(row))
        return tuple(out)

    def _shift_cell(c, pad: int):
        if c is None:
            return None
        return (int(c[0]) + int(pad), int(c[1]) + int(pad))

    def _unshift_cell(c, pad: int):
        if not isinstance(c, (list, tuple)) or len(c) < 2:
            return None
        return (int(c[0]) - int(pad), int(c[1]) - int(pad))

    def _unshift_lane(lane, pad: int):
        out = []
        for c in lane or []:
            if isinstance(c, (list, tuple)) and len(c) >= 2:
                out.append((int(c[0]) - int(pad), int(c[1]) - int(pad)))
        return out

    def _unshift_lanes(lanes, pad: int):
        return [_unshift_lane(ln, pad) for ln in (lanes or [])]

    def _compute_turn_side(rel, from_dir, to_dir, from_approach_side=None):
        _opp = {"N": "S", "S": "N", "E": "W", "W": "E"}
        _idx = {"N": 0, "E": 1, "S": 2, "W": 3}
        _dirs = ["N", "E", "S", "W"]
        if rel == "corner":
            fi = _idx.get(_opp.get(from_dir, ""), -1)
            ti = _idx.get(_opp.get(to_dir, ""), -1)
            if fi < 0 or ti < 0:
                return None
            diff = (ti - fi) % 4
            return "right" if diff == 1 else "left" if diff == 3 else None
        if rel == "opposite":
            _side_map = {(1, 0): "E", (-1, 0): "W", (0, 1): "N", (0, -1): "S"}
            approach_dir = _side_map.get(tuple(from_approach_side or ()))
            if not approach_dir:
                return None
            fi = _idx.get(_opp.get(from_dir, ""), -1)
            if fi < 0:
                return None
            right_dir = _dirs[(fi + 1) % 4]
            return "right" if approach_dir == right_dir else "left"
        return None

    normalized_moves: List[Dict] = []
    for i, mv in enumerate(moves or []):
        mp = move_paths[i] if move_paths is not None and i < len(move_paths) else None
        md = move_directions[i] if move_directions is not None and i < len(move_directions) else None
        parsed = _move_tuple_and_meta(mv, mp, md)
        if parsed[0] is None:
            continue
        move_tuple, meta = parsed
        normalized_moves.append(
            {
                "source": (int(move_tuple[0]), int(move_tuple[1])),
                "target": (int(move_tuple[2]), int(move_tuple[3])),
                "item": int(move_tuple[4]),
                "pick_direction": _normalize_key(meta.get("pick_direction", "N")),
                "place_direction": _normalize_key(meta.get("place_direction", "N")),
                "pick_height": int(meta.get("pick_height", 0) or 0),
                "place_height": int(meta.get("place_height", 0) or 0),
            }
        )

    for i, mv in enumerate(normalized_moves):
        src = tuple(int(v) for v in mv.get("source", (0, 0)))
        dst = tuple(int(v) for v in mv.get("target", (0, 0)))
        pick_dir = _normalize_key(mv.get("pick_direction", "N"))
        place_dir = _normalize_key(mv.get("place_direction", "N"))
        relation = _classify_route_relation(pick_dir, place_dir)

        approach_turn_pivot: Optional[Tuple[int, int]] = None
        approach_lanes: List[List[Tuple[int, int]]] = []
        approach_main: List[Tuple[int, int]] = []
        approach_turn_side: Optional[str] = None
        approach_from_approach_side = None
        if i > 0:
            prev_mv = normalized_moves[i - 1]
            approach_from_cell = tuple(int(v) for v in prev_mv.get("target", src))
            approach_from_dir = _normalize_key(prev_mv.get("place_direction", pick_dir))
        else:
            approach_from_cell = src
            approach_from_dir = pick_dir
        approach_relation = _classify_route_relation(approach_from_dir, pick_dir)
        approach_fn = handlers.get(approach_relation)
        if callable(approach_fn) and i > 0:
            try:
                frozen_approach_base = _freeze_state(states[i])
                frozen_approach = _pad_frozen(frozen_approach_base, route_pad)
                approach_from_p = _shift_cell(approach_from_cell, route_pad)
                src_p = _shift_cell(src, route_pad)
                raw_ap = approach_fn(
                    vehicle_cell=None,
                    from_cell=approach_from_p,
                    to_cell=src_p,
                    from_access_dir=approach_from_dir,
                    to_access_dir=pick_dir,
                    node_frozen=frozen_approach,
                    ignore_to_block_for_egress=False,
                )
            except Exception:
                raw_ap = None
            parsed_ap = _normalize_route_case_output(raw_ap)
            approach_from_approach_side = parsed_ap.get("from_approach_side")
            approach_turn_side = _compute_turn_side(
                approach_relation,
                approach_from_dir,
                pick_dir,
                approach_from_approach_side,
            )
            ap_tp = parsed_ap.get("turn_pivot")
            if isinstance(ap_tp, (list, tuple)) and len(ap_tp) >= 2:
                approach_turn_pivot = (int(ap_tp[0]), int(ap_tp[1]))
            approach_lanes = list(
                parsed_ap.get("carry_parallel_lanes", [])
                or parsed_ap.get("approach_parallel_lanes", [])
                or []
            )
            approach_main = list(
                parsed_ap.get("carry_main_route", [])
                or parsed_ap.get("approach_main_route", [])
                or []
            )
            approach_lanes = _unshift_lanes(approach_lanes, route_pad)
            approach_main = _unshift_lane(approach_main, route_pad)
            if isinstance(approach_turn_pivot, (list, tuple)) and len(approach_turn_pivot) >= 2:
                approach_turn_pivot = _unshift_cell(approach_turn_pivot, route_pad)
            approach_lanes = _filter_stepwise_lanes(approach_lanes)
            approach_main = _normalize_lane_cells(approach_main)
            if not _is_stepwise_route(approach_main):
                approach_main = []
            if parsed_ap.get("is_outer_fallback"):
                approach_main = []
                approach_lanes = []
                approach_turn_pivot = None

        raw_case = None
        fn = handlers.get(relation)
        if callable(fn):
            try:
                frozen_carry_base = _freeze_state(states[i + 1])
                frozen_carry = _pad_frozen(frozen_carry_base, route_pad)
                src_p = _shift_cell(src, route_pad)
                dst_p = _shift_cell(dst, route_pad)
                dst_was_empty = all(int(v) == 0 for v in states[i][dst[0]][dst[1]])
                raw_case = fn(
                    vehicle_cell=None,
                    from_cell=src_p,
                    to_cell=dst_p,
                    from_access_dir=pick_dir,
                    to_access_dir=place_dir,
                    node_frozen=frozen_carry,
                    ignore_to_block_for_egress=dst_was_empty,
                )
            except Exception:
                raw_case = None

        parsed = _normalize_route_case_output(raw_case)
        carry_lanes = _unshift_lanes(list(parsed.get("carry_parallel_lanes", []) or []), route_pad)
        carry_main = _unshift_lane(list(parsed.get("carry_main_route", []) or []), route_pad)
        carry_lanes = _filter_stepwise_lanes(carry_lanes)
        carry_main = _normalize_lane_cells(carry_main)
        turn_pivot = parsed.get("turn_pivot")
        if isinstance(turn_pivot, (list, tuple)) and len(turn_pivot) >= 2:
            turn_pivot = _unshift_cell(turn_pivot, route_pad)
        from_approach_side = parsed.get("from_approach_side")
        carry_turn_side = _compute_turn_side(relation, pick_dir, place_dir, from_approach_side)
        if not _is_stepwise_route(carry_main):
            carry_main = []

        pick_height_idx = int(mv.get("pick_height", 0))
        place_height_idx = int(mv.get("place_height", 0))
        src_h = _stack_height(states, i, src)
        dst_h = _stack_height(states, i, dst)
        pick_level = (src_h - pick_height_idx) if src_h > 0 else pick_height_idx
        place_level = (dst_h - place_height_idx) if dst_h > 0 else place_height_idx

        plans.append(
            {
                "relation": relation,
                "pick_direction": pick_dir,
                "place_direction": place_dir,
                "source": src,
                "target": dst,
                "item": int(mv.get("item", 0) or 0),
                "pick_height": pick_height_idx,
                "place_height": place_height_idx,
                "pick_level": int(pick_level),
                "place_level": int(place_level),
                "ok": bool(approach_main or carry_main),
                "approach_parallel_lanes": list(approach_lanes or []),
                "approach_main_route": list(approach_main or []),
                "approach_turn_pivot": approach_turn_pivot,
                "approach_turn_side": approach_turn_side,
                "approach_from_dir": approach_from_dir,
                "approach_relation": approach_relation,
                "carry_parallel_lanes": list(carry_lanes or []),
                "carry_main_route": list(carry_main or []),
                "turn_pivot": turn_pivot,
                "turn_side": carry_turn_side,
                "from_approach_side": from_approach_side,
            }
        )

    return plans


def build_anim_moves_from_plans(plans: Sequence[Dict]) -> List[Dict]:
    out: List[Dict] = []
    for plan in plans or []:
        if not isinstance(plan, dict):
            continue
        src = _to_cell(plan.get("source"))
        dst = _to_cell(plan.get("target"))
        if src is None or dst is None:
            continue
        out.append({
            "source": src,
            "target": dst,
            "item": int(plan.get("item", 0) or 0),
            "pick_direction": str(plan.get("pick_direction", "N") or "N"),
            "place_direction": str(plan.get("place_direction", "N") or "N"),
            "pick_height": int(plan.get("pick_height", 0) or 0),
            "place_height": int(plan.get("place_height", 0) or 0),
        })
    return out


def build_route_overlay_from_plan(plan: Dict) -> Dict:
    if not isinstance(plan, dict):
        return {}
    return {
        "source": plan.get("source"),
        "target": plan.get("target"),
        "pick_direction": plan.get("pick_direction"),
        "place_direction": plan.get("place_direction"),
        "approach_route": list(plan.get("approach_main_route") or []),
        "route": list(plan.get("carry_main_route") or []),
        "approach_parallel_lanes": list(plan.get("approach_parallel_lanes") or []),
        "carry_parallel_lanes": list(plan.get("carry_parallel_lanes") or []),
        "approach_turn_pivot": plan.get("approach_turn_pivot"),
        "turn_pivot": plan.get("turn_pivot"),
    }


def calculate_plan_time_from_animation(plan: Dict, time_params: Optional[Dict[str, Any]] = None) -> Dict:
    if not isinstance(plan, dict):
        return {"total_time": 0.0, "components": {}, "model": {"note": "empty plan"}}

    import contextlib
    import io

    from .route_animation import RouteAnimation

    anim = RouteAnimation(step_plans=[plan])
    anim.time_parameters = _animation_time_params(time_params)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            anim.talimat_hazirla()
    except Exception:
        return {"total_time": 0.0, "components": {}, "model": {"note": "instruction build failed"}}

    total = 0.0
    approach = 0.0
    carry = 0.0
    comps = {
        "time_approach_pick": 0.0,
        "time_carry_to_place": 0.0,
        "t_fork_prep": 0.0,
        "t_travel_approach": 0.0,
        "t_pick": 0.0,
        "t_lower_safe": 0.0,
        "t_travel_carry": 0.0,
        "t_reverse": 0.0,
        "t_raise_place": 0.0,
        "t_place": 0.0,
    }

    for q in list(getattr(anim, "talimat_queue", []) or []):
        try:
            sec = float(q.get("duration_s", 0.0) or 0.0)
        except Exception:
            sec = 0.0
        total += sec
        phase = str(q.get("phase", "") or "")
        text = str(q.get("text", "") or "")
        if phase == "approach":
            approach += sec
            if text.startswith("Git") or text.startswith("Yan Git") or text.startswith("Dön"):
                comps["t_travel_approach"] += sec
            elif text.startswith("Çatal Seviyesi"):
                comps["t_fork_prep"] += sec
            else:
                comps["t_pick"] += sec
        elif phase == "carry":
            carry += sec
            if text.startswith("Git") or text.startswith("Yan Git") or text.startswith("Dön"):
                comps["t_travel_carry"] += sec
            elif text.startswith("Bloğu Bırak") or text == "Yaklaş" or text == "Geri Çekil":
                comps["t_place"] += sec
            elif text.startswith("Çatal Seviyesi"):
                comps["t_raise_place"] += sec
            else:
                comps["t_lower_safe"] += sec

    comps["time_approach_pick"] = approach
    comps["time_carry_to_place"] = carry
    return {
        "total_time": float(total),
        "relation": plan.get("relation"),
        "pick_height": plan.get("pick_level", plan.get("pick_height")),
        "place_height": plan.get("place_level", plan.get("place_height")),
        "components": {k: float(v) for k, v in comps.items()},
        "metrics": {},
        "model": {
            "enabled": True,
            "note": "RouteAnimation instruction durations from route_cases plan",
        },
    }


def calculate_plan_times_from_animation(
    plans: Sequence[Dict],
    time_params: Optional[Dict[str, Any]] = None,
) -> Tuple[List[float], List[Dict]]:
    times: List[float] = []
    details: List[Dict] = []
    for plan in plans or []:
        info = calculate_plan_time_from_animation(plan, time_params)
        details.append(info)
        try:
            times.append(float(info.get("total_time", 0.0) or 0.0))
        except Exception:
            times.append(0.0)
    return times, details


def build_anim_moves(
    playback_moves: Sequence,
    move_paths: Sequence,
) -> List[Dict]:
    out: List[Dict] = []
    for i, mv in enumerate(playback_moves or []):
        try:
            sw, sl, tw, tl, item = mv
        except Exception:
            continue
        mp = (
            move_paths[i]
            if (move_paths is not None and i < len(move_paths) and isinstance(move_paths[i], dict))
            else {}
        )
        out.append({
            "source": (int(sw), int(sl)),
            "target": (int(tw), int(tl)),
            "item": int(item),
            "pick_direction": str(mp.get("pick_direction", "N") or "N"),
            "place_direction": str(mp.get("place_direction", "N") or "N"),
            "pick_height": int(mp.get("pick_height", 0) or 0),
            "place_height": int(mp.get("place_height", 0) or 0),
        })
    return out


def collect_block_actors_from_scene(scene, coords: Optional[Dict[str, float]] = None) -> Dict[Tuple[int, int, int], object]:
    out: Dict[Tuple[int, int, int], object] = {}
    coords = coords or {}
    try:
        x1 = float(coords.get("x1", 0.0))
        y1 = float(coords.get("y1", 0.0))
    except Exception:
        x1 = 0.0
        y1 = 0.0

    has_rect = "x2" in coords and "y2" in coords
    if has_rect:
        try:
            x2 = float(coords["x2"])
            y2 = float(coords["y2"])
            xmin, xmax = (x1, x2) if x1 <= x2 else (x2, x1)
            ymin, ymax = (y1, y2) if y1 <= y2 else (y2, y1)
        except Exception:
            has_rect = False

    for b in (getattr(scene, "_blocks", []) or []):
        try:
            px, py, pz = b.GetPosition()
        except Exception:
            continue
        if has_rect and not (xmin - 1e-3 <= px <= xmax + 1e-3 and ymin - 1e-3 <= py <= ymax + 1e-3):
            continue
        gx = int(round(px - x1 - 0.5))
        gy = int(round(py - y1 - 0.5))
        gz = int(round(pz - 0.5))
        out[(gx, gy, gz)] = b
    return out
