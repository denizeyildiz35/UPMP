import vtk


def attach_fork_addon(
    vehicle_root: vtk.vtkAssembly,
    vehicle_parts: dict,
    fork_len: float = 1.6,
    fork_t: float = 0.12,
    mast_h: float = 2.4,
    mast_w: float = 1.0,
    front_offset: float = 0.18,
    fork_mount_x: float = 0.06,
    color_fork=(0.12, 0.12, 0.14),
    color_mast=(0.12, 0.12, 0.14),
):
    L, W, H = vehicle_parts.get("chassis_size", (2.2, 1.2, 0.5))
    wheel_r = float(vehicle_parts.get("wheel_radius", 0.28))

    def box(x, y, z, col):
        s = vtk.vtkCubeSource()
        s.SetXLength(x)
        s.SetYLength(y)
        s.SetZLength(z)
        m = vtk.vtkPolyDataMapper()
        m.SetInputConnection(s.GetOutputPort())
        a = vtk.vtkActor()
        a.SetMapper(m)
        a.GetProperty().SetColor(*col)
        a.GetProperty().SetSpecular(0.25)
        return a

    mast = vtk.vtkAssembly()
    mast_x = +L * 0.5 + float(front_offset)
    mast.SetPosition(mast_x, 0.0, 0.0)

    rail_h, rail_t, rail_d = float(mast_h), 0.12, 0.22
    rail_L = box(rail_d, rail_t, rail_h, color_mast)
    rail_R = box(rail_d, rail_t, rail_h, color_mast)
    rail_L.SetPosition(0.0, -mast_w * 0.5, wheel_r + rail_h * 0.5)
    rail_R.SetPosition(0.0, +mast_w * 0.5, wheel_r + rail_h * 0.5)
    back = box(rail_d * 0.6, mast_w, rail_h * 0.9, color_mast)
    back.SetPosition(-rail_d * 0.3, 0.0, wheel_r + rail_h * 0.55)

    mast.AddPart(rail_L)
    mast.AddPart(rail_R)
    mast.AddPart(back)

    carriage = vtk.vtkAssembly()
    carr_plate = box(0.14, mast_w * 0.9, 0.42, color_mast)
    carr_plate.SetPosition(0.0, 0.0, wheel_r + 0.11)
    carriage.AddPart(carr_plate)
    mast.AddPart(carriage)

    EPS = 0.004
    drop = float(vehicle_parts.get("body_drop", 0.0))
    z0 = wheel_r - drop
    body_top_z = wheel_r + H - drop
    gap_x = float(mast_x) - (float(L) * 0.5)
    bridge_x = max(0.06, gap_x - 0.02)
    bridge_h = max(0.18, min(1.2 * H, (body_top_z - z0) - 0.02))
    bridge_y = W * 1.04

    bridge = box(bridge_x, bridge_y, bridge_h, color_mast)
    bridge.SetPosition((float(L) * 0.5) + bridge_x * 0.5 - EPS, 0.0, z0 + bridge_h * 0.5)
    vehicle_root.AddPart(bridge)

    def make_fork(y_ofs: float):
        s = vtk.vtkCubeSource()
        s.SetXLength(fork_len)
        s.SetYLength(fork_t)
        s.SetZLength(fork_t * 2.0)
        m = vtk.vtkPolyDataMapper()
        m.SetInputConnection(s.GetOutputPort())
        a = vtk.vtkActor()
        a.SetMapper(m)
        a.GetProperty().SetColor(*color_fork)
        a.SetOrigin(-fork_len * 0.5, 0.0, 0.0)
        a.SetPosition(float(fork_mount_x), float(y_ofs), wheel_r + fork_t - 0.1)
        return a

    y_ofs = max(0.18, mast_w * 0.25)
    fork_L = make_fork(-y_ofs)
    fork_R = make_fork(+y_ofs)

    carriage.AddPart(fork_L)
    carriage.AddPart(fork_R)
    vehicle_root.AddPart(mast)

    vehicle_parts.setdefault("fork_addon", {})
    vehicle_parts["fork_addon"].update({
        "mast": mast,
        "carriage": carriage,
        "fork_L": fork_L,
        "fork_R": fork_R,
        "fork_len": float(fork_len),
        "fork_t": float(fork_t),
        "wheel_r": float(wheel_r),
        "mast_x": float(mast_x),
        "fork_mount": {"x": float(fork_mount_x), "z": float(wheel_r + fork_t)},
        "carriage_z": 0.0,
        "levels": (0.0, 0.45, 0.90, 1.35),
    })
    return mast, carriage, fork_L, fork_R
