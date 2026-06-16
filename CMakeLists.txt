cmake_minimum_required(VERSION 3.15)

project(ida_star_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(PYBIND11_FINDPYTHON ON)
find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(ida_star_cpp src/ida_star_cpp.cpp)

install(TARGETS ida_star_cpp
    LIBRARY DESTINATION .
    RUNTIME DESTINATION .
)
