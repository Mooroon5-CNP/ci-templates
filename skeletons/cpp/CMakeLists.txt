cmake_minimum_required(VERSION 3.16)
project(cnp_test_cpp CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(routes src/routes.cpp)
target_include_directories(routes PUBLIC src)

add_executable(server src/main.cpp)
target_link_libraries(server PRIVATE routes)

enable_testing()
add_executable(routes_test tests/routes_test.cpp)
target_link_libraries(routes_test PRIVATE routes)
add_test(NAME routes_test COMMAND routes_test)
