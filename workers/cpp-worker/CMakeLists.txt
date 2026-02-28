cmake_minimum_required(VERSION 3.20)
project(meshml-cpp-worker VERSION 0.1.0 LANGUAGES CXX)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Build options
option(BUILD_TESTS "Build test executables" ON)
option(USE_CUDA "Enable CUDA support" OFF)
option(USE_METAL "Enable Metal support (macOS)" OFF)

# Find packages
find_package(Protobuf REQUIRED)
find_package(gRPC CONFIG REQUIRED)
find_package(Threads REQUIRED)

# Try to find PyTorch (LibTorch)
find_package(Torch QUIET)
if(NOT Torch_FOUND)
    message(WARNING "PyTorch not found. Download from https://pytorch.org/")
endif()

# Source files
set(WORKER_SOURCES
    src/main.cpp
    src/worker.cpp
    src/grpc/client.cpp
    src/compute/tensor_ops.cpp
    src/compute/forward_pass.cpp
    src/compute/backward_pass.cpp
    src/memory/pool_allocator.cpp
)

# Include directories
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${Protobuf_INCLUDE_DIRS}
    ${CMAKE_CURRENT_BINARY_DIR}  # For generated proto files
)

# Main executable
add_executable(meshml-worker ${WORKER_SOURCES})

# Link libraries
target_link_libraries(meshml-worker
    PRIVATE
        protobuf::libprotobuf
        gRPC::grpc++
        Threads::Threads
)

# Link PyTorch if found
if(Torch_FOUND)
    target_link_libraries(meshml-worker PRIVATE ${TORCH_LIBRARIES})
    target_compile_definitions(meshml-worker PRIVATE USE_TORCH)
endif()

# CUDA support
if(USE_CUDA)
    enable_language(CUDA)
    find_package(CUDAToolkit REQUIRED)
    target_sources(meshml-worker PRIVATE src/acceleration/cuda_kernel.cu)
    target_link_libraries(meshml-worker PRIVATE CUDA::cudart)
    target_compile_definitions(meshml-worker PRIVATE USE_CUDA)
endif()

# Metal support (macOS)
if(USE_METAL AND APPLE)
    target_sources(meshml-worker PRIVATE src/acceleration/metal_kernel.metal)
    target_compile_definitions(meshml-worker PRIVATE USE_METAL)
endif()

# Compiler warnings
if(MSVC)
    target_compile_options(meshml-worker PRIVATE /W4)
else()
    target_compile_options(meshml-worker PRIVATE -Wall -Wextra -Wpedantic)
endif()

# Testing
if(BUILD_TESTS)
    enable_testing()
    find_package(GTest REQUIRED)

    add_executable(worker-tests
        tests/test_tensor_ops.cpp
        tests/test_grpc_client.cpp
        src/compute/tensor_ops.cpp
        src/grpc/client.cpp
        src/memory/pool_allocator.cpp
    )

    target_link_libraries(worker-tests
        PRIVATE
            GTest::gtest
            GTest::gtest_main
            protobuf::libprotobuf
            gRPC::grpc++
    )

    if(Torch_FOUND)
        target_link_libraries(worker-tests PRIVATE ${TORCH_LIBRARIES})
    endif()

    include(GoogleTest)
    gtest_discover_tests(worker-tests)
endif()

# Installation
install(TARGETS meshml-worker
    RUNTIME DESTINATION bin
)

# Print configuration summary
message(STATUS "MeshML C++ Worker Configuration:")
message(STATUS "  C++ Standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "  Build Type: ${CMAKE_BUILD_TYPE}")
message(STATUS "  PyTorch Support: ${Torch_FOUND}")
message(STATUS "  CUDA Support: ${USE_CUDA}")
message(STATUS "  Metal Support: ${USE_METAL}")
message(STATUS "  Build Tests: ${BUILD_TESTS}")
