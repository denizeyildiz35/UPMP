_OPEN_WINDOWS = []


def _load_main_route_bridge():
    try:
        from .animation_bridge import (
            build_route_overlay_from_plan,
            rebuild_step_plans_like_pathfinding_deneme,
        )

        return rebuild_step_plans_like_pathfinding_deneme, build_route_overlay_from_plan
    except ImportError:
        return None, None


def Animation(ida_result=None, depo=None, lanes=None, lane_matrix=None, **kwargs):
    """Open a PySide6 window with a simple embedded VTK stack-area scene.

    If ida_result, depo, and lanes are provided, the C++ lane/slot result is
    converted into physical animation data and the initial state is rendered.
    The real movement animation will be wired here later. PySide6 and VTK are
    optional dependencies, so they are imported only when this function is
    called.
    """
    try:
        from PySide6.QtWidgets import (
            QAbstractItemView,
            QApplication,
            QDialog,
            QDoubleSpinBox,
            QFrame,
            QFormLayout,
            QHBoxLayout,
            QLabel,
            QListWidget,
            QListWidgetItem,
            QMainWindow,
            QPushButton,
            QHeaderView,
            QSlider,
            QTableWidget,
            QTableWidgetItem,
            QVBoxLayout,
            QWidget,
        )
        from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
        from PySide6.QtCore import Qt, QTimer
        from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
        from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera
        from vtkmodules.vtkRenderingCore import vtkRenderer
        import vtkmodules.vtkInteractionStyle  # noqa: F401
        import vtkmodules.vtkRenderingOpenGL2  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "Animation requires optional GUI dependencies. "
            "Install them with: pip install UPMP[animation]"
        ) from exc

    animation_data = None
    if ida_result is not None or depo is not None or lanes is not None:
        if ida_result is None or depo is None or lanes is None:
            raise ValueError("ida_result, depo, and lanes must be provided together")
        from .converter import convert_ida_result_to_animation_data

        animation_data = convert_ida_result_to_animation_data(
            ida_result=ida_result,
            depo=depo,
            lanes=lanes,
            lane_matrix=lane_matrix,
        )

    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication([])

    window = QMainWindow()
    window.setObjectName("upmpAnimationWindow")
    window.setWindowTitle("UPMP Animation")
    window.resize(1100, 750)
    window.setStyleSheet(
        """
        QMainWindow#upmpAnimationWindow {
            background: #0f1115;
            color: #e5e7eb;
        }
        QFrame#leftPanel {
            background: #202020;
            border-right: 1px solid #333333;
        }
        QFrame#rightPanel {
            background: #202020;
            border-left: 1px solid #333333;
        }
        QLabel#panelTitle {
            background: transparent;
            color: #ffffff;
            font-size: 13px;
            font-weight: 700;
            padding-bottom: 4px;
        }
        QLabel#stepLabel {
            background: transparent;
            color: #c9d1d9;
            font-size: 11px;
            font-weight: 600;
        }
        QListWidget#stepList {
            background: #0d1117;
            border: 1px solid #21262d;
            border-radius: 8px;
            color: #c9d1d9;
            font-family: Consolas, monospace;
            font-size: 11px;
            outline: none;
        }
        QListWidget#stepList::item {
            padding: 6px 8px;
            border-bottom: 1px solid #161b22;
        }
        QListWidget#stepList::item:hover {
            background: #1c2128;
            color: #e6edf3;
        }
        QListWidget#stepList::item:selected {
            background: #1b2a40;
            color: #ffffff;
            border: 1px solid #2d5f95;
            border-radius: 5px;
            font-weight: 700;
        }
        QPushButton#stepButton {
            background: #353535;
            color: #ffffff;
            border: 1px solid #555555;
            border-radius: 6px;
            padding: 6px;
            font-weight: 600;
        }
        QPushButton#stepButton:hover {
            background: #4a4a4a;
        }
        QPushButton#stepButton:disabled {
            background: #1e1e1e;
            color: #555555;
            border-color: #333333;
        }
        QLabel#animTitle {
            background: transparent;
            color: #58a6ff;
            font-size: 13px;
            font-weight: 700;
            border-bottom: 1px solid #30363d;
            padding-bottom: 4px;
        }
        QLabel#animPhase {
            background: transparent;
            color: #8b949e;
            font-size: 11px;
            font-style: italic;
            padding: 2px 0;
        }
        QLabel#animCaption,
        QLabel#animValue {
            background: transparent;
            color: #ffffff;
            font-size: 11px;
        }
        QLabel#animValue {
            font-weight: 700;
        }
        QLabel#animMetric {
            background: transparent;
            color: #8b949e;
            font-size: 11px;
            padding: 2px 0;
        }
        QLabel#animMetricAccent {
            background: transparent;
            color: #58a6ff;
            font-size: 12px;
            font-weight: 700;
            padding: 4px 0;
        }
        QLabel#animSummary {
            background: transparent;
            color: #9aa4b2;
            font-size: 10px;
            padding-top: 6px;
        }
        QPushButton#animAllButton {
            background: #0d4a1a;
            color: #9fffb0;
            border: 1px solid #1e8a35;
            border-radius: 6px;
            padding: 8px 6px;
            font-weight: 700;
        }
        QPushButton#animAllButton:hover {
            background: #1e8a35;
        }
        QPushButton#animPauseButton {
            background: #4a1010;
            color: #ff6b6b;
            border: 1px solid #7f1d1d;
            border-radius: 6px;
            padding: 6px;
            font-weight: 700;
        }
        QPushButton#animPauseButton:hover {
            background: #7f1d1d;
            color: #ffffff;
        }
        QPushButton#animCancelButton {
            background: #3a2410;
            color: #ffc27a;
            border: 1px solid #8a5a1e;
            border-radius: 6px;
            padding: 6px;
            font-weight: 700;
        }
        QPushButton#animCancelButton:hover {
            background: #8a5a1e;
            color: #ffffff;
        }
        QPushButton#timeParamsButton {
            background: #1a2030;
            color: #9ec9ff;
            border: 1px solid #2d4f86;
            border-radius: 6px;
            padding: 6px;
            font-weight: 700;
        }
        QPushButton#timeParamsButton:hover {
            background: #25385e;
            border-color: #4d78bd;
            color: #ffffff;
        }
        QPushButton#accessButton {
            background: #123b45;
            color: #b9f3ff;
            border: 1px solid #2a7f90;
            border-radius: 6px;
            padding: 6px;
            font-weight: 700;
        }
        QPushButton#accessButton:hover,
        QPushButton#accessButton:checked {
            background: #2a7f90;
            color: #ffffff;
            border-color: #65b8c8;
        }
        QPushButton#routeButton {
            background: #1a2b1a;
            color: #9aff9a;
            border: 1px solid #3a7a3a;
            border-radius: 6px;
            padding: 6px;
            font-weight: 700;
        }
        QPushButton#routeButton:hover,
        QPushButton#routeButton:checked {
            background: #3a7a3a;
            color: #ffffff;
            border-color: #6adf6a;
        }
        QPushButton#timeLogButton {
            background: #4a3b0d;
            color: #ffe9a6;
            border: 1px solid #8a6a1e;
            border-radius: 6px;
            padding: 6px;
            font-weight: 700;
        }
        QPushButton#timeLogButton:hover {
            background: #8a6a1e;
            color: #fff7dc;
        }
        QPushButton#cameraViewsButton {
            background: #172033;
            color: #c7d8ff;
            border: 1px solid #405a92;
            border-radius: 6px;
            padding: 6px;
            font-weight: 700;
        }
        QPushButton#cameraViewsButton:hover {
            background: #263b68;
            color: #ffffff;
            border-color: #6f91da;
        }
        QFrame#miniCameraPanel {
            background: #0d1117;
            border: 1px solid #21262d;
            border-radius: 8px;
        }
        QLabel#miniCameraTitle {
            background: transparent;
            color: #cfd6e6;
            font-size: 11px;
            font-weight: 700;
        }
        QPushButton#miniCameraPopButton {
            background: #172033;
            color: #c7d8ff;
            border: 1px solid #405a92;
            border-radius: 5px;
            padding: 3px 8px;
            font-size: 10px;
            font-weight: 700;
        }
        QPushButton#miniCameraPopButton:hover {
            background: #263b68;
            color: #ffffff;
        }
        """
    )

    central = QWidget(window)
    layout = QHBoxLayout(central)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    left_panel = QFrame(central)
    left_panel.setObjectName("leftPanel")
    left_panel.setFixedWidth(280)
    left_layout = QVBoxLayout(left_panel)
    left_layout.setContentsMargins(10, 10, 10, 10)
    left_layout.setSpacing(8)

    step_title = QLabel("Steps", left_panel)
    step_title.setObjectName("panelTitle")
    left_layout.addWidget(step_title)

    step_label = QLabel("Step: 0 / 0", left_panel)
    step_label.setObjectName("stepLabel")
    left_layout.addWidget(step_label)

    step_list = QListWidget(left_panel)
    step_list.setObjectName("stepList")
    step_list.setSpacing(1)
    left_layout.addWidget(step_list, 1)

    step_buttons = QHBoxLayout()
    prev_button = QPushButton("Back", left_panel)
    prev_button.setObjectName("stepButton")
    next_button = QPushButton("Next", left_panel)
    next_button.setObjectName("stepButton")
    step_buttons.addWidget(prev_button)
    step_buttons.addWidget(next_button)
    left_layout.addLayout(step_buttons)

    right_panel = QFrame(central)
    right_panel.setObjectName("rightPanel")
    right_panel.setFixedWidth(280)
    right_layout = QVBoxLayout(right_panel)
    right_layout.setContentsMargins(10, 10, 10, 10)
    right_layout.setSpacing(10)

    anim_title = QLabel("Forklift Animation", right_panel)
    anim_title.setObjectName("animTitle")
    right_layout.addWidget(anim_title)

    anim_phase = QLabel("--", right_panel)
    anim_phase.setObjectName("animPhase")
    anim_phase.setWordWrap(True)
    right_layout.addWidget(anim_phase)

    speed_row = QHBoxLayout()
    speed_caption = QLabel("Speed:", right_panel)
    speed_caption.setObjectName("animCaption")
    speed_row.addWidget(speed_caption)

    speed_slider = QSlider(Qt.Horizontal, right_panel)
    speed_slider.setMinimum(1)
    speed_slider.setMaximum(50)
    speed_slider.setValue(5)
    speed_slider.setTickInterval(5)
    speed_slider.setTickPosition(QSlider.TicksBelow)
    speed_row.addWidget(speed_slider, 1)

    speed_value = QLabel("1.0x", right_panel)
    speed_value.setObjectName("animValue")
    speed_value.setFixedWidth(38)
    speed_row.addWidget(speed_value)
    right_layout.addLayout(speed_row)

    anim_all_button = QPushButton("Play All", right_panel)
    anim_all_button.setObjectName("animAllButton")
    right_layout.addWidget(anim_all_button)

    pause_button = QPushButton("Pause", right_panel)
    pause_button.setObjectName("animPauseButton")
    right_layout.addWidget(pause_button)

    cancel_button = QPushButton("Cancel", right_panel)
    cancel_button.setObjectName("animCancelButton")
    right_layout.addWidget(cancel_button)

    mini_camera_panel = QFrame(right_panel)
    mini_camera_panel.setObjectName("miniCameraPanel")
    mini_camera_layout = QVBoxLayout(mini_camera_panel)
    mini_camera_layout.setContentsMargins(6, 6, 6, 6)
    mini_camera_layout.setSpacing(5)

    mini_camera_header = QHBoxLayout()
    mini_camera_title = QLabel("Camera Views", mini_camera_panel)
    mini_camera_title.setObjectName("miniCameraTitle")
    mini_camera_header.addWidget(mini_camera_title)
    mini_camera_header.addStretch()
    mini_camera_pop_button = QPushButton("Pop Out", mini_camera_panel)
    mini_camera_pop_button.setObjectName("miniCameraPopButton")
    mini_camera_header.addWidget(mini_camera_pop_button)
    mini_camera_layout.addLayout(mini_camera_header)

    mini_camera_widget = QVTKRenderWindowInteractor(mini_camera_panel)
    mini_camera_widget.setFixedHeight(220)
    mini_camera_layout.addWidget(mini_camera_widget)
    right_layout.addWidget(mini_camera_panel)

    anim_step = QLabel("", right_panel)
    anim_step.setObjectName("animMetric")
    anim_step.setAlignment(Qt.AlignCenter)
    right_layout.addWidget(anim_step)
    anim_step.hide()

    anim_time = QLabel("", right_panel)
    anim_time.setObjectName("animMetricAccent")
    anim_time.setAlignment(Qt.AlignCenter)
    right_layout.addWidget(anim_time)
    anim_time.hide()

    anim_total_time = QLabel("", right_panel)
    anim_total_time.setObjectName("animMetric")
    anim_total_time.setAlignment(Qt.AlignCenter)
    right_layout.addWidget(anim_total_time)
    anim_total_time.hide()

    anim_summary = QLabel(
        "Start animation to see the current step operation and time summary here.",
        right_panel,
    )
    anim_summary.setObjectName("animSummary")
    anim_summary.setWordWrap(True)
    right_layout.addWidget(anim_summary)
    anim_summary.hide()

    right_layout.addStretch()

    time_params_button = QPushButton("Forklift Times", right_panel)
    time_params_button.setObjectName("timeParamsButton")
    right_layout.addWidget(time_params_button)

    access_button = QPushButton("Show Access Directions", right_panel)
    access_button.setObjectName("accessButton")
    access_button.setCheckable(True)
    right_layout.addWidget(access_button)

    route_button = QPushButton("Show Route", right_panel)
    route_button.setObjectName("routeButton")
    route_button.setCheckable(True)
    right_layout.addWidget(route_button)

    time_log_button = QPushButton("Time Log", right_panel)
    time_log_button.setObjectName("timeLogButton")
    right_layout.addWidget(time_log_button)

    camera_views_button = QPushButton("Camera Views", right_panel)
    camera_views_button.setObjectName("cameraViewsButton")
    right_layout.addWidget(camera_views_button)

    vtk_widget = QVTKRenderWindowInteractor(central)
    layout.addWidget(left_panel)
    layout.addWidget(vtk_widget, 1)
    layout.addWidget(right_panel)
    window.setCentralWidget(central)

    renderer = vtkRenderer()
    renderer.SetBackground(0.09, 0.10, 0.12)
    vtk_widget.GetRenderWindow().AddRenderer(renderer)

    scene = None
    if animation_data is not None:
        from .simple_scene import SimpleVTKScene

        scene = SimpleVTKScene(renderer)
        scene.render_state(animation_data["initial_state"])

    states = list((animation_data or {}).get("states_frozen", []))
    moves = list((animation_data or {}).get("moves", []))
    move_directions = list((animation_data or {}).get("move_directions", []))
    access_lanes = list((animation_data or {}).get("lanes", []))
    time_param_fields = (
        ("time_per_grid_straight", "Straight travel (s/cell)", 1.0),
        ("time_per_grid_strafe", "Strafe travel (s/cell)", 1.5),
        ("time_turn_90", "90 deg turn (s)", 2.0),
        ("time_turn_180", "180 deg turn (s)", 3.5),
        ("time_fork_up_empty", "Empty fork up (s/level)", 0.5),
        ("time_fork_down_empty", "Empty fork down (s/level)", 0.4),
        ("time_fork_up_loaded", "Loaded fork up (s/level)", 0.8),
        ("time_fork_down_loaded", "Loaded fork down (s/level)", 0.6),
        ("time_pick_insert", "Pick maneuver (s)", 2.0),
        ("time_place_release", "Place maneuver (s)", 2.0),
    )
    time_param_defaults = {key: default for key, _label, default in time_param_fields}
    time_params = dict(time_param_defaults)
    for key, value in dict((animation_data or {}).get("time_params") or kwargs.get("time_params") or {}).items():
        if key in time_params:
            try:
                time_params[key] = float(value)
            except Exception:
                pass
    window.upmp_time_params = time_params

    def open_time_params_dialog():
        dialog = QDialog(window)
        dialog.setWindowTitle("Forklift Times")
        dialog.setModal(True)
        dialog.setMinimumWidth(390)
        dialog.setStyleSheet(
            """
            QDialog { background: #0f1115; color: #e6e6e6; }
            QLabel { color: #cfd6e6; font-size: 12px; }
            QDoubleSpinBox {
                background: #161a22;
                color: #e6e6e6;
                border: 1px solid #2a2f3a;
                border-radius: 5px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QDoubleSpinBox:hover { border-color: #3a4356; }
            QPushButton {
                background: #353535;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: 700;
            }
            QPushButton:hover { background: #4a4a4a; }
            QPushButton#saveTimeParams { background: #1a5276; border-color: #2980b9; }
            QPushButton#saveTimeParams:hover { background: #2471a3; }
            """
        )

        root = QVBoxLayout(dialog)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(10)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(8)
        spins = {}
        for key, label, default in time_param_fields:
            spin = QDoubleSpinBox(dialog)
            spin.setRange(0.0, 9999.0)
            spin.setDecimals(2)
            spin.setSingleStep(0.1)
            spin.setValue(float(time_params.get(key, default)))
            spins[key] = spin
            form.addRow(f"{label}:", spin)
        root.addLayout(form)

        buttons = QHBoxLayout()
        reset_button = QPushButton("Reset Defaults", dialog)
        cancel_button = QPushButton("Cancel", dialog)
        save_button = QPushButton("Save", dialog)
        save_button.setObjectName("saveTimeParams")
        buttons.addWidget(reset_button)
        buttons.addStretch()
        buttons.addWidget(cancel_button)
        buttons.addWidget(save_button)
        root.addLayout(buttons)

        reset_button.clicked.connect(
            lambda: [spins[key].setValue(float(default)) for key, _label, default in time_param_fields]
        )
        cancel_button.clicked.connect(dialog.reject)
        save_button.clicked.connect(dialog.accept)

        if dialog.exec() == QDialog.Accepted:
            for key, spin in spins.items():
                time_params[key] = float(spin.value())
            window.upmp_time_params = dict(time_params)
            if isinstance(animation_data, dict):
                animation_data["time_params"] = dict(time_params)

    def _camera_bounds():
        state = states[0] if states else (animation_data or {}).get("initial_state")
        width = len(state or [])
        length = len(state[0]) if state else 0
        pad = max(0, int(getattr(scene, "padding", 0) if scene is not None else 0))
        total_width = width + 2 * pad
        total_length = length + 2 * pad
        return total_width * 0.5, total_length * 0.5, max(total_width, total_length, 4) * 1.6

    def set_camera_preset(key):
        center_x, center_y, cam_dist = _camera_bounds()
        camera = renderer.GetActiveCamera()
        camera.SetFocalPoint(center_x, center_y, 0.0)
        if key == "7":
            camera.SetPosition(center_x - cam_dist, center_y - cam_dist, cam_dist)
            camera.SetViewUp(0.0, 0.0, 1.0)
        elif key == "8":
            camera.SetPosition(center_x, center_y, cam_dist * 1.5)
            camera.SetViewUp(0.0, 1.0, 0.0)
        elif key == "9":
            camera.SetPosition(center_x, center_y - cam_dist * 1.5, 0.0)
            camera.SetViewUp(0.0, 0.0, 1.0)
        elif key == "0":
            camera.SetPosition(center_x + cam_dist * 0.5, center_y - cam_dist * 0.9, cam_dist * 0.7)
            camera.SetViewUp(0.0, 0.0, 1.0)
        else:
            return
        renderer.ResetCameraClippingRange()
        vtk_widget.GetRenderWindow().Render()

    def on_camera_key(obj, _event):
        set_camera_preset((obj.GetKeySym() or "").lower())

    anim_runtime = {
        "anim": None,
        "from_step": 0,
        "move_count": 0,
        "paused": False,
        "last_active_step": None,
        "poll": QTimer(window),
    }
    anim_runtime["poll"].setInterval(33)

    rebuild_step_plans, build_route_overlay = _load_main_route_bridge()
    route_plans = []
    route_overlays = []
    if callable(rebuild_step_plans) and callable(build_route_overlay) and moves and states:
        try:
            route_plans = rebuild_step_plans(
                moves=moves,
                states=states,
                move_directions=move_directions,
            )
            route_overlays = [build_route_overlay(plan) for plan in route_plans]
        except Exception:
            route_plans = []
            route_overlays = []
    route_button.setEnabled(bool(route_overlays))

    def _new_camera_view_store(dialog=None, widget=None):
        return {
            "dialog": dialog,
            "widget": widget,
            "scenes": [],
            "renderers": [],
            "labels": [],
            "carried_actors": [],
            "front_fork_actors": [],
            "closing": False,
        }

    camera_views = _new_camera_view_store()
    mini_camera_views = _new_camera_view_store(widget=mini_camera_widget)

    def _camera_view_state(row=None):
        if not states:
            return (animation_data or {}).get("initial_state")
        try:
            row = step_list.currentRow() if row is None else int(row)
        except Exception:
            row = 0
        row = max(0, min(row, len(states) - 1))
        return states[row]

    def _state_size_for_camera_view(state_matrix):
        width = len(state_matrix or [])
        length = len(state_matrix[0]) if state_matrix else 0
        max_height = 1
        for row in state_matrix or []:
            for stack in row or []:
                try:
                    max_height = max(max_height, sum(1 for value in stack if int(value) != 0))
                except Exception:
                    pass
        pad = max(0, int(getattr(scene, "padding", 5) if scene is not None else 5))
        return width + 2 * pad, length + 2 * pad, max_height

    def _configure_camera_view(view_renderer, state_matrix, view_name, forklift_pose=None):
        total_width, total_length, max_height = _state_size_for_camera_view(state_matrix)
        distance = max(total_width, total_length, max_height + 2, 4) * 1.4
        camera = view_renderer.GetActiveCamera()

        if forklift_pose is not None:
            import math

            fx, fy, yaw = forklift_pose
            yaw_rad = math.radians(float(yaw))
            vectors = {
                "Front": (math.cos(yaw_rad), math.sin(yaw_rad)),
                "Rear": (-math.cos(yaw_rad), -math.sin(yaw_rad)),
                "Left": (math.cos(yaw_rad + math.pi * 0.5), math.sin(yaw_rad + math.pi * 0.5)),
                "Right": (math.cos(yaw_rad - math.pi * 0.5), math.sin(yaw_rad - math.pi * 0.5)),
            }
            dx, dy = vectors.get(view_name, vectors["Front"])
            eye_z = max(1.25, min(float(max_height) + 0.75, 2.05))
            look_dist = max(7.0, min(distance, 14.0))
            camera.ParallelProjectionOff()
            camera.SetViewAngle(72.0)
            camera.SetPosition(float(fx), float(fy), eye_z)
            camera.SetFocalPoint(float(fx) + dx * look_dist, float(fy) + dy * look_dist, eye_z - 0.85)
            camera.SetViewUp(0.0, 0.0, 1.0)
            camera.SetClippingRange(0.08, max(distance * 4.0, 80.0))
            return

        center_x = total_width * 0.5
        center_y = total_length * 0.5
        center_z = max(0.5, max_height * 0.5)
        camera.SetFocalPoint(center_x, center_y, center_z)
        camera.SetViewUp(0.0, 0.0, 1.0)
        camera.ParallelProjectionOn()
        if view_name == "Front":
            camera.SetPosition(center_x, center_y - distance, center_z)
            camera.SetParallelScale(max(total_width, max_height + 2) * 0.58)
        elif view_name == "Rear":
            camera.SetPosition(center_x, center_y + distance, center_z)
            camera.SetParallelScale(max(total_width, max_height + 2) * 0.58)
        elif view_name == "Left":
            camera.SetPosition(center_x - distance, center_y, center_z)
            camera.SetParallelScale(max(total_length, max_height + 2) * 0.58)
        else:
            camera.SetPosition(center_x + distance, center_y, center_z)
            camera.SetParallelScale(max(total_length, max_height + 2) * 0.58)
        view_renderer.ResetCameraClippingRange()

    def _current_forklift_pose(anim=None):
        anim = anim or anim_runtime.get("anim")
        if anim is None:
            return None
        try:
            loc = getattr(anim, "forklift_location", None)
            yaw = getattr(anim, "forklift_yaw", None)
            if loc is not None and yaw is not None:
                return (float(loc[0]), float(loc[1]), float(yaw))
        except Exception:
            pass
        actor = getattr(anim, "forklift_actor", None)
        if actor is None:
            return None
        try:
            x, y, _z = actor.GetPosition()
            yaw = actor.GetOrientation()[2]
            return (float(x), float(y), float(yaw))
        except Exception:
            return None

    def _add_camera_view_label(view_renderer, text):
        from vtkmodules.vtkRenderingCore import vtkTextActor

        label = vtkTextActor()
        label.SetInput(text)
        label.GetPositionCoordinate().SetCoordinateSystemToNormalizedViewport()
        label.GetPositionCoordinate().SetValue(0.03, 0.84)
        prop = label.GetTextProperty()
        prop.SetFontSize(14)
        prop.SetBold(True)
        prop.SetShadow(True)
        prop.SetColor(0.86, 0.90, 0.98)
        view_renderer.AddActor2D(label)
        return label

    def _add_camera_view_light(view_renderer):
        from vtkmodules.vtkRenderingCore import vtkLight

        light = vtkLight()
        light.SetLightTypeToHeadlight()
        light.SetIntensity(1.45)
        view_renderer.AddLight(light)
        view_renderer.AutomaticLightCreationOff()
        return light

    def _prepare_camera_view_scene(view_scene):
        for actor in list(getattr(view_scene, "_blocks", []) or []):
            try:
                prop = actor.GetProperty()
                prop.LightingOff()
                prop.SetAmbient(1.0)
                prop.SetDiffuse(0.0)
            except Exception:
                pass

    def _make_camera_carried_actor():
        from vtkmodules.vtkFiltersSources import vtkCubeSource
        from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

        cube = vtkCubeSource()
        cube.SetXLength(1.0)
        cube.SetYLength(1.0)
        cube.SetZLength(1.0)
        cube.SetCenter(0.0, 0.0, 0.0)
        cube.Update()

        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(cube.GetOutputPort())

        actor = vtkActor()
        actor.SetMapper(mapper)
        prop = actor.GetProperty()
        prop.SetEdgeVisibility(True)
        prop.SetEdgeColor(0.08, 0.08, 0.08)
        prop.LightingOff()
        prop.SetAmbient(1.0)
        prop.SetDiffuse(0.0)
        actor.SetPickable(False)
        actor.SetVisibility(False)
        return actor

    def _make_camera_fork_actor():
        from vtkmodules.vtkFiltersSources import vtkCubeSource
        from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

        cube = vtkCubeSource()
        cube.SetXLength(2.10)
        cube.SetYLength(0.12)
        cube.SetZLength(0.10)
        cube.SetCenter(0.0, 0.0, 0.0)
        cube.Update()

        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(cube.GetOutputPort())

        actor = vtkActor()
        actor.SetMapper(mapper)
        prop = actor.GetProperty()
        prop.SetColor(0.02, 0.02, 0.025)
        prop.SetEdgeVisibility(True)
        prop.SetEdgeColor(0.0, 0.0, 0.0)
        prop.LightingOff()
        prop.SetAmbient(1.0)
        prop.SetDiffuse(0.0)
        actor.SetPickable(False)
        actor.SetVisibility(False)
        return actor

    def _current_fork_z(anim=None):
        anim = anim or anim_runtime.get("anim")
        if anim is None:
            return 0.0
        try:
            get_fork_z = getattr(anim, "_get_current_fork_z", None)
            if callable(get_fork_z):
                return float(get_fork_z())
        except Exception:
            pass
        try:
            return max(0.0, float(getattr(anim, "fork_level", 1.0)) - 1.0)
        except Exception:
            return 0.0

    def _sync_camera_front_forks(store=None, anim=None, forklift_pose=None):
        import math

        store = store or camera_views
        fork_actors = list(store.get("front_fork_actors") or [])
        if not fork_actors:
            return
        anim = anim or anim_runtime.get("anim")
        forklift_pose = forklift_pose or _current_forklift_pose(anim)
        if anim is None or forklift_pose is None:
            for fork_actor in fork_actors:
                try:
                    fork_actor.SetVisibility(False)
                except Exception:
                    pass
            return

        fx, fy, yaw = forklift_pose
        yaw_rad = math.radians(float(yaw))
        forward = (math.cos(yaw_rad), math.sin(yaw_rad))
        side = (-math.sin(yaw_rad), math.cos(yaw_rad))
        fork_z = _current_fork_z(anim) + 0.08
        center_forward = 0.45
        side_offsets = (-0.28, 0.28)
        for fork_actor, side_offset in zip(fork_actors, side_offsets):
            try:
                x = float(fx) + forward[0] * center_forward + side[0] * side_offset
                y = float(fy) + forward[1] * center_forward + side[1] * side_offset
                fork_actor.SetPosition(x, y, float(fork_z))
                fork_actor.SetOrientation(0.0, 0.0, float(yaw))
                fork_actor.SetVisibility(True)
                fork_actor.Modified()
            except Exception:
                pass

    def _sync_camera_carried_block(store=None, anim=None):
        store = store or camera_views
        carried = getattr(anim or anim_runtime.get("anim"), "_carried_block_actor", None)
        carried_actors = list(store.get("carried_actors") or [])
        if not carried_actors:
            return

        carried_key = None
        if carried is not None:
            try:
                gx, gy, gz = carried.anim_grid_position
                carried_key = (int(gx), int(gy), int(gz))
            except Exception:
                carried_key = None

        for view_scene in list(store.get("scenes") or []):
            for block_actor in list(getattr(view_scene, "_blocks", []) or []):
                if carried is not None and carried_key is not None:
                    try:
                        bx, by, bz = block_actor.anim_grid_position
                        block_actor.SetVisibility((int(bx), int(by), int(bz)) != carried_key)
                    except Exception:
                        pass

        if carried is None:
            for mirror in carried_actors:
                try:
                    mirror.SetVisibility(False)
                except Exception:
                    pass
            return

        try:
            pos = carried.GetPosition()
            orient = carried.GetOrientation()
            color = carried.GetProperty().GetColor()
        except Exception:
            return

        for mirror in carried_actors:
            try:
                mirror.SetPosition(float(pos[0]), float(pos[1]), float(pos[2]))
                mirror.SetOrientation(float(orient[0]), float(orient[1]), float(orient[2]))
                mirror.GetProperty().SetColor(float(color[0]), float(color[1]), float(color[2]))
                mirror.SetVisibility(True)
                mirror.Modified()
            except Exception:
                pass

    def _finalize_camera_views(store=None):
        store = store or camera_views
        dialog = store.get("dialog")
        widget = store.get("widget")
        if dialog is None and widget is None:
            return
        store["closing"] = True
        if widget is not None:
            try:
                render_window = widget.GetRenderWindow()
                interactor = render_window.GetInteractor()
                if interactor is not None:
                    try:
                        interactor.Disable()
                    except Exception:
                        pass
                    try:
                        interactor.TerminateApp()
                    except Exception:
                        pass
                for view_renderer in list(store.get("renderers") or []):
                    try:
                        render_window.RemoveRenderer(view_renderer)
                    except Exception:
                        pass
                try:
                    render_window.Finalize()
                except Exception:
                    pass
            except Exception:
                pass
        if dialog is not None:
            try:
                _OPEN_WINDOWS.remove(dialog)
            except ValueError:
                pass
        store.update({
            "dialog": None,
            "widget": None,
            "scenes": [],
            "renderers": [],
            "labels": [],
            "carried_actors": [],
            "front_fork_actors": [],
            "closing": False,
        })

    def _refresh_camera_views(store=None, row=None, forklift_pose=None, rebuild_scene=True):
        store = store or camera_views
        dialog = store.get("dialog")
        widget = store.get("widget")
        if store.get("closing") or widget is None or not store.get("scenes"):
            return
        if dialog is not None:
            try:
                if not dialog.isVisible():
                    return
            except RuntimeError:
                return
        else:
            try:
                if not widget.isVisible():
                    return
            except RuntimeError:
                return
        state_matrix = _camera_view_state(row)
        if not state_matrix:
            return
        if forklift_pose is None:
            forklift_pose = _current_forklift_pose()
        for view_scene, view_renderer, view_name in zip(
            store["scenes"],
            store["renderers"],
            ("Front", "Rear", "Left", "Right"),
        ):
            if rebuild_scene:
                view_scene.render_state(state_matrix, reset_camera=False)
                _prepare_camera_view_scene(view_scene)
            _configure_camera_view(view_renderer, state_matrix, view_name, forklift_pose=forklift_pose)
        _sync_camera_carried_block(store=store)
        _sync_camera_front_forks(store=store, forklift_pose=forklift_pose)
        if widget is not None:
            try:
                widget.GetRenderWindow().Render()
            except RuntimeError:
                pass

    def _refresh_all_camera_views(row=None, forklift_pose=None, rebuild_scene=True):
        _refresh_camera_views(mini_camera_views, row=row, forklift_pose=forklift_pose, rebuild_scene=rebuild_scene)
        _refresh_camera_views(camera_views, row=row, forklift_pose=forklift_pose, rebuild_scene=rebuild_scene)

    def _setup_camera_view_render_window(store, camera_widget, state_matrix):
        from .simple_scene import SimpleVTKScene as CameraSimpleVTKScene

        view_specs = (
            ("Front", (0.0, 0.5, 0.5, 1.0), (0.08, 0.09, 0.12)),
            ("Rear", (0.5, 0.5, 1.0, 1.0), (0.09, 0.08, 0.11)),
            ("Left", (0.0, 0.0, 0.5, 0.5), (0.07, 0.09, 0.10)),
            ("Right", (0.5, 0.0, 1.0, 0.5), (0.09, 0.10, 0.08)),
        )
        scenes = []
        renderers = []
        labels = []
        carried_actors = []
        front_fork_actors = []
        render_window = camera_widget.GetRenderWindow()
        for view_name, viewport, background in view_specs:
            view_renderer = vtkRenderer()
            view_renderer.SetViewport(*viewport)
            view_renderer.SetBackground(*background)
            _add_camera_view_light(view_renderer)
            render_window.AddRenderer(view_renderer)
            view_scene = CameraSimpleVTKScene(view_renderer)
            view_scene.render_state(state_matrix, reset_camera=False)
            _prepare_camera_view_scene(view_scene)
            _configure_camera_view(view_renderer, state_matrix, view_name, forklift_pose=_current_forklift_pose())
            label = _add_camera_view_label(view_renderer, view_name)
            carried_actor = _make_camera_carried_actor()
            view_renderer.AddActor(carried_actor)
            if view_name == "Front":
                for _ in range(2):
                    fork_actor = _make_camera_fork_actor()
                    view_renderer.AddActor(fork_actor)
                    front_fork_actors.append(fork_actor)
            scenes.append(view_scene)
            renderers.append(view_renderer)
            labels.append(label)
            carried_actors.append(carried_actor)

        store.update({
            "widget": camera_widget,
            "scenes": scenes,
            "renderers": renderers,
            "labels": labels,
            "carried_actors": carried_actors,
            "front_fork_actors": front_fork_actors,
        })
        _sync_camera_carried_block(store=store)
        _sync_camera_front_forks(store=store, forklift_pose=_current_forklift_pose())

    def open_camera_views_dialog():
        state_matrix = _camera_view_state()
        if not state_matrix:
            anim_phase.setText("No state data available for camera views.")
            return

        existing = camera_views.get("dialog")
        if existing is not None:
            mini_camera_panel.setVisible(False)
            existing.show()
            _refresh_camera_views(camera_views)
            existing.raise_()
            existing.activateWindow()
            return

        dialog = QDialog(window)
        dialog.setWindowTitle("Forklift Camera Views")
        dialog.resize(920, 680)
        dialog.setStyleSheet("QDialog{background:#0f1115;color:#e6e6e6;}")

        def _hide_camera_views(event=None):
            if event is not None:
                event.ignore()
            try:
                dialog.hide()
            except RuntimeError:
                pass
            mini_camera_panel.setVisible(True)
            _refresh_camera_views(mini_camera_views)

        dialog.closeEvent = _hide_camera_views
        dialog.reject = _hide_camera_views

        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setContentsMargins(8, 8, 8, 8)
        dialog_layout.setSpacing(0)

        camera_widget = QVTKRenderWindowInteractor(dialog)
        dialog_layout.addWidget(camera_widget, 1)

        camera_views.update({
            "dialog": dialog,
        })
        _setup_camera_view_render_window(camera_views, camera_widget, state_matrix)
        _OPEN_WINDOWS.append(dialog)

        def _clear_camera_views(*_args):
            if camera_views.get("dialog") is not dialog:
                return
            _finalize_camera_views()

        dialog.destroyed.connect(_clear_camera_views)
        camera_widget.GetRenderWindow().GetInteractor().Initialize()
        mini_camera_panel.setVisible(False)
        dialog.show()
        camera_widget.GetRenderWindow().Render()

    def _anim_speed():
        return max(0.1, float(speed_slider.value()) / 5.0)

    def _shift_cell_for_anim(cell):
        if not isinstance(cell, (list, tuple)) or len(cell) < 2:
            return cell
        pad = max(0, int(getattr(scene, "padding", 0) if scene is not None else 0))
        return (int(cell[0]) + pad, int(cell[1]) + pad)

    def _shift_lane_for_anim(lane):
        return [_shift_cell_for_anim(cell) for cell in (lane or [])]

    def _shift_plan_for_anim(plan):
        shifted = dict(plan or {})
        for key in ("source", "target", "turn_pivot", "approach_turn_pivot"):
            if key in shifted and shifted.get(key) is not None:
                shifted[key] = _shift_cell_for_anim(shifted.get(key))
        for key in ("approach_main_route", "carry_main_route"):
            shifted[key] = _shift_lane_for_anim(shifted.get(key))
        for key in ("approach_parallel_lanes", "carry_parallel_lanes"):
            shifted[key] = [_shift_lane_for_anim(lane) for lane in (shifted.get(key) or [])]
        return shifted

    def _visual_source_level(state, cell, stack_index):
        try:
            stack = state[int(cell[0])][int(cell[1])]
            visible = [idx for idx, value in enumerate(stack) if int(value) != 0]
            idx = int(stack_index)
            if idx not in visible:
                idx = visible[0] if visible else 0
            return 1 + (len(visible) - 1 - visible.index(idx))
        except Exception:
            return 1

    def _visual_target_level(state, cell, stack_index):
        try:
            stack = state[int(cell[0])][int(cell[1])]
            visible = [idx for idx, value in enumerate(stack) if int(value) != 0]
            insert_pos = 0
            target_idx = int(stack_index)
            while insert_pos < len(visible) and visible[insert_pos] < target_idx:
                insert_pos += 1
            return 1 + (len(visible) - insert_pos)
        except Exception:
            return 1

    def _prepare_plan_for_anim(plan, state_before):
        prepared = dict(plan or {})
        source = prepared.get("source")
        target = prepared.get("target")
        prepared["pick_level"] = _visual_source_level(state_before, source, prepared.get("pick_height", 0))
        prepared["place_level"] = _visual_target_level(state_before, target, prepared.get("place_height", 0))
        return _shift_plan_for_anim(prepared)

    def _set_anim_buttons(running):
        anim_all_button.setEnabled(bool(moves and route_plans) and not running)
        pause_button.setEnabled(bool(running))
        cancel_button.setEnabled(bool(running))
        step_list.setEnabled(not running and bool(states))
        if running:
            prev_button.setEnabled(False)
            next_button.setEnabled(False)
        else:
            update_step_controls(step_list.currentRow())
        if not running:
            pause_button.setText("Pause")
            anim_runtime["paused"] = False

    def _cleanup_animator():
        anim = anim_runtime.get("anim")
        if anim is None:
            return
        try:
            anim._stop_animation_timer()
        except Exception:
            pass
        for actor in [getattr(anim, "forklift_actor", None)] + list(getattr(anim, "_dir_point_actors", []) or []):
            if actor is not None:
                try:
                    renderer.RemoveActor(actor)
                except Exception:
                    pass
        try:
            anim.forklift_actor = None
            anim._dir_point_actors = []
            anim._carried_block_actor = None
        except Exception:
            pass
        anim_runtime["anim"] = None

    def _finalize_vtk_widget(widget):
        if widget is None:
            return
        try:
            render_window = widget.GetRenderWindow()
            interactor = render_window.GetInteractor()
            if interactor is not None:
                try:
                    interactor.Disable()
                except Exception:
                    pass
                try:
                    interactor.TerminateApp()
                except Exception:
                    pass
            try:
                render_window.Finalize()
            except Exception:
                pass
        except Exception:
            pass

    def _snap_to_state(row, message=None):
        if scene is None or not states:
            return
        row = max(0, min(int(row), len(states) - 1))
        scene.render_state(states[row], reset_camera=False)
        update_move_highlights(row)
        update_route_overlay(row, render=False)
        update_access_directions(row, render=False)
        if step_list.currentRow() != row:
            step_list.blockSignals(True)
            step_list.setCurrentRow(row)
            step_list.blockSignals(False)
        update_step_controls(row)
        if message:
            anim_phase.setText(message)
        _refresh_all_camera_views(row)
        vtk_widget.GetRenderWindow().Render()

    def _sync_anim_step(active_step):
        if scene is None or not states:
            return
        try:
            active_step = int(active_step)
        except Exception:
            return
        if active_step <= 0 or active_step == anim_runtime.get("last_active_step"):
            return
        anim_runtime["last_active_step"] = active_step

        from_step = int(anim_runtime.get("from_step", 0) or 0)
        move_idx = from_step + active_step - 1
        row = move_idx + 1
        state_idx = max(0, min(move_idx, len(states) - 1))

        if 0 <= row < step_list.count():
            step_list.blockSignals(True)
            step_list.setCurrentRow(row)
            step_list.blockSignals(False)
        update_step_controls(row)
        update_move_highlights(row)
        update_route_overlay(row, render=False)
        update_access_directions(state_idx, render=False)
        _refresh_all_camera_views(state_idx)
        vtk_widget.GetRenderWindow().Render()

    def _finish_animation(cancelled=False):
        try:
            anim_runtime["poll"].stop()
        except Exception:
            pass
        from_step = int(anim_runtime.get("from_step", 0) or 0)
        move_count = int(anim_runtime.get("move_count", 0) or 0)
        final_row = step_list.currentRow() if cancelled else from_step + move_count
        _cleanup_animator()
        _set_anim_buttons(False)
        anim_runtime["last_active_step"] = None
        _snap_to_state(final_row, "Animation cancelled." if cancelled else "Animation complete.")

    def _is_anim_timer_active(anim):
        timer = getattr(anim, "_qt_anim_timer", None)
        if timer is not None:
            try:
                return bool(timer.isActive())
            except Exception:
                return False
        return getattr(anim, "_anim_iren", None) is not None

    def _english_anim_text(text):
        result = str(text or "")
        replacements = (
            ("\u00c7atal Seviyesi", "Fork Level"),
            ("\x43atal Seviyesi", "Fork Level"),
            ("Blo\u011fu B\u0131rak", "Place Block"),
            ("\x42logu \x42irak", "Place Block"),
            ("Blo\u011fu Al", "Pick Block"),
            ("\x42logu Al", "Pick Block"),
            ("\x47eri \u00c7ekil", "Retreat"),
            ("\x47eri Cekil", "Retreat"),
            ("Yakla\u015f", "Approach"),
            ("\x59aklas", "Approach"),
            ("\x59an \x47it, Sa\u011f Yan", "Strafe Right"),
            ("\x59an \x47it, Sag Yan", "Strafe Right"),
            ("\x59an \x47it, Sol Yan", "Strafe Left"),
            ("\x47it, \x47eri", "Move Backward"),
            ("D\u00f6n", "Turn"),
            ("\x44on", "Turn"),
            ("\x47it", "Move"),
            ("Do\u011fu", "East"),
            ("\x44ogu", "East"),
            ("Bat\u0131", "West"),
            ("\x42ati", "West"),
            ("Kuzey", "North"),
            ("G\u00fcney", "South"),
            ("\x47uney", "South"),
        )
        for source, target in replacements:
            result = result.replace(source, target)
        return result

    def _english_phase(phase):
        phase_key = str(phase or "").strip().lower()
        if not phase_key:
            return ""
        return {
            "approach": "Approach",
            "carry": "Carry",
        }.get(phase_key, phase_key.title())

    def _poll_animation():
        anim = anim_runtime.get("anim")
        if anim is None:
            anim_runtime["poll"].stop()
            return
        active_cmd = getattr(anim, "_active_cmd", None)
        if isinstance(active_cmd, dict):
            text = _english_anim_text(active_cmd.get("text", ""))
            phase = _english_phase(active_cmd.get("phase", ""))
            if text:
                anim_phase.setText(f"{phase} - {text}" if phase else text)
        active_step = getattr(anim, "_active_step", None)
        if active_step is not None:
            try:
                anim_step.setText(f"Step {int(active_step)} / {int(anim_runtime.get('move_count', 0) or 0)}")
                _sync_anim_step(active_step)
            except Exception:
                pass
        pose = _current_forklift_pose(anim)
        if pose is not None:
            _refresh_all_camera_views(forklift_pose=pose, rebuild_scene=False)
        if not _is_anim_timer_active(anim):
            _finish_animation(cancelled=False)

    anim_runtime["poll"].timeout.connect(_poll_animation)

    def _start_animation_from(from_step):
        if scene is None or not moves or not route_plans or not states:
            anim_phase.setText("No moves/routes available for animation.")
            return
        from_step = max(0, min(int(from_step), len(moves) - 1))
        _finish_animation(cancelled=True) if anim_runtime.get("anim") is not None else None

        plans = [plan for plan in route_plans[from_step:] if isinstance(plan, dict)]
        if not plans:
            anim_phase.setText("No convertible step plan is available.")
            return

        _snap_to_state(from_step)
        update_move_highlights(from_step + 1)
        update_route_overlay(from_step + 1, render=False)
        update_access_directions(from_step, render=False)
        vtk_widget.GetRenderWindow().Render()
        shifted_plans = [
            _prepare_plan_for_anim(plan, states[from_step + idx] if (from_step + idx) < len(states) else states[from_step])
            for idx, plan in enumerate(plans)
        ]

        try:
            from .route_animation import RouteAnimation
            from .animation_bridge import apply_time_params, build_anim_moves_from_plans
        except Exception as exc:
            anim_phase.setText(f"Could not load animation module: {exc}")
            return

        block_actors = scene.collect_anim_block_actors() if hasattr(scene, "collect_anim_block_actors") else {}
        anim_moves = build_anim_moves_from_plans(shifted_plans)
        if not anim_moves or not block_actors:
            anim_phase.setText("Block actors are not ready for animation.")
            return

        anim = RouteAnimation(step_plans=shifted_plans)
        params = dict(time_params)
        params["time_reverse_penalty"] = 0.0
        apply_time_params(anim, params)
        anim.speed = _anim_speed()

        anim_runtime["anim"] = anim
        anim_runtime["from_step"] = from_step
        anim_runtime["move_count"] = len(shifted_plans)
        anim_runtime["paused"] = False
        anim_runtime["last_active_step"] = None
        _set_anim_buttons(True)
        anim_step.setText(f"Step 1 / {len(shifted_plans)}")
        anim_time.setText("")
        anim_total_time.setText("")
        anim_summary.setText("Animation running.")
        anim_phase.setText("Starting animation...")

        try:
            anim.run(renderer, anim_moves, current_idx=1, block_actors=block_actors)
        except Exception as exc:
            _cleanup_animator()
            _set_anim_buttons(False)
            _snap_to_state(from_step, f"Could not start animation: {exc}")
            return
        _refresh_all_camera_views(from_step, forklift_pose=_current_forklift_pose(anim), rebuild_scene=True)
        anim_runtime["poll"].start()

    def _start_all_animation():
        _start_animation_from(0)

    def _toggle_animation_pause():
        anim = anim_runtime.get("anim")
        if anim is None:
            return
        try:
            paused = bool(anim.toggle_pause())
        except Exception:
            return
        anim_runtime["paused"] = paused
        pause_button.setText("Resume" if paused else "Pause")
        anim_phase.setText("Paused." if paused else "Running...")

    def _cancel_animation():
        if anim_runtime.get("anim") is not None:
            _finish_animation(cancelled=True)

    def _on_speed_changed(value):
        speed_value.setText(f"{value / 5.0:.1f}x")
        anim = anim_runtime.get("anim")
        if anim is not None:
            try:
                anim.speed = _anim_speed()
            except Exception:
                pass

    def update_step_controls(row):
        total = len(states)
        if total <= 0:
            step_label.setText("Step: 0 / 0")
            prev_button.setEnabled(False)
            next_button.setEnabled(False)
            return
        row = max(0, min(int(row), total - 1))
        step_label.setText(f"Step: {row} / {total - 1}")
        if anim_runtime.get("anim") is not None:
            prev_button.setEnabled(False)
            next_button.setEnabled(False)
            return
        prev_button.setEnabled(row > 0)
        next_button.setEnabled(row < total - 1)

    def select_step(row):
        if not states:
            return
        row = max(0, min(int(row), len(states) - 1))
        if step_list.currentRow() != row:
            step_list.setCurrentRow(row)
            return
        if anim_runtime.get("anim") is not None:
            update_step_controls(row)
            return
        if scene is not None:
            scene.render_state(states[row], reset_camera=False)
            update_move_highlights(row)
            update_route_overlay(row, render=False)
            update_access_directions(row, render=False)
            _refresh_all_camera_views(row)
            vtk_widget.GetRenderWindow().Render()
        update_step_controls(row)

    def on_step_selected(row):
        if row < 0:
            update_step_controls(0)
            return
        select_step(row)

    def add_step_items():
        step_list.clear()
        if not states:
            step_list.addItem("No step data")
            step_list.setEnabled(False)
            update_step_controls(0)
            return

        step_list.setEnabled(True)
        step_list.addItem(_make_step_item("Step 0  Start", None))
        for idx, move in enumerate(moves, 1):
            try:
                sx, sy, tx, ty, item = move
                text = f"Step {idx}  ({sx},{sy}) -> ({tx},{ty})  item={item}"
            except Exception:
                text = f"Step {idx}"
                item = None
            step_list.addItem(_make_step_item(text, item))

        step_list.setCurrentRow(0)
        update_step_controls(0)

    def _make_color_icon(priority):
        pixmap = QPixmap(14, 14)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        color_map = {
            1: "#db2e2e",
            2: "#339e47",
            3: "#2e5cd1",
            4: "#db9e29",
            5: "#8c52b8",
        }
        color = QColor(color_map.get(int(priority or 0), "#8b949e"))
        painter.setBrush(color)
        painter.setPen(QColor("#0b0e14"))
        painter.drawEllipse(2, 2, 10, 10)
        painter.end()
        return QIcon(pixmap)

    def _make_step_item(text, priority):
        item = QListWidgetItem(str(text))
        item.setIcon(_make_color_icon(priority))
        item.setForeground(QColor("#c9d1d9" if priority is not None else "#8b949e"))
        return item

    def _route_overlay_for_move(move_idx):
        if 0 <= move_idx < len(route_overlays):
            overlay = route_overlays[move_idx]
            if isinstance(overlay, dict):
                return overlay
        return {}

    def update_move_highlights(row):
        if scene is None or not hasattr(scene, "add_move_highlights"):
            return
        move_idx = int(row) - 1
        if move_idx < 0 or not (0 <= move_idx < len(moves)) or not (0 <= move_idx < len(states)):
            scene.clear_cell_highlights()
            return
        move_direction = move_directions[move_idx] if move_idx < len(move_directions) else None
        scene.add_move_highlights(moves[move_idx], states[move_idx], move_direction)

    def update_route_overlay(row=None, render=True):
        if scene is None:
            return
        if not route_button.isChecked():
            scene.clear_route_overlay()
            if render:
                vtk_widget.GetRenderWindow().Render()
            return

        if row is None:
            row = step_list.currentRow()
        move_idx = int(row) - 1
        if move_idx < 0:
            scene.clear_route_overlay()
        else:
            scene.add_route_overlay(_route_overlay_for_move(move_idx))
        if render:
            vtk_widget.GetRenderWindow().Render()

    def update_access_directions(row=None, render=True):
        if scene is None:
            return
        if not access_button.isChecked():
            scene.clear_access_directions()
        else:
            if row is None:
                row = step_list.currentRow()
            if 0 <= int(row) < len(states):
                scene.add_access_directions(access_lanes, states[int(row)])
        if render:
            vtk_widget.GetRenderWindow().Render()

    def open_time_log_dialog():
        if not moves:
            anim_phase.setText("No moves found for the log.")
            return

        move_times = []
        time_details = []
        if route_plans:
            try:
                from .animation_bridge import calculate_plan_times_from_animation

                params = dict(time_params)
                params["time_reverse_penalty"] = 0.0
                timed_plans = [
                    _prepare_plan_for_anim(plan, states[idx] if idx < len(states) else states[0])
                    for idx, plan in enumerate(route_plans)
                ]
                move_times, time_details = calculate_plan_times_from_animation(timed_plans, params)
            except Exception:
                move_times = []
                time_details = []

        def _to_float(value, default=0.0):
            try:
                return float(value)
            except Exception:
                return default

        comp_keys = [
            "time_approach_pick",
            "time_carry_to_place",
            "t_fork_prep",
            "t_travel_approach",
            "t_pick",
            "t_lower_safe",
            "t_travel_carry",
            "t_reverse",
            "t_raise_place",
            "t_place",
        ]
        comp_headers = {
            "time_approach_pick": "Approach+Pick",
            "time_carry_to_place": "Carry+Place",
            "t_fork_prep": "ForkPrep",
            "t_travel_approach": "TravelA",
            "t_pick": "Pick",
            "t_lower_safe": "Lower",
            "t_travel_carry": "TravelC",
            "t_reverse": "Reverse",
            "t_raise_place": "Raise",
            "t_place": "Place",
        }
        comp_totals = {key: 0.0 for key in comp_keys}

        rows = []
        running_sum = 0.0
        detail_rows = 0
        for idx, move in enumerate(moves):
            if isinstance(move, (list, tuple)) and len(move) >= 5:
                sx, sy, tx, ty, item = move[:5]
                move_text = f"({sx},{sy}) -> ({tx},{ty}) item={item}"
            else:
                move_text = str(move)

            detail = time_details[idx] if idx < len(time_details) else None
            if isinstance(detail, dict):
                detail_rows += 1
                relation = detail.get("relation", "-")
                pick_h = detail.get("pick_height", "-")
                place_h = detail.get("place_height", "-")
                comps = detail.get("components") if isinstance(detail.get("components"), dict) else {}
                detail_total = _to_float(detail.get("total_time", 0.0))
            else:
                relation = "-"
                pick_h = "-"
                place_h = "-"
                comps = {}
                detail_total = 0.0

            move_time = _to_float(move_times[idx]) if idx < len(move_times) else detail_total
            running_sum += move_time
            row_comps = {}
            for key in comp_keys:
                value = _to_float(comps.get(key, 0.0))
                row_comps[key] = value
                comp_totals[key] += value

            rows.append({
                "idx": idx + 1,
                "move": move_text,
                "relation": relation,
                "pick_h": pick_h,
                "place_h": place_h,
                "move_time": move_time,
                "total_time": running_sum,
                "comps": row_comps,
            })

        dialog = QDialog(window)
        dialog.setWindowTitle("Time Log")
        dialog.resize(1320, 620)
        dialog.setStyleSheet(
            "QDialog{background:#0f1115;color:#e6e6e6;}"
            "QLabel{color:#cfd6e6;}"
            "QTableWidget{background:#0b0e14;color:#e6e6e6;gridline-color:#242b36;alternate-background-color:#121825;}"
            "QHeaderView::section{background:#1a2333;color:#cfd6e6;padding:4px;border:0px;}"
        )

        layout = QVBoxLayout(dialog)
        total_final = rows[-1]["total_time"] if rows else 0.0
        info = QLabel(
            f"Moves: {len(moves)}   |   Final Total: {total_final:.2f}s   |   Details: {detail_rows}/{len(moves)}",
            dialog,
        )
        info.setStyleSheet("color:#cfd6e6; font-weight:600;")
        layout.addWidget(info)

        headers = ["#", "Move", "Rel", "PickH", "PlaceH", "Move (s)", "Total (s)"]
        headers += [comp_headers[key] for key in comp_keys]
        table = QTableWidget(len(rows), len(headers), dialog)
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for col in range(2, len(headers)):
            table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)

        for row_idx, row in enumerate(rows):
            values = [
                row["idx"],
                row["move"],
                row["relation"],
                row["pick_h"],
                row["place_h"],
                f"{row['move_time']:.2f}",
                f"{row['total_time']:.2f}",
            ]
            for col_idx, value in enumerate(values):
                table.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))
            for offset, key in enumerate(comp_keys, 7):
                table.setItem(row_idx, offset, QTableWidgetItem(f"{row['comps'][key]:.2f}"))

        layout.addWidget(table)

        total_moves = sum(row["move_time"] for row in rows)
        totals = QLabel(
            f"Move time total: {total_moves:.2f}s   |   Final total: {total_final:.2f}s\n"
            f"Component total (Approach+Pick): {comp_totals['time_approach_pick']:.2f}s   |   "
            f"Component total (Carry+Place): {comp_totals['time_carry_to_place']:.2f}s",
            dialog,
        )
        totals.setStyleSheet("color:#9fb0c8;")
        layout.addWidget(totals)

        dialog.exec()

    step_list.currentRowChanged.connect(on_step_selected)
    prev_button.clicked.connect(lambda: select_step(step_list.currentRow() - 1))
    next_button.clicked.connect(lambda: select_step(step_list.currentRow() + 1))
    speed_slider.valueChanged.connect(_on_speed_changed)
    anim_all_button.clicked.connect(_start_all_animation)
    pause_button.clicked.connect(_toggle_animation_pause)
    cancel_button.clicked.connect(_cancel_animation)
    time_params_button.clicked.connect(open_time_params_dialog)
    time_log_button.clicked.connect(open_time_log_dialog)
    mini_camera_pop_button.clicked.connect(open_camera_views_dialog)
    camera_views_button.clicked.connect(open_camera_views_dialog)
    route_button.toggled.connect(lambda _checked: update_route_overlay())
    access_button.toggled.connect(lambda _checked: update_access_directions())
    add_step_items()
    _set_anim_buttons(False)

    mini_state = _camera_view_state()
    if mini_state:
        _setup_camera_view_render_window(mini_camera_views, mini_camera_widget, mini_state)
        mini_camera_widget.GetRenderWindow().GetInteractor().Initialize()
        mini_camera_widget.GetRenderWindow().Render()
    else:
        mini_camera_panel.setVisible(False)

    interactor = vtk_widget.GetRenderWindow().GetInteractor()
    interactor.SetInteractorStyle(vtkInteractorStyleTrackballCamera())
    interactor.AddObserver("KeyPressEvent", on_camera_key)
    interactor.Initialize()

    def _on_main_close(event):
        try:
            anim_runtime["poll"].stop()
        except Exception:
            pass
        try:
            _cleanup_animator()
        except Exception:
            pass
        try:
            _finalize_camera_views(camera_views)
            _finalize_camera_views(mini_camera_views)
        except Exception:
            pass
        try:
            _finalize_vtk_widget(vtk_widget)
        except Exception:
            pass
        try:
            _OPEN_WINDOWS.remove(window)
        except ValueError:
            pass
        event.accept()

    window.closeEvent = _on_main_close

    window.show()
    vtk_widget.GetRenderWindow().Render()
    _OPEN_WINDOWS.append(window)

    if owns_app:
        app.exec()
