# UPMP

Parallel IDA* solver written in C++ with pybind11.

## Installation

```bash
pip install -e .
```

## Usage

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

The native module is still available as `ida_star_cpp` for existing code.

## Stack area generation

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

## Access direction fixing

```python
from UPMP import accessDirectionFixing, idaStar

lanes, lane_matrix = accessDirectionFixing(depo)

details, lane_matrix = accessDirectionFixing(depo, return_details=True)
print(details["lanes"])

# lane_matrix is padded to width * length * height slots.
result = idaStar(lane_matrix)
```
