import ida_star_cpp
from UPMP import accessDirectionFixing, idaStar, stackAreaGenerator
from UPMP.accessDirectionFixing import _virtual_lanes_raw_from_specs
from UPMP.converter import convert_ida_result_to_animation_data


def test_import():
    assert ida_star_cpp is not None
    assert hasattr(ida_star_cpp, "ida_star_cpp")
    assert callable(idaStar)
    assert callable(stackAreaGenerator)
    assert callable(accessDirectionFixing)


def test_small_call():
    lanes = [[1], [2]]

    result = ida_star_cpp.ida_star_cpp(
        lanes,
        log_fn=None,
        stop_get_best_fn=None,
        stop_fn=None,
        use_dsg_tiebreak=False,
        num_threads=1,
    )

    assert result is not None
    assert result["num_moves"] == 0


def test_stack_area_generator_depo_dict():
    depo = stackAreaGenerator(
        width=4,
        length=3,
        height=2,
        fill_pct=50,
        access="NW",
        max_priority=5,
        seed=7,
    )

    assert depo["size"] == {"width": 4, "length": 3}
    assert depo["max_floor"] == 2
    assert depo["doors"] == {"N": True, "E": False, "S": False, "W": True}
    assert len(depo["priorities"]) == 4
    assert len(depo["priorities"][0]) == 3
    assert depo["capacity_matrix"] == [[2, 2, 2] for _ in range(4)]
    assert depo["meta"]["block_count"] == 12

    for row in depo["priorities"]:
        for cell in row:
            assert len(cell) <= 2
            assert all(1 <= p <= 5 for p in cell)


def test_stack_area_generator_seed_is_deterministic():
    first = stackAreaGenerator(3, 3, 2, fill_pct=60, access="NSWE", seed=11)
    second = stackAreaGenerator(3, 3, 2, fill_pct=60, access="NSWE", seed=11)

    assert first["layout"] == second["layout"]
    assert first["priorities"] == second["priorities"]


def test_access_direction_fixing_details():
    pytest = __import__("pytest")
    pytest.importorskip("ortools")

    depo = stackAreaGenerator(3, 3, 1, fill_pct=60, access="NW", seed=3)
    result, lane_matrix = accessDirectionFixing(depo, return_details=True)

    assert result["lanes"]
    assert result["lane_matrix"] == lane_matrix
    assert result["status"]
    assert result["matrix"]
    assert isinstance(lane_matrix, list)
    assert all(lane for lane in lane_matrix)
    assert sum(len(lane) for lane in lane_matrix) == (
        depo["size"]["width"] * depo["size"]["length"] * depo["max_floor"]
    )
    for lane in result["lanes"]:
        assert lane["direction"] in {"N", "W"}
        assert lane["cells"]


def test_virtual_lanes_raw_from_specs_matches_main_app_shape():
    priorities = [
        [[1, 0], [2]],
        [[0, 3], [4, 0]],
    ]
    lane_specs = (
        ("W", ((0, 0), (1, 0))),
        ("N", ((1, 1), (0, 1))),
    )

    assert _virtual_lanes_raw_from_specs(lane_specs, priorities, height=3) == [
        [1, 0, 0, 0, 3, 0],
        [4, 0, 0, 2, 0, 0],
    ]


def test_upmp_idastar_call():
    lanes = [[1], [2]]

    result = idaStar(
        lanes,
        log_fn=None,
        stop_get_best_fn=None,
        stop_fn=None,
        use_dsg_tiebreak=False,
        num_threads=1,
    )

    assert result is not None
    assert result["num_moves"] == 0


def test_converter_builds_physical_animation_data():
    depo = stackAreaGenerator(3, 3, 2, fill_pct=40, access="NW", seed=2)
    lanes, lane_matrix = accessDirectionFixing(depo)
    result = idaStar(lane_matrix, num_threads=1)

    data = convert_ida_result_to_animation_data(result, depo, lanes, lane_matrix)

    assert data["width"] == 3
    assert data["length"] == 3
    assert data["height"] == 2
    assert data["num_moves"] == len(result["moves"])
    assert len(data["states_frozen"]) == data["num_moves"] + 1
    assert len(data["moves"]) == data["num_moves"]
    assert len(data["move_directions"]) == data["num_moves"]
