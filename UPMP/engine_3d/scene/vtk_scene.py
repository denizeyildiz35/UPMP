import vtk


_ARROW_GLYPH_CACHE = None


def _get_arrow_glyph_cache():
    global _ARROW_GLYPH_CACHE
    if _ARROW_GLYPH_CACHE is not None:
        return _ARROW_GLYPH_CACHE
    arrow_map = {"N": "^", "S": "v", "E": ">", "W": "<"}
    cache = {}
    for d, sym in arrow_map.items():
        vt = vtk.vtkVectorText()
        vt.SetText(sym)
        vt.Update()
        pd = vt.GetOutput()
        pts_obj = pd.GetPoints()
        coords = [pts_obj.GetPoint(i) for i in range(pts_obj.GetNumberOfPoints())] if pts_obj else []
        cells_iter = pd.GetPolys()
        cell_id_lists = []
        if cells_iter is not None:
            cells_iter.InitTraversal()
            id_list = vtk.vtkIdList()
            while cells_iter.GetNextCell(id_list):
                cell_id_lists.append([id_list.GetId(j) for j in range(id_list.GetNumberOfIds())])
        if coords:
            bnds = pd.GetBounds()
            cx_glyph = 0.5 * (bnds[0] + bnds[1])
            cy_glyph = 0.5 * (bnds[2] + bnds[3])
        else:
            cx_glyph = cy_glyph = 0.0
        cache[d] = (coords, cell_id_lists, cx_glyph, cy_glyph)
    _ARROW_GLYPH_CACHE = cache
    return cache


def build_access_arrow_actor(pending_arrows, scale=0.4, z_offset=0.6, color=(1.0, 1.0, 1.0)):
    arrows = list(pending_arrows or [])
    if not arrows:
        return None

    glyphs = _get_arrow_glyph_cache()
    out_pts = vtk.vtkPoints()
    out_polys = vtk.vtkCellArray()

    for (bx, by, bz_base, dstr) in arrows:
        glyph = glyphs.get(dstr)
        if glyph is None:
            continue
        coords, cell_id_lists, cx_glyph, cy_glyph = glyph
        if not coords:
            continue
        base_idx = out_pts.GetNumberOfPoints()
        for (px, py, pz) in coords:
            out_pts.InsertNextPoint(
                bx + (px - cx_glyph) * scale,
                by + (py - cy_glyph) * scale,
                bz_base + z_offset + pz * scale,
            )
        for ids in cell_id_lists:
            il = vtk.vtkIdList()
            il.SetNumberOfIds(len(ids))
            for j, cid in enumerate(ids):
                il.SetId(j, base_idx + cid)
            out_polys.InsertNextCell(il)

    if out_pts.GetNumberOfPoints() == 0:
        return None

    pd_out = vtk.vtkPolyData()
    pd_out.SetPoints(out_pts)
    pd_out.SetPolys(out_polys)

    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(pd_out)

    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(*color)
    actor.PickableOff()
    return actor
