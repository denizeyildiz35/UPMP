# UPMP

UPMP is a Python package for stack-area generation, access-direction fixing,
and a parallel IDA* solver implemented in C++ with pybind11.

The package exposes the native solver through a small Python API and includes
an optional PySide6/VTK animation viewer.

## Installation

Core package:

```bash
pip install UPMP
```

With the animation viewer:

```bash
pip install "UPMP[animation]"
```

For local development from this repository:

```bash
pip install -e .
```

## Basic Usage

```python
from UPMP import idaStar

lanes = [
    [1, 2, 3],
    [1, 2, 3],
]

result = idaStar(
    lanes,
    log_fn=None,
    stop_get_best_fn=None,
    stop_fn=None,
    use_dsg_tiebreak=False,
    num_threads=8,
)

print(result)
```

The native extension module is also available as `ida_star_cpp`.

## Stack Area Generation

```python
from UPMP import stackAreaGenerator

depo = stackAreaGenerator(
    width=9,
    length=9,
    height=2,
    fill_pct=60,
    access="NSWE",
    max_priority=5,
    seed=123,
)

print(depo["priorities"])
```

## Access Direction Fixing

```python
from UPMP import accessDirectionFixing, idaStar, stackAreaGenerator

depo = stackAreaGenerator(9, 9, 2, fill_pct=60, access="NSWE", seed=123)

lanes, lane_matrix = accessDirectionFixing(depo)
details, lane_matrix = accessDirectionFixing(depo, return_details=True)

print(details["lanes"])

result = idaStar(lane_matrix)
print(result)
```

## Animation Viewer

Install the optional dependencies first:

```bash
pip install "UPMP[animation]"
```

Then:

```python
from UPMP import Animation, accessDirectionFixing, idaStar, stackAreaGenerator

area = stackAreaGenerator(5, 5, 3, 40, "NSWE", 5)
lanes, lane_matrix = accessDirectionFixing(area)
result = idaStar(lane_matrix)

Animation(result, area, lanes, lane_matrix)
```

## Build From Source

UPMP contains a C++ extension. Building from source requires a C++17 compiler,
CMake, pybind11, and scikit-build-core.

```bash
python -m pip install build scikit-build-core pybind11
python -m build
```

On Windows, Visual Studio Build Tools are required.
