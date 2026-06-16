def _priority_color(value):
    palette = {
        1: (0.86, 0.18, 0.18),
        2: (0.20, 0.62, 0.28),
        3: (0.18, 0.36, 0.82),
        4: (0.86, 0.62, 0.16),
        5: (0.55, 0.32, 0.72),
    }
    return palette.get(int(value), (0.72, 0.74, 0.78))


class SimpleVTKScene:
    def __init__(self, renderer, padding=5):
        self.renderer = renderer
        self._actors = []
        self._blocks = []
        self._route_actors = []
        self._highlight_actors = []
        self._access_actor = None
        self.padding = int(padding)

    def clear(self):
        for actor in list(self._actors):
            try:
                self.renderer.RemoveActor(actor)
            except Exception:
                pass
        self._actors.clear()
        self._blocks.clear()
        self.clear_route_overlay()
        self.clear_cell_highlights()
        self.clear_access_directions()

    def clear_route_overlay(self):
        for actor in list(self._route_actors):
            try:
                self.renderer.RemoveActor(actor)
            except Exception:
                pass
        self._route_actors.clear()

    def clear_cell_highlights(self):
        for actor in list(self._highlight_actors):
            try:
                self.renderer.RemoveActor(actor)
            except Exception:
                pass
        self._highlight_actors.clear()

    def clear_access_directions(self):
        if self._access_actor is not None:
            try:
                self.renderer.RemoveActor(self._access_actor)
            except Exception:
                pass
            self._access_actor = None

    def render_state(self, state_matrix, reset_camera=True):
        self.clear()
        if not state_matrix:
            return
        width = len(state_matrix)
        length = len(state_matrix[0]) if state_matrix else 0
        self._add_floor(width, length)
        self._add_blocks(state_matrix)
        if reset_camera:
            self._reset_camera(width, length)

    def _add_actor(self, actor):
        self.renderer.AddActor(actor)
        self._actors.append(actor)
        return actor

    def collect_anim_block_actors(self):
        out = {}
        for actor in list(self._blocks):
            try:
                gx, gy, phys_z = actor.anim_grid_position
            except Exception:
                continue
            out[(int(gx), int(gy), int(phys_z))] = actor
        return out

    def _add_route_actor(self, actor):
        self.renderer.AddActor(actor)
        self._route_actors.append(actor)
        return actor

    def _add_highlight_actor(self, actor):
        self.renderer.AddActor(actor)
        self._highlight_actors.append(actor)
        return actor

    def add_move_highlights(self, move, state_before, move_direction=None):
        self.clear_cell_highlights()
        if move is None or not state_before:
            return
        try:
            sx, sy, tx, ty, _item = move
        except Exception:
            return
        pick_height = None
        place_height = None
        if isinstance(move_direction, dict):
            try:
                pick_height = int(move_direction.get("pick_height"))
            except Exception:
                pick_height = None
            try:
                place_height = int(move_direction.get("place_height"))
            except Exception:
                place_height = None
        self._add_cell_highlight((sx, sy), self._stack_z_for_source(state_before, (sx, sy), pick_height))
        self._add_cell_highlight((tx, ty), self._stack_z_for_target(state_before, (tx, ty), place_height))

    def add_access_directions(self, lanes, state_matrix):
        self.clear_access_directions()
        pending = []
        for lane in lanes or []:
            if isinstance(lane, dict):
                direction = str(lane.get("direction", "")).strip().upper()
                cells = lane.get("cells") or []
            elif isinstance(lane, (list, tuple)) and len(lane) >= 2:
                direction = str(lane[0]).strip().upper()
                cells = lane[1] or []
            else:
                continue
            if direction not in ("N", "E", "S", "W"):
                continue
            for cell in cells:
                center = self._cell_center(cell, z=self._top_z_for_cell(state_matrix, cell))
                if center is not None:
                    pending.append((center[0], center[1], center[2], direction))
        self._access_actor = self._build_access_arrow_actor(pending)
        if self._access_actor is not None:
            self.renderer.AddActor(self._access_actor)

    def _top_z_for_cell(self, state_matrix, cell):
        try:
            stack = state_matrix[int(cell[0])][int(cell[1])]
            visible = [idx for idx, value in enumerate(stack) if int(value) != 0]
            if not visible:
                return -0.48
            return self._rendered_z_for_stack_index(stack, visible[0])
        except Exception:
            return -0.48

    def _build_access_arrow_actor(self, pending_arrows):
        if not pending_arrows:
            return None
        try:
            from .engine_3d.scene.vtk_scene import build_access_arrow_actor
            return build_access_arrow_actor(pending_arrows)
        except Exception:
            pass
        from vtkmodules.vtkCommonCore import vtkPoints
        from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyData, vtkTriangle
        from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

        vectors = {"N": (0.0, 1.0), "S": (0.0, -1.0), "E": (1.0, 0.0), "W": (-1.0, 0.0)}
        points = vtkPoints()
        cells = vtkCellArray()
        for x, y, z, direction in pending_arrows:
            dx, dy = vectors[direction]
            px, py = -dy, dx
            scale = 0.36
            z += 0.6
            tip = (x + dx * scale, y + dy * scale, z)
            left = (x - dx * scale * 0.55 + px * scale * 0.42, y - dy * scale * 0.55 + py * scale * 0.42, z)
            right = (x - dx * scale * 0.55 - px * scale * 0.42, y - dy * scale * 0.55 - py * scale * 0.42, z)
            base = points.GetNumberOfPoints()
            points.InsertNextPoint(*tip)
            points.InsertNextPoint(*left)
            points.InsertNextPoint(*right)
            tri = vtkTriangle()
            tri.GetPointIds().SetId(0, base)
            tri.GetPointIds().SetId(1, base + 1)
            tri.GetPointIds().SetId(2, base + 2)
            cells.InsertNextCell(tri)

        data = vtkPolyData()
        data.SetPoints(points)
        data.SetPolys(cells)
        mapper = vtkPolyDataMapper()
        mapper.SetInputData(data)
        actor = vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(1.0, 1.0, 1.0)
        actor.GetProperty().SetOpacity(0.95)
        actor.SetPickable(False)
        return actor

    def _stack_z_for_source(self, state_matrix, cell, pick_height=None):
        try:
            sx, sy = int(cell[0]), int(cell[1])
            stack = state_matrix[sx][sy]
            return self._rendered_z_for_stack_index(stack, pick_height)
        except Exception:
            return 0.5

    def _stack_z_for_target(self, state_matrix, cell, place_height=None):
        try:
            tx, ty = int(cell[0]), int(cell[1])
            stack = state_matrix[tx][ty]
            if place_height is not None:
                visible = [idx for idx, value in enumerate(stack) if int(value) != 0]
                insert_pos = 0
                while insert_pos < len(visible) and visible[insert_pos] < int(place_height):
                    insert_pos += 1
                return 0.5 + (len(visible) - insert_pos) * 1.0
            first_nz = next((idx for idx, value in enumerate(stack) if int(value) != 0), len(stack))
            place_idx = max(0, first_nz - 1)
            return self._rendered_z_for_stack_index(stack, place_idx)
        except Exception:
            return 0.5

    def _rendered_z_for_stack_index(self, stack, stack_index):
        visible = [idx for idx, value in enumerate(stack) if int(value) != 0]
        if not visible:
            return 0.5
        try:
            idx = int(stack_index)
        except Exception:
            idx = visible[0]
        if idx not in visible:
            idx = visible[0]
        level_from_top = visible.index(idx)
        return 0.5 + (len(visible) - 1 - level_from_top) * 1.0

    def _add_cell_highlight(self, cell, z_pos):
        from vtkmodules.vtkFiltersSources import vtkCubeSource
        from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

        center = self._cell_center(cell, z=float(z_pos))
        if center is None:
            return

        cube = vtkCubeSource()
        cube.SetXLength(1.06)
        cube.SetYLength(1.06)
        cube.SetZLength(1.06)
        cube.SetCenter(float(center[0]), float(center[1]), float(center[2]))
        cube.Update()

        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(cube.GetOutputPort())

        actor = vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetRepresentationToWireframe()
        actor.GetProperty().SetColor(1.0, 0.93, 0.45)
        actor.GetProperty().SetLineWidth(1.4)
        actor.SetPickable(False)
        self._add_highlight_actor(actor)

    def add_route_overlay(self, route_data):
        self.clear_route_overlay()
        if not isinstance(route_data, dict):
            return

        approach_route = route_data.get("approach_route") or []
        carry_route = route_data.get("route") or []

        for route in route_data.get("approach_parallel_lanes") or []:
            if list(route or []) != list(approach_route or []):
                self._draw_cell_route(route, (1.0, 0.55, 0.10), 2.0, 0.38)
        self._draw_cell_route(approach_route, (1.0, 0.55, 0.10), 4.0, 0.9)

        for route in route_data.get("carry_parallel_lanes") or []:
            if list(route or []) != list(carry_route or []):
                self._draw_cell_route(route, (0.22, 0.55, 0.98), 2.0, 0.38)
        if carry_route:
            src_bridge = self._axis_stepwise_bridge(route_data.get("source"), carry_route[0])
            if len(src_bridge) >= 2:
                self._draw_cell_route(src_bridge, (0.22, 0.55, 0.98), 4.0, 0.92)
        self._draw_cell_route(carry_route, (0.22, 0.55, 0.98), 4.0, 0.92)

    def _axis_stepwise_bridge(self, a, b):
        a = self._as_cell(a)
        b = self._as_cell(b)
        if a is None or b is None or a == b:
            return []
        if a[0] == b[0]:
            step = 1 if b[1] >= a[1] else -1
            return [(a[0], y) for y in range(a[1], b[1] + step, step)]
        if a[1] == b[1]:
            step = 1 if b[0] >= a[0] else -1
            return [(x, a[1]) for x in range(a[0], b[0] + step, step)]
        return []

    def _as_cell(self, cell):
        if isinstance(cell, (list, tuple)) and len(cell) >= 2:
            try:
                return (int(cell[0]), int(cell[1]))
            except Exception:
                return None
        return None

    def _draw_cell_route(self, cells, color, line_width, opacity=0.85):
        cells = list(cells or [])
        if len(cells) < 2:
            return
        for idx in range(len(cells) - 1):
            p1 = self._cell_center(cells[idx], z=0.12)
            p2 = self._cell_center(cells[idx + 1], z=0.12)
            if p1 is not None and p2 is not None:
                self._add_route_line(p1, p2, color, line_width, opacity)

    def _cell_center(self, cell, z=0.12):
        if not isinstance(cell, (list, tuple)) or len(cell) < 2:
            return None
        pad = max(0, self.padding)
        return (float(cell[0]) + pad + 0.5, float(cell[1]) + pad + 0.5, float(z))

    def _add_route_line(self, p1, p2, color, line_width, opacity):
        from vtkmodules.vtkCommonCore import vtkPoints
        from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkLine, vtkPolyData
        from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

        points = vtkPoints()
        points.InsertNextPoint(float(p1[0]), float(p1[1]), float(p1[2]))
        points.InsertNextPoint(float(p2[0]), float(p2[1]), float(p2[2]))

        line = vtkLine()
        line.GetPointIds().SetId(0, 0)
        line.GetPointIds().SetId(1, 1)

        cells = vtkCellArray()
        cells.InsertNextCell(line)

        data = vtkPolyData()
        data.SetPoints(points)
        data.SetLines(cells)

        mapper = vtkPolyDataMapper()
        mapper.SetInputData(data)

        actor = vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(float(color[0]), float(color[1]), float(color[2]))
        actor.GetProperty().SetLineWidth(float(line_width))
        actor.GetProperty().SetOpacity(float(opacity))
        actor.SetPickable(False)
        self._add_route_actor(actor)

    def _add_floor(self, width, length):
        from vtkmodules.vtkFiltersSources import vtkCubeSource
        from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

        if width <= 0 or length <= 0:
            return

        pad = max(0, self.padding)
        total_width = width + 2 * pad
        total_length = length + 2 * pad

        def add_floor_rect(center, size, color, opacity, z_center):
            cube = vtkCubeSource()
            cube.SetXLength(float(size[0]))
            cube.SetYLength(float(size[1]))
            cube.SetZLength(0.04)
            cube.SetCenter(float(center[0]), float(center[1]), float(z_center))
            cube.Update()

            mapper = vtkPolyDataMapper()
            mapper.SetInputConnection(cube.GetOutputPort())

            actor = vtkActor()
            actor.SetMapper(mapper)
            actor.GetProperty().SetColor(float(color[0]), float(color[1]), float(color[2]))
            actor.GetProperty().SetOpacity(float(opacity))
            self._add_actor(actor)

        add_floor_rect(
            (total_width / 2.0, total_length / 2.0),
            (total_width, total_length),
            (0.11, 0.13, 0.16),
            0.78,
            -0.04,
        )
        add_floor_rect(
            (pad + width / 2.0, pad + length / 2.0),
            (width, length),
            (0.24, 0.27, 0.31),
            0.82,
            -0.015,
        )

        for x in range(total_width + 1):
            color = (0.30, 0.33, 0.38) if pad <= x <= pad + width else (0.21, 0.24, 0.29)
            self._add_line((x, 0, 0.01), (x, total_length, 0.01), color)
        for y in range(total_length + 1):
            color = (0.30, 0.33, 0.38) if pad <= y <= pad + length else (0.21, 0.24, 0.29)
            self._add_line((0, y, 0.01), (total_width, y, 0.01), color)

        x0, x1 = pad, pad + width
        y0, y1 = pad, pad + length
        border_color = (0.56, 0.64, 0.74)
        self._add_line((x0, y0, 0.03), (x1, y0, 0.03), border_color, line_width=2.0)
        self._add_line((x1, y0, 0.03), (x1, y1, 0.03), border_color, line_width=2.0)
        self._add_line((x1, y1, 0.03), (x0, y1, 0.03), border_color, line_width=2.0)
        self._add_line((x0, y1, 0.03), (x0, y0, 0.03), border_color, line_width=2.0)

    def _add_line(self, p1, p2, color, line_width=1.0):
        from vtkmodules.vtkCommonCore import vtkPoints
        from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkLine, vtkPolyData
        from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

        points = vtkPoints()
        points.InsertNextPoint(float(p1[0]), float(p1[1]), float(p1[2]))
        points.InsertNextPoint(float(p2[0]), float(p2[1]), float(p2[2]))

        line = vtkLine()
        line.GetPointIds().SetId(0, 0)
        line.GetPointIds().SetId(1, 1)

        cells = vtkCellArray()
        cells.InsertNextCell(line)

        data = vtkPolyData()
        data.SetPoints(points)
        data.SetLines(cells)

        mapper = vtkPolyDataMapper()
        mapper.SetInputData(data)

        actor = vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(float(color[0]), float(color[1]), float(color[2]))
        actor.GetProperty().SetLineWidth(float(line_width))
        self._add_actor(actor)

    def _add_blocks(self, state_matrix):
        from vtkmodules.vtkFiltersSources import vtkCubeSource
        from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

        pad = max(0, self.padding)
        for x, row in enumerate(state_matrix):
            for y, stack in enumerate(row):
                visible_blocks = [
                    (idx, int(value))
                    for idx, value in enumerate(stack)
                    if int(value) > 0
                ]
                for level_from_top, (idx, value) in enumerate(visible_blocks):
                    value = int(value)
                    cube = vtkCubeSource()
                    cube.SetXLength(1.0)
                    cube.SetYLength(1.0)
                    cube.SetZLength(1.0)
                    z_pos = 0.5 + (len(visible_blocks) - 1 - level_from_top)
                    cube.SetCenter(0.0, 0.0, 0.0)
                    cube.Update()

                    mapper = vtkPolyDataMapper()
                    mapper.SetInputConnection(cube.GetOutputPort())

                    actor = vtkActor()
                    actor.SetMapper(mapper)
                    actor.SetPosition(float(x + pad) + 0.5, float(y + pad) + 0.5, float(z_pos))
                    actor.GetProperty().SetColor(*_priority_color(value))
                    actor.GetProperty().SetEdgeVisibility(True)
                    actor.GetProperty().SetEdgeColor(0.08, 0.08, 0.08)
                    actor.priority = value
                    phys_z = int(round(float(z_pos) - 0.5))
                    actor.grid_position = (x, y, phys_z)
                    actor.scene_position = (x + pad, y + pad, phys_z)
                    actor.anim_grid_position = (x + pad, y + pad, phys_z)
                    self._blocks.append(actor)
                    self._add_actor(actor)

    def _reset_camera(self, width, length):
        if width <= 0 or length <= 0:
            return
        pad = max(0, self.padding)
        total_width = width + 2 * pad
        total_length = length + 2 * pad
        camera = self.renderer.GetActiveCamera()
        center_x = total_width / 2.0
        center_y = total_length / 2.0
        span = max(total_width, total_length, 4)
        camera.SetPosition(center_x - span * 0.9, center_y - span * 1.4, span * 1.2)
        camera.SetFocalPoint(center_x, center_y, 0.0)
        camera.SetViewUp(0.0, 0.0, 1.0)
        self.renderer.ResetCamera()
