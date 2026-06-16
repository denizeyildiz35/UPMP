from typing import Dict, List, Optional, Tuple


class RouteAnimation:

    def __init__(
        self,
        step_plans=None,
        nudge_distance=1.2,
    ):

        self.step_plans = step_plans
        self.nudge_distance = float(nudge_distance)
        self.proper_step_plans = self.proper_step_plan_maker()

        self.forklift_first_location = None
        self.forklift_first_yaw = None
        self.forklift_location = None
        self.forklift_yaw = None  # sag tarafa bakiyorsa 0, sol 180, yukari 90, asagi 270
        self.fork_level = 1

        self._dir_point_actors = []
        self.forklift_front = 2.2
        self.forklift_back = 0.8

        self.dt = 1 / 60

        self.time_parameters = {
            "duz": 1,
            "strafe": 1.5,
            "donus(90)": 2,
            "bos_catal_cikis": 0.5,
            "bos_catal_inis": 0.4,
            "catal_cikis": 0.8,
            "catal_inis": 0.6,
            "pick": 2,
            "place": 2,
        }
        self.talimat_queue = []
        self._exec_queue = []
        self._exec_idx = 0
        self._active_cmd = None
        self._parallel_fork_cmd = None
        self._active_step = None

        self.forklift_actor = None
        self.forklift_parts = {}
        self._fork_carriage = None
        self._fork_levels = (0.0, 1.0, 2.0, 3.0)

        self._anim_ren = None
        self._anim_iren = None
        self._anim_timer_id = None
        self._anim_obs_id = None
        self._qt_anim_timer = None
        self._anim_paused = False
        self.speed = 1.0

        self._block_actors = {}
        self._carried_block_actor = None
        self._carried_block_offset = (0.0, 0.0)
        self._moves = []


    def remove_shared_points_across_lanes(self, lanes):
        counts = {}
        for lane in lanes:
            for pt in set(lane):
                counts[pt] = counts.get(pt, 0) + 1

        return [[pt for pt in lane if counts.get(pt, 0) == 1] for lane in lanes]


    def detect_neighbor_axis_turns(self, path):
        turns = []
        prev_axis = None

        for i in range(1, len(path)):
            x0, y0 = path[i - 1]
            x1, y1 = path[i]
            dx, dy = x1 - x0, y1 - y0

            if abs(dx) + abs(dy) != 1 or (dx != 0 and dy != 0):
                prev_axis = None
                continue

            curr_axis = "x" if dx != 0 else "y"

            if prev_axis is not None and curr_axis != prev_axis and i >= 2:
                ax, ay = path[i - 1][0] - path[i - 2][0], path[i - 1][1] - path[i - 2][1]  # giriş vektörü
                bx, by = path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]          # çıkış vektörü

                cross = ax * by - ay * bx  # z-bileşeni
                # Matematik koordinatı (y yukarı): cross>0 sola(CCW), cross<0 sağa(CW)
                turn_dir = "left" if cross > 0 else ("right" if cross < 0 else "straight")

                turns.append({
                    "turn_at_index": i - 1,
                    "turn_point": path[i - 1],
                    "from_axis": prev_axis,
                    "to_axis": curr_axis,
                    "turn_dir_math": turn_dir,
                })

            prev_axis = curr_axis

        return turns

    def proper_step_plan_maker(self):
        liste = []
        for plan in (self.step_plans or []):
            if not isinstance(plan, dict):
                continue

            carry_main = list(plan.get("carry_main_route") or [])
            approach_main = list(plan.get("approach_main_route") or [])


            tp = plan.get("turn_pivot")
            turn_pivot = (int(tp[0]), int(tp[1])) if isinstance(tp, (list, tuple)) and len(tp) >= 2 else None
            turn_side = str(plan.get("turn_side", "")).strip().lower()
          
            if turn_side not in ("left", "right"):
                turn_side = None


            from_approach_side = plan.get("from_approach_side")
            ap_tp = plan.get("approach_turn_pivot")
            approach_turn_pivot = (int(ap_tp[0]), int(ap_tp[1])) if isinstance(ap_tp, (list, tuple)) and len(ap_tp) >= 2 else None

            liste.append(
              [{
                  "relation": plan.get("relation"),
                  "pick_direction": plan.get("pick_direction"),
                  "place_direction": plan.get("place_direction"),
                  "source": plan.get("source"),
                  "target": plan.get("target"),
                  "pick_height": plan.get("pick_height", 0),
                  "place_height": plan.get("place_height", 0),
                  "pick_level": plan.get("pick_level", plan.get("pick_height", 0)),
                  "place_level": plan.get("place_level", plan.get("place_height", 0)),
                  "approach_main_route": approach_main,
                  "carry_main_route": carry_main,
                  "turn_pivot": turn_pivot,
                  "turn_side": turn_side,
                  "from_approach_side": from_approach_side,
                  "approach_turn_pivot": approach_turn_pivot,
                  "approach_turn_side": plan.get("approach_turn_side"),
                  "approach_from_dir": plan.get("approach_from_dir"),
                  "approach_relation": plan.get("approach_relation"),
              }]
          )
        

        return liste


    def spawn_forklift(self, ren, moves, current_idx, spawn_distance=1.0):
        from vtkmodules.vtkFiltersSources import vtkCubeSource
        from vtkmodules.vtkRenderingCore import vtkActor, vtkAssembly, vtkPolyDataMapper

        if self.forklift_actor is not None:
            try:
                ren.RemoveActor(self.forklift_actor)
            except Exception:
                pass
            self.forklift_actor = None

        try:
            dist = abs(float(spawn_distance))
        except Exception:
            dist = 1.0

        # Spawn in front of the source block by user-defined distance.
        _access_delta = {"N": (0.0, dist), "S": (0.0, -dist), "E": (dist, 0.0), "W": (-dist, 0.0)}
        _access_yaw = {"N": -90.0, "S": 90.0, "E": 180.0, "W": 0.0}

        try:
            move_idx = int(current_idx) - 1 if int(current_idx) > 0 else 0
        except Exception:
            move_idx = 0

        fork_src = None
        fork_pick_dir = "N"
        if moves and 0 <= move_idx < len(moves):
            mv = moves[move_idx]
            fork_src = mv.get("source")
            fork_pick_dir = str(mv.get("pick_direction", "N") or "").strip().upper()
        elif moves:
            mv = moves[0]
            fork_src = mv.get("source")
            fork_pick_dir = str(mv.get("pick_direction", "N") or "").strip().upper()

        if fork_src is None:
            return

        if fork_pick_dir not in _access_delta:
            fork_pick_dir = "N"
        dx, dy = _access_delta[fork_pick_dir]
        yaw = _access_yaw[fork_pick_dir]
        fx = float(fork_src[0]) + 0.5 + dx
        fy = float(fork_src[1]) + 0.5 + dy

        def _box(size, pos, color):
            src = vtkCubeSource()
            src.SetXLength(float(size[0]))
            src.SetYLength(float(size[1]))
            src.SetZLength(float(size[2]))
            src.SetCenter(0.0, 0.0, 0.0)
            src.Update()

            mapper = vtkPolyDataMapper()
            mapper.SetInputConnection(src.GetOutputPort())

            actor = vtkActor()
            actor.SetMapper(mapper)
            actor.SetPosition(float(pos[0]), float(pos[1]), float(pos[2]))
            prop = actor.GetProperty()
            prop.SetColor(float(color[0]), float(color[1]), float(color[2]))
            prop.SetAmbient(0.25)
            prop.SetDiffuse(0.75)
            prop.SetEdgeVisibility(True)
            prop.SetEdgeColor(0.05, 0.05, 0.05)
            actor.SetPickable(False)
            return actor

        fork_assembly = vtkAssembly()
        body = _box((1.45, 0.92, 0.42), (-0.25, 0.0, 0.34), (0.95, 0.68, 0.18))
        cabin = _box((0.56, 0.72, 0.58), (-0.58, 0.0, 0.86), (0.16, 0.20, 0.25))
        mast_left = _box((0.12, 0.08, 2.65), (0.50, -0.34, 1.35), (0.04, 0.04, 0.045))
        mast_right = _box((0.12, 0.08, 2.65), (0.50, 0.34, 1.35), (0.04, 0.04, 0.045))
        fork_carriage = vtkAssembly()
        carriage_bar = _box((0.16, 0.86, 0.18), (0.64, 0.0, 0.0), (0.03, 0.03, 0.035))
        fork_left = _box((1.18, 0.10, 0.08), (1.22, -0.28, -0.12), (0.02, 0.02, 0.025))
        fork_right = _box((1.18, 0.10, 0.08), (1.22, 0.28, -0.12), (0.02, 0.02, 0.025))
        fork_carriage.AddPart(carriage_bar)
        fork_carriage.AddPart(fork_left)
        fork_carriage.AddPart(fork_right)
        fork_carriage.SetPosition(0.0, 0.0, 0.0)
        for part in (body, cabin, mast_left, mast_right, fork_carriage):
            fork_assembly.AddPart(part)

        self.forklift_actor = fork_assembly
        self.forklift_parts = {}
        self._fork_carriage = fork_carriage
        self._fork_levels = (0.0, 1.0, 2.0, 3.0)

        fork_assembly.SetUserTransform(None)
        fork_assembly.SetPosition(float(fx), float(fy), 0.0)
        fork_assembly.SetOrientation(0.0, 0.0, float(yaw))
        ren.AddActor(fork_assembly)

        self.forklift_first_location = (fx, fy)
        self.forklift_first_yaw = yaw
        self.forklift_location = (fx, fy)
        self.forklift_yaw = yaw
        self._set_fork_level_visual(float(self.fork_level))

        print(self.forklift_first_location)
        print(self.forklift_first_yaw)

    def draw_forward_backward_points(self, ren, forward_m=1.0, backward_m=1.0):
        import math
        import vtk

        if self.forklift_location is None or self.forklift_yaw is None:
            return

        # Onceki cizimler birikmesin.
        for actor in self._dir_point_actors:
            try:
                ren.RemoveActor(actor)
            except Exception:
                pass
        self._dir_point_actors = []

        x, y = self.forklift_location
        yaw_rad = math.radians(float(self.forklift_yaw))
        vx = math.cos(yaw_rad)
        vy = math.sin(yaw_rad)

        forward_pt = (x + vx * float(forward_m), y + vy * float(forward_m), 0.15)
        backward_pt = (x - vx * float(backward_m), y - vy * float(backward_m), 0.15)

        def _make_point_actor(pt, rgb):
            src = vtk.vtkSphereSource()
            src.SetRadius(0.06)
            src.SetThetaResolution(24)
            src.SetPhiResolution(24)
            src.SetCenter(pt[0], pt[1], pt[2])

            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(src.GetOutputPort())

            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            actor.GetProperty().SetColor(rgb[0], rgb[1], rgb[2])
            actor.GetProperty().SetAmbient(0.25)
            actor.GetProperty().SetDiffuse(0.75)
            return actor

        actor_forward = _make_point_actor(forward_pt, (0.2, 0.9, 0.2))
        actor_backward = _make_point_actor(backward_pt, (0.9, 0.25, 0.25))

        ren.AddActor(actor_forward)
        ren.AddActor(actor_backward)
        self._dir_point_actors.extend([actor_forward, actor_backward])

    def talimat_hazirla(self):
        _opp = {"N": "S", "S": "N", "E": "W", "W": "E"}
        _idx = {"N": 0, "E": 1, "S": 2, "W": 3}
        _dirs = ["N", "E", "S", "W"]
        _dir_tr = {"N": "kuzey", "S": "güney", "E": "doğu", "W": "batı"}
        _vec_dir = {(0, 1): "N", (0, -1): "S", (1, 0): "E", (-1, 0): "W"}

        def _rotate(facing, side, deg):
            steps = (1 if side == "right" else -1) * (deg // 90)
            return _dirs[(_idx.get(facing, 0) + steps) % 4]

        def _seg_type(move_dir, facing):
            diff = (_idx.get(move_dir, 0) - _idx.get(facing, 0)) % 4
            return {0: "düz", 2: "geri", 1: "sağ_yan", 3: "sol_yan"}[diff]

        def _route_instrs(route, facing, extra_end=0):
            instrs = []
            if len(route) < 2:
                return instrs
            cur_d, cur_n = None, 0
            for i in range(1, len(route)):
                dx = int(route[i][0]) - int(route[i - 1][0])
                dy = int(route[i][1]) - int(route[i - 1][1])
                d = _vec_dir.get((dx, dy))
                if d is None:
                    continue
                if d == cur_d:
                    cur_n += 1
                else:
                    if cur_d:
                        instrs.append((_seg_type(cur_d, facing), cur_n, _dir_tr[cur_d]))
                    cur_d, cur_n = d, 1
            if cur_d:
                instrs.append((_seg_type(cur_d, facing), cur_n + extra_end, _dir_tr[cur_d]))
            return instrs

        def _split(route, pivot):
            if pivot is None:
                return list(route), []
            tp = (int(pivot[0]), int(pivot[1]))
            for i, c in enumerate(route):
                if (int(c[0]), int(c[1])) == tp:
                    # Keep pivot as the first point of post so pivot->next step is counted.
                    return list(route[:i + 1]), list(route[i:])
            return list(route), []

        all_steps = []
        for adim_list in self.proper_step_plans:
            adim = adim_list[0]
            relation = adim.get("relation", "same")
            pick_dir = adim.get("pick_direction", "N")
            pick_level = adim.get("pick_level", adim.get("pick_height", 0))
            place_level = adim.get("place_level", adim.get("place_height", 0))
            # Talimatlar yalnızca main route'lardan üretilir.
            approach_route = adim.get("approach_main_route") or []
            carry_route = adim.get("carry_main_route") or []
            approach_from_dir = adim.get("approach_from_dir") or pick_dir
            approach_relation = adim.get("approach_relation", "same")
            approach_turn_pivot = adim.get("approach_turn_pivot")
            approach_turn_side = adim.get("approach_turn_side")
            carry_turn_pivot = adim.get("turn_pivot")
            carry_turn_side = adim.get("turn_side")

            instrs = []
            instrs.append(("fork_yükselt", pick_level))

            if approach_route:
                facing = _opp.get(approach_from_dir, "S")
                pre, post = _split(approach_route, approach_turn_pivot)
                instrs.extend(_route_instrs(pre, facing))
                if approach_turn_side and post:
                    deg = 180 if approach_relation == "opposite" else 90
                    instrs.append(("dön", deg, approach_turn_side, approach_turn_pivot))
                    facing = _rotate(facing, approach_turn_side, deg)
                    instrs.extend(_route_instrs(post, facing))

            instrs.append(("fork_al",))
            instrs.append(("fork_indir", 1))

            if carry_route:
                facing = _opp.get(pick_dir, "S")
                pre, post = _split(carry_route, carry_turn_pivot)
                instrs.extend(_route_instrs(pre, facing))
                if carry_turn_side and post:
                    deg = 180 if relation == "opposite" else 90
                    instrs.append(("dön", deg, carry_turn_side, carry_turn_pivot))
                    facing = _rotate(facing, carry_turn_side, deg)
                    instrs.extend(_route_instrs(post, facing))

            instrs.append(("fork_yükselt", place_level))
            instrs.append(("fork_birak",))

            all_steps.append(instrs)

        def _fmt_with_duration(instr, fork_level, phase):
            tag = instr[0]
            tp = self.time_parameters

            if tag in ("fork_yükselt", "fork_indir"):
                target_level = int(instr[1])
                diff = target_level - int(fork_level)
                is_approach = str(phase) == "approach"
                up_key = "bos_catal_cikis" if is_approach else "catal_cikis"
                down_key = "bos_catal_inis" if is_approach else "catal_inis"
                if diff > 0:
                    sec = float(tp.get(up_key, 0.0)) * diff
                elif diff < 0:
                    sec = float(tp.get(down_key, 0.0)) * abs(diff)
                else:
                    sec = 0.0
                return [(f"Çatal Seviyesi {target_level}", sec)], target_level

            if tag == "fork_al":
                move_sec = float(tp.get("pick", 0.0)) / 2.0
                pick_sec = float(tp.get("pick", 0.0))
                return [("Yaklaş", move_sec), ("Bloğu Al", pick_sec), ("Geri Çekil", move_sec)], fork_level

            if tag == "fork_birak":
                move_sec = float(tp.get("place", 0.0)) / 2.0
                place_sec = float(tp.get("place", 0.0))
                return [("Yaklaş", move_sec), ("Bloğu Bırak", place_sec), ("Geri Çekil", move_sec)], fork_level

            if tag == "düz":
                sec = float(tp.get("duz", 0.0)) * int(instr[1])
                return [(f"Git, {instr[1]}, {instr[2].title()}", sec)], fork_level

            if tag == "geri":
                sec = float(tp.get("duz", 0.0)) * int(instr[1])
                return [(f"Git, Geri, {instr[1]}, {instr[2].title()}", sec)], fork_level

            if tag == "sağ_yan":
                sec = float(tp.get("strafe", 0.0)) * int(instr[1])
                return [(f"Yan Git, Sağ Yan, {instr[1]}, {instr[2].title()}", sec)], fork_level

            if tag == "sol_yan":
                sec = float(tp.get("strafe", 0.0)) * int(instr[1])
                return [(f"Yan Git, Sol Yan, {instr[1]}, {instr[2].title()}", sec)], fork_level

            if tag == "dön":
                sec = float(tp.get("donus(90)", 0.0)) * (float(instr[1]) / 90.0)
                pivot = instr[3] if len(instr) > 3 and instr[3] is not None else None
                if pivot is not None:
                    text = f"Dön, {instr[1]}, {instr[2]}, {int(pivot[0])}, {int(pivot[1])}"
                else:
                    text = f"Dön, {instr[1]}, {instr[2]}"
                return [(text, sec)], fork_level

            return [(str(instr), 0.0)], fork_level

        self.talimat_queue = []
        print("\n=== TALİMAT PLANLARI ===")
        fork_level = int(self.fork_level)
        print(f"Başlangıç Çatal Seviyesi: {fork_level}")
        for i, step_instrs in enumerate(all_steps, 1):
            print(f"\n--- Adım {i}")
            split_idx = next((j for j, ins in enumerate(step_instrs) if ins[0] == "fork_al"), None)
            approach_instrs = step_instrs[:split_idx + 1] if split_idx is not None else step_instrs
            carry_instrs = step_instrs[split_idx + 1:] if split_idx is not None else []
            print("--- Approach")
            approach_entries = []
            for instr in approach_instrs:
                lines, fork_level = _fmt_with_duration(instr, fork_level, "approach")
                for line, sec in lines:
                    approach_entries.append(
                        {"line": line, "sec": float(sec), "real_sec": float(sec), "tag": str(instr[0]), "note": ""}
                    )

            # If initial fork-change can be completed while driving approach route,
            # show it as 0 s (handled in parallel).
            first_fork_idx = next(
                (
                    idx
                    for idx, ent in enumerate(approach_entries)
                    if ent["tag"] in ("fork_yükselt", "fork_indir")
                ),
                None,
            )
            if first_fork_idx is not None:
                route_total = sum(
                    ent["sec"]
                    for ent in approach_entries
                    if ent["tag"] in ("düz", "geri", "sağ_yan", "sol_yan", "dön")
                )
                if approach_entries[first_fork_idx]["sec"] < route_total:
                    real_sec = float(approach_entries[first_fork_idx]["real_sec"])
                    approach_entries[first_fork_idx]["sec"] = 0.0
                    approach_entries[first_fork_idx]["note"] = (
                        f" (toplamdan küçük diye 0 yazıldı, gerçek süre: {real_sec:.2f} sn)"
                    )

            for ent in approach_entries:
                self.talimat_queue.append(
                    {
                        "step": i,
                        "phase": "approach",
                        "text": ent["line"],
                        "duration_s": ent["sec"],
                        "real_duration_s": ent["real_sec"],
                        "note": ent["note"],
                        "raw_tag": ent["tag"],
                    }
                )
                print(f"  {ent['line']} | Süre: {ent['sec']:.2f} sn{ent['note']}")
            if carry_instrs:
                print("--- Carry")
                for instr in carry_instrs:
                    lines, fork_level = _fmt_with_duration(instr, fork_level, "carry")
                    for line, sec in lines:
                        self.talimat_queue.append(
                            {
                                "step": i,
                                "phase": "carry",
                                "text": line,
                                "duration_s": float(sec),
                                "real_duration_s": float(sec),
                                "note": "",
                                "raw_tag": str(instr[0]),
                            }
                        )
                        print(f"  {line} | Süre: {sec:.2f} sn")
            print("---")

        return all_steps

    def _norm_text(self, s: str) -> str:
        return str(s or "").strip().lower()

    def _dir_from_tr(self, s: str) -> Optional[Tuple[float, float]]:
        k = self._norm_text(s)
        mapping = {
            "dogu": (1.0, 0.0),
            "doğu": (1.0, 0.0),
            "bati": (-1.0, 0.0),
            "batı": (-1.0, 0.0),
            "kuzey": (0.0, 1.0),
            "guney": (0.0, -1.0),
            "güney": (0.0, -1.0),
        }
        return mapping.get(k)

    def _set_fork_level_visual(self, level_value: float):
        if self._fork_carriage is None:
            self.fork_level = float(level_value)
            return
        levels = tuple(float(v) for v in (self._fork_levels or (0.0, 0.45, 0.90, 1.35)))
        if not levels:
            self.fork_level = float(level_value)
            return

        lv = max(1.0, min(float(len(levels)), float(level_value)))
        lo = int(lv)
        hi = min(lo + 1, len(levels))
        frac = lv - float(lo)
        z0 = levels[lo - 1]
        z1 = levels[hi - 1]
        z = z0 + (z1 - z0) * frac

        x, y, _ = self._fork_carriage.GetPosition()
        self._fork_carriage.SetPosition(float(x), float(y), float(z))
        self._fork_carriage.Modified()
        self.fork_level = float(level_value)

    def _apply_forklift_pose(self, x: float, y: float, yaw: float):
        self.forklift_location = (float(x), float(y))
        self.forklift_yaw = float(yaw)
        if self.forklift_actor is None:
            return

        self.forklift_actor.SetUserTransform(None)
        self.forklift_actor.SetPosition(float(x), float(y), 0.0)
        self.forklift_actor.SetOrientation(0.0, 0.0, float(yaw))
        self.forklift_actor.Modified()

    def _parse_talimat_queue(self) -> List[Dict]:
        out: List[Dict] = []
        for q in (self.talimat_queue or []):
            text = str(q.get("text", "")).strip()
            note = str(q.get("note", "") or "")
            dur = float(q.get("duration_s", 0.0) or 0.0)
            real_dur = float(q.get("real_duration_s", dur) or dur)
            phase = str(q.get("phase", "") or "")

            cmd = {
                "step": q.get("step"),
                "phase": phase,
                "text": text,
                "note": note,
                "duration_s": dur,
                "real_duration_s": real_dur,
                "kind": "wait",
            }

            if text.startswith("Çatal Seviyesi"):
                parts = text.split()
                try:
                    cmd["kind"] = "fork_level"
                    cmd["target_level"] = float(int(parts[-1]))
                except Exception:
                    pass
            elif text == "Yaklaş":
                cmd["kind"] = "nudge"
                cmd["distance"] = self.nudge_distance
            elif text == "Geri Çekil":
                cmd["kind"] = "nudge"
                cmd["distance"] = -self.nudge_distance
            elif text in ("Bloğu Al", "Bloğu Bırak"):
                cmd["kind"] = "dwell"
            elif text.startswith("Dön,"):
                parts = [p.strip() for p in text.split(",")]
                if len(parts) >= 3:
                    try:
                        cmd["kind"] = "turn"
                        cmd["deg"] = float(parts[1])
                        cmd["side"] = self._norm_text(parts[2])
                        if len(parts) >= 5 and parts[3] and parts[4]:
                            cmd["pivot_world"] = (int(parts[3]) + 0.5, int(parts[4]) + 0.5)
                    except Exception:
                        pass
            elif text.startswith("Git, Geri,"):
                parts = [p.strip() for p in text.split(",")]
                if len(parts) >= 4:
                    try:
                        cmd["kind"] = "move_abs"
                        cmd["blocks"] = float(int(parts[2]))
                        cmd["dir"] = parts[3]
                    except Exception:
                        pass
            elif text.startswith("Git,"):
                parts = [p.strip() for p in text.split(",")]
                if len(parts) >= 3:
                    try:
                        cmd["kind"] = "move_abs"
                        cmd["blocks"] = float(int(parts[1]))
                        cmd["dir"] = parts[2]
                    except Exception:
                        pass
            elif text.startswith("Yan Git,"):
                parts = [p.strip() for p in text.split(",")]
                if len(parts) >= 4:
                    try:
                        cmd["kind"] = "move_abs"
                        cmd["blocks"] = float(int(parts[2]))
                        cmd["dir"] = parts[3]
                    except Exception:
                        pass

            out.append(cmd)
        return out

    def _build_runtime_cmd(self, cmd: Dict, use_real_duration: bool = False) -> Dict:
        import math

        c = dict(cmd)
        c["elapsed_s"] = 0.0
        c["anim_duration_s"] = float(c.get("real_duration_s", 0.0) if use_real_duration else c.get("duration_s", 0.0))
        c["start_pos"] = tuple(self.forklift_location or self.forklift_first_location or (0.0, 0.0))
        c["start_yaw"] = float(self.forklift_yaw if self.forklift_yaw is not None else 0.0)
        c["start_level"] = float(self.fork_level)

        kind = c.get("kind")
        if kind == "move_abs":
            vec = self._dir_from_tr(c.get("dir", ""))
            if vec is None:
                vec = (0.0, 0.0)
            dist = float(c.get("blocks", 0.0))
            sx, sy = c["start_pos"]
            c["target_pos"] = (sx + vec[0] * dist, sy + vec[1] * dist)
        elif kind == "nudge":
            sx, sy = c["start_pos"]
            yaw = math.radians(c["start_yaw"])
            dist = float(c.get("distance", 0.0))
            c["target_pos"] = (sx + math.cos(yaw) * dist, sy + math.sin(yaw) * dist)
        elif kind == "turn":
            deg = float(c.get("deg", 0.0))
            side = self._norm_text(c.get("side", ""))
            sign = -1.0 if side == "right" else 1.0
            c["target_yaw"] = c["start_yaw"] + sign * deg
            c["turn_sign"] = sign
        elif kind == "fork_level":
            c["target_level"] = float(c.get("target_level", c["start_level"]))
        return c

    def _advance_runtime_cmd(self, c: Dict, dt: float) -> bool:
        dur = max(0.0, float(c.get("anim_duration_s", 0.0)))
        c["elapsed_s"] = float(c.get("elapsed_s", 0.0)) + float(dt)
        t = 1.0 if dur <= 1e-9 else min(1.0, c["elapsed_s"] / dur)
        kind = c.get("kind")

        if kind in ("move_abs", "nudge"):
            sx, sy = c.get("start_pos", (0.0, 0.0))
            tx, ty = c.get("target_pos", (sx, sy))
            x = sx + (tx - sx) * t
            y = sy + (ty - sy) * t
            self._apply_forklift_pose(x, y, float(c.get("start_yaw", 0.0)))
        elif kind == "turn":
            import math
            syaw = float(c.get("start_yaw", 0.0))
            tyaw = float(c.get("target_yaw", syaw))
            yaw = syaw + (tyaw - syaw) * t
            pivot = c.get("pivot_world")
            if pivot is not None:
                px, py = pivot
                sx, sy = c.get("start_pos", (0.0, 0.0))
                angle = math.radians(float(c.get("turn_sign", 1.0)) * float(c.get("deg", 0.0)) * t)
                rx, ry = sx - px, sy - py
                x = px + rx * math.cos(angle) - ry * math.sin(angle)
                y = py + rx * math.sin(angle) + ry * math.cos(angle)
            else:
                x, y = c.get("start_pos", (0.0, 0.0))
            self._apply_forklift_pose(x, y, yaw)
        elif kind == "fork_level":
            slev = float(c.get("start_level", 1.0))
            tlev = float(c.get("target_level", slev))
            lev = slev + (tlev - slev) * t
            self._set_fork_level_visual(lev)

        return t >= 1.0

    def _start_next_exec_cmd(self):
        while self._exec_idx < len(self._exec_queue):
            cmd = self._exec_queue[self._exec_idx]
            self._exec_idx += 1

            is_approach_overlap = (
                str(cmd.get("phase", "")) == "approach"
                and str(cmd.get("kind", "")) == "fork_level"
                and float(cmd.get("duration_s", 0.0)) <= 1e-9
                and float(cmd.get("real_duration_s", 0.0)) > 1e-9
                and "toplamdan küçük" in str(cmd.get("note", ""))
            )
            if is_approach_overlap:
                self._parallel_fork_cmd = self._build_runtime_cmd(cmd, use_real_duration=True)
                continue

            runtime_cmd = self._build_runtime_cmd(cmd, use_real_duration=False)
            if float(runtime_cmd.get("anim_duration_s", 0.0)) <= 1e-9:
                self._advance_runtime_cmd(runtime_cmd, 1e9)
                continue
            self._active_cmd = runtime_cmd
            self._active_step = runtime_cmd.get("step")
            return

        self._active_cmd = None
        self._active_step = None

    def _stop_animation_timer(self):
        try:
            if self._qt_anim_timer is not None:
                self._qt_anim_timer.stop()
        except Exception:
            pass

        if self._anim_iren is None:
            self._anim_ren = None
            return
        try:
            if self._anim_timer_id is not None:
                self._anim_iren.DestroyTimer(self._anim_timer_id)
        except Exception:
            pass
        try:
            if self._anim_obs_id is not None:
                self._anim_iren.RemoveObserver(self._anim_obs_id)
        except Exception:
            pass
        self._anim_timer_id = None
        self._anim_obs_id = None
        self._anim_iren = None
        self._anim_ren = None

    def toggle_pause(self) -> bool:
        self._anim_paused = not self._anim_paused
        return self._anim_paused

    def _on_anim_timer(self, obj, _ev):
        if self._anim_ren is None or self._anim_iren is None:
            self._stop_animation_timer()
            return
        if self._anim_paused:
            return

        dt = float(self.dt) * max(0.1, float(self.speed))

        if self._active_cmd is not None:
            done = self._advance_runtime_cmd(self._active_cmd, dt)
            if done:
                finished_cmd = self._active_cmd
                self._active_cmd = None
                self._on_cmd_finished(finished_cmd)
                self._start_next_exec_cmd()
        else:
            self._start_next_exec_cmd()

        self._update_carried_block()

        if self._parallel_fork_cmd is not None:
            p_done = self._advance_runtime_cmd(self._parallel_fork_cmd, dt)
            if p_done:
                self._parallel_fork_cmd = None

        if (
            self._active_cmd is None
            and self._parallel_fork_cmd is None
            and self._exec_idx >= len(self._exec_queue)
        ):
            self._stop_animation_timer()
            return

        try:
            if self._anim_ren is not None and self._anim_ren.GetRenderWindow() is not None:
                self._anim_ren.GetRenderWindow().Render()
        except Exception:
            self._stop_animation_timer()

    def _get_current_fork_z(self) -> float:
        levels = tuple(float(v) for v in (self._fork_levels or (0.0, 1.0, 2.0, 3.0)))
        if not levels:
            return 0.0
        lv = max(1.0, min(float(len(levels)), float(self.fork_level)))
        lo = int(lv)
        hi = min(lo + 1, len(levels))
        frac = lv - float(lo)
        return levels[lo - 1] + (levels[hi - 1] - levels[lo - 1]) * frac

    def _on_cmd_finished(self, cmd: Dict):
        text = str(cmd.get("text", ""))
        step = cmd.get("step")
        if step is None:
            return
        if text == "Bloğu Al":
            self._pick_block(int(step))
        elif text == "Bloğu Bırak":
            self._place_block(int(step))

    def _pick_block(self, step: int):
        import math
        if step < 1 or step > len(self.proper_step_plans):
            return
        adim = self.proper_step_plans[step - 1][0]
        source = adim.get("source")
        phys_z = int(adim.get("pick_level", 1)) - 1
        if source is None:
            return
        sx, sy = int(source[0]), int(source[1])
        actor = self._block_actors.get((sx, sy, phys_z))
        if actor is None:
            return
        fx, fy = self.forklift_location or (0.0, 0.0)
        yaw_rad = math.radians(-(self.forklift_yaw or 0.0))
        dx = float(sx) + 0.5 - fx
        dy = float(sy) + 0.5 - fy
        self._carried_block_offset = (
            dx * math.cos(yaw_rad) - dy * math.sin(yaw_rad),
            dx * math.sin(yaw_rad) + dy * math.cos(yaw_rad),
        )
        self._carried_block_actor = actor
        del self._block_actors[(sx, sy, phys_z)]

    def _update_carried_block(self):
        import math
        if self._carried_block_actor is None:
            return
        fx, fy = self.forklift_location or (0.0, 0.0)
        yaw_rad = math.radians(self.forklift_yaw or 0.0)
        lx, ly = self._carried_block_offset
        wx = fx + lx * math.cos(yaw_rad) - ly * math.sin(yaw_rad)
        wy = fy + lx * math.sin(yaw_rad) + ly * math.cos(yaw_rad)
        self._carried_block_actor.SetPosition(float(wx), float(wy), self._get_current_fork_z() + 0.5)
        self._carried_block_actor.SetOrientation(0.0, 0.0, float(self.forklift_yaw or 0.0))
        self._carried_block_actor.Modified()

    def _place_block(self, step: int):
        if self._carried_block_actor is None:
            return
        if step < 1 or step > len(self.proper_step_plans):
            return
        adim = self.proper_step_plans[step - 1][0]
        target = adim.get("target")
        phys_z = int(adim.get("place_level", 1)) - 1
        if target is None:
            return
        tx, ty = int(target[0]), int(target[1])
        self._carried_block_actor.SetPosition(float(tx) + 0.5, float(ty) + 0.5, float(phys_z) + 0.5)
        self._carried_block_actor.Modified()
        self._block_actors[(tx, ty, phys_z)] = self._carried_block_actor
        self._carried_block_actor = None
        self._carried_block_offset = (0.0, 0.0)

    def _on_qt_anim_tick(self):
        self._on_anim_timer(None, None)

    def animation_start(self, ren):
        if ren is None:
            return
        ren_win = ren.GetRenderWindow() if hasattr(ren, "GetRenderWindow") else None
        iren = ren_win.GetInteractor() if ren_win is not None else None
        if iren is None:
            print("Animasyon başlatılamadı: interactor bulunamadı.")
            return

        self._stop_animation_timer()
        self._anim_ren = ren
        self._anim_iren = iren

        self._exec_queue = self._parse_talimat_queue()
        self._exec_idx = 0
        self._active_cmd = None
        self._parallel_fork_cmd = None
        self._active_step = None
        self._anim_paused = False
        if not self._exec_queue:
            print("Animasyon kuyruğu boş.")
            return

        print(f"Animasyon başlatıldı. Komut sayısı: {len(self._exec_queue)}")
        self._start_next_exec_cmd()
        try:
            if self._anim_ren is not None and self._anim_ren.GetRenderWindow() is not None:
                self._anim_ren.GetRenderWindow().Render()
        except Exception:
            pass
        started = False
        try:
            from PySide6.QtCore import QTimer

            if self._qt_anim_timer is None:
                self._qt_anim_timer = QTimer()
                self._qt_anim_timer.timeout.connect(self._on_qt_anim_tick)
            self._qt_anim_timer.setInterval(int(max(1, round(self.dt * 1000.0))))
            self._qt_anim_timer.start()
            started = True
        except Exception:
            started = False

        if not started:
            self._anim_obs_id = iren.AddObserver("TimerEvent", self._on_anim_timer, 1.0)
            self._anim_timer_id = iren.CreateRepeatingTimer(int(max(1, round(self.dt * 1000.0))))

    def run(self, ren, moves, current_idx, block_actors=None):
        self._block_actors = dict(block_actors or {})
        self._moves = list(moves or [])
        self._carried_block_actor = None
        self._carried_block_offset = (0.0, 0.0)
        self.spawn_forklift(ren, moves, current_idx, spawn_distance=2.8)
        self.draw_forward_backward_points(ren, forward_m=2.2, backward_m=0.8)
        self.talimat_hazirla()
        self.animation_start(ren)
