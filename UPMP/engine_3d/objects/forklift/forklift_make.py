import math

import vtk


def _mk_mecanum_wheel(
    r=0.18,
    w=0.14,
    *,
    rollers=12,
    roller_r=0.040,
    roller_w=0.18,
    tilt_deg=45.0,
    mirror=False,
    tire_color=(0.10, 0.10, 0.10),
    roller_color=(0.28, 0.28, 0.28),
):
    wheel = vtk.vtkAssembly()

    tire_src = vtk.vtkCylinderSource()
    tire_src.SetRadius(r)
    tire_src.SetHeight(w)
    tire_src.SetResolution(40)
    tire_src.Update()

    tf_tire = vtk.vtkTransform()
    tpf = vtk.vtkTransformPolyDataFilter()
    tpf.SetInputData(tire_src.GetOutput())
    tpf.SetTransform(tf_tire)
    tpf.Update()

    tire_map = vtk.vtkPolyDataMapper()
    tire_map.SetInputData(tpf.GetOutput())
    tire_act = vtk.vtkActor()
    tire_act.SetMapper(tire_map)
    tire_act.GetProperty().SetColor(*tire_color)
    tire_act.GetProperty().SetAmbient(0.20)
    tire_act.GetProperty().SetDiffuse(0.80)
    tire_act.GetProperty().EdgeVisibilityOn()
    tire_act.GetProperty().SetEdgeColor(0.06, 0.06, 0.06)
    wheel.AddPart(tire_act)

    tilt = math.radians(tilt_deg) * (-1.0 if mirror else +1.0)
    ey = (0.0, 1.0, 0.0)

    for i in range(rollers):
        phi = (2.0 * math.pi / rollers) * i
        nx, nz = math.cos(phi), math.sin(phi)
        t_xz = (-nz, 0.0, nx)

        ax = math.cos(tilt) * t_xz[0] + math.sin(tilt) * ey[0]
        ay = math.cos(tilt) * t_xz[1] + math.sin(tilt) * ey[1]
        az = math.cos(tilt) * t_xz[2] + math.sin(tilt) * ey[2]
        alen = max(1e-9, math.sqrt(ax * ax + ay * ay + az * az))
        ax, ay, az = ax / alen, ay / alen, az / alen

        dr = r - roller_r * 0.15
        px, py, pz = dr * nx, 0.0, dr * nz

        rc = vtk.vtkCylinderSource()
        rc.SetRadius(roller_r)
        rc.SetHeight(roller_w)
        rc.SetResolution(28)
        rc.Update()

        dot = max(-1.0, min(1.0, ay))
        ang_deg = math.degrees(math.acos(dot))
        rx, ry, rz = az, 0.0, -ax
        rlen = max(1e-9, math.sqrt(rx * rx + ry * ry + rz * rz))
        if rlen > 1e-6:
            rx, ry, rz = rx / rlen, ry / rlen, rz / rlen
        else:
            rx, ry, rz = 1.0, 0.0, 0.0

        T = vtk.vtkTransform()
        T.RotateWXYZ(ang_deg, rx, ry, rz)
        T.Translate(px, py, pz)

        rtf = vtk.vtkTransformPolyDataFilter()
        rtf.SetInputData(rc.GetOutput())
        rtf.SetTransform(T)
        rtf.Update()

        rm = vtk.vtkPolyDataMapper()
        rm.SetInputData(rtf.GetOutput())
        ra = vtk.vtkActor()
        ra.SetMapper(rm)
        ra.GetProperty().SetColor(*roller_color)
        ra.GetProperty().SetAmbient(0.18)
        ra.GetProperty().SetDiffuse(0.82)
        wheel.AddPart(ra)

    return wheel


def araba_olustur_mecanum(
    *,
    chassis=(1.50, 0.80, 1.20),
    wheel_r=0.18,
    wheel_w=0.14,
    track=0.78,
    wheelbase=1.20,
    body_color=(0.30, 0.30, 0.32),
):
    car = vtk.vtkAssembly()
    parts = {}

    L, W, H = chassis
    box = vtk.vtkCubeSource()
    box.SetXLength(L)
    box.SetYLength(W)
    box.SetZLength(H)
    box.Update()
    mp = vtk.vtkPolyDataMapper()
    mp.SetInputData(box.GetOutput())
    ac = vtk.vtkActor()
    ac.SetMapper(mp)
    ac.GetProperty().SetColor(*body_color)
    ac.GetProperty().SetAmbient(0.18)
    ac.GetProperty().SetDiffuse(0.82)
    ac.GetProperty().EdgeVisibilityOn()
    ac.GetProperty().SetEdgeColor(0.07, 0.07, 0.07)
    ac.SetPosition(0.0, 0.0, wheel_r + H * 0.5)
    car.AddPart(ac)

    cap_t = 0.06
    cap_L = L * 0.55
    cap = vtk.vtkCubeSource()
    cap.SetXLength(cap_L)
    cap.SetYLength(W * 0.96)
    cap.SetZLength(cap_t)
    cap.Update()
    cap_mp = vtk.vtkPolyDataMapper()
    cap_mp.SetInputData(cap.GetOutput())
    cap_ac = vtk.vtkActor()
    cap_ac.SetMapper(cap_mp)
    cap_ac.GetProperty().SetColor(0.12, 0.12, 0.14)
    cap_ac.GetProperty().SetAmbient(0.18)
    cap_ac.GetProperty().SetDiffuse(0.82)
    cap_ac.GetProperty().EdgeVisibilityOn()
    cap_ac.GetProperty().SetEdgeColor(0.05, 0.05, 0.05)

    cap_tf = vtk.vtkTransform()
    cap_tf.Translate(-L * 0.15, 0.0, wheel_r + H + cap_t * 0.5)
    cap_tf.RotateY(10)
    cap_ac.SetPosition(0, 0, 0)
    cap_ac.SetUserTransform(cap_tf)
    car.AddPart(cap_ac)

    Lx = wheelbase * 0.5
    Ly = track * 0.5
    z_wheel = wheel_r

    w_FL = _mk_mecanum_wheel(wheel_r, wheel_w, mirror=True)
    w_FR = _mk_mecanum_wheel(wheel_r, wheel_w, mirror=False)
    w_RL = _mk_mecanum_wheel(wheel_r, wheel_w, mirror=False)
    w_RR = _mk_mecanum_wheel(wheel_r, wheel_w, mirror=True)

    w_FL.SetPosition(+Lx, +Ly, z_wheel)
    w_FR.SetPosition(+Lx, -Ly, z_wheel)
    w_RL.SetPosition(-Lx, +Ly, z_wheel)
    w_RR.SetPosition(-Lx, -Ly, z_wheel)

    car.AddPart(w_FL)
    car.AddPart(w_FR)
    car.AddPart(w_RL)
    car.AddPart(w_RR)

    parts["wheels"] = {"FL": w_FL, "FR": w_FR, "RL": w_RL, "RR": w_RR}
    parts["wheelbase"] = float(wheelbase)
    parts["track"] = float(track)
    parts["chassis_size"] = (L, W, H)
    parts["wheel_radius"] = float(wheel_r)

    return car, parts
