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
option(DOWNLOAD_LIBTORCH "Automatically download LibTorch if not found" ON)

# Set default build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Find packages
find_package(Threads REQUIRED)
find_package(ZLIB REQUIRED)
find_package(gRPC CONFIG REQUIRED)
find_package(Protobuf REQUIRED)

# Try to find PyTorch (LibTorch)
find_package(Torch QUIET)

# Auto-download LibTorch if not found and option is enabled
if(NOT Torch_FOUND AND DOWNLOAD_LIBTORCH)
    message(STATUS "LibTorch not found. Downloading...")
    include(cmake/DownloadLibTorch.cmake)
    download_libtorch()
    find_package(Torch REQUIRED)
endif()

if(NOT Torch_FOUND)
    message(FATAL_ERROR "PyTorch (LibTorch) is required. Download from https://pytorch.org/ or enable DOWNLOAD_LIBTORCH option")
endif()

message(STATUS "Found LibTorch: ${TORCH_INSTALL_PREFIX}")
message(STATUS "LibTorch version: ${Torch_VERSION}")

# Source files
set(WORKER_SOURCES
    src/main.cpp
    src/worker.cpp
    src/config/config_loader.cpp
    src/grpc/client.cpp
    src/grpc/heartbeat.cpp
    src/training/trainer.cpp
    src/training/data_loader.cpp
    src/training/checkpoint.cpp
    src/utils/performance.cpp
    src/utils/simd_ops.cpp
    src/utils/memory_pool.cpp
    src/models/model_loader.cpp
    # src/utils/logger.cpp  # TODO: Implement
)

# Include directories
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${Protobuf_INCLUDE_DIRS}
    ${CMAKE_CURRENT_BINARY_DIR}  # For generated proto files
    ${TORCH_INCLUDE_DIRS}
)

# Main executable
add_executable(meshml-worker ${WORKER_SOURCES})

# Set C++17 features required by LibTorch
set_property(TARGET meshml-worker PROPERTY CXX_STANDARD 17)

# Platform-specific optimizations
if(CMAKE_SYSTEM_PROCESSOR MATCHES "x86_64|AMD64")
    # Enable AVX2 on x86_64 if supported
    if(NOT MSVC)
        target_compile_options(meshml-worker PRIVATE -mavx2 -mfma)
        message(STATUS "Enabled AVX2 and FMA optimizations")
    else()
        target_compile_options(meshml-worker PRIVATE /arch:AVX2)
        message(STATUS "Enabled AVX2 optimizations (MSVC)")
    endif()
elseif(CMAKE_SYSTEM_PROCESSOR MATCHES "arm64|aarch64|ARM64")
    # Enable NEON on ARM
    if(NOT MSVC)
        target_compile_options(meshml-worker PRIVATE -march=armv8-a+simd)
        message(STATUS "Enabled NEON optimizations (ARM)")
    endif()
endif()

# Link libraries
target_link_libraries(meshml-worker
    PRIVATE
        protobuf::libprotobuf
        gRPC::grpc++
        Threads::Threads
        ZLIB::ZLIB
        ${TORCH_LIBRARIES}
)

# Copy PyTorch DLLs on Windows
if(MSVC)
    file(GLOB TORCH_DLLS "${TORCH_INSTALL_PREFIX}/lib/*.dll")
    add_custom_command(TARGET meshml-worker
        POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
        ${TORCH_DLLS}
        $<TARGET_FILE_DIR:meshml-worker>)
endif()

# CUDA support
if(USE_CUDA)
    enable_language(CUDA)
    find_package(CUDAToolkit REQUIRED)
    
    # Add CUDA sources
    target_sources(meshml-worker PRIVATE 
        src/cuda/cuda_kernels.cu
    )
    
    # Set CUDA standard
    set_target_properties(meshml-worker PROPERTIES
        CUDA_STANDARD 17
        CUDA_STANDARD_REQUIRED ON
    )
    
    # CUDA compile options
    target_compile_options(meshml-worker PRIVATE
        $<$<COMPILE_LANGUAGE:CUDA>:
            --expt-relaxed-constexpr
            --use_fast_math
            -arch=sm_60  # Adjust based on your GPU
        >
    )
    
    target_link_libraries(meshml-worker PRIVATE 
        CUDA::cudart
        CUDA::cuda_driver
    )
    target_compile_definitions(meshml-worker PRIVATE USE_CUDA)
    
    message(STATUS "CUDA support enabled")
    message(STATUS "CUDA Toolkit: ${CUDAToolkit_VERSION}")
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

# Examples
option(BUILD_EXAMPLES "Build example executables" ON)

if(BUILD_EXAMPLES)
    # Config example
    add_executable(config_example examples/config_example.cpp)
    target_link_libraries(config_example PRIVATE
        protobuf::libprotobuf
        gRPC::grpc++
        Threads::Threads
        ZLIB::ZLIB
        ${TORCH_LIBRARIES}
    )
    set_property(TARGET config_example PROPERTY CXX_STANDARD 17)
    
    # Model loader example
    add_executable(model_loader_example 
        examples/model_loader_example.cpp
        src/models/model_loader.cpp
    )
    target_link_libraries(model_loader_example PRIVATE
        ${TORCH_LIBRARIES}
    )
    set_property(TARGET model_loader_example PROPERTY CXX_STANDARD 17)
    
    # CUDA kernels example (only if CUDA enabled)
    if(USE_CUDA)
        add_executable(cuda_kernels_example 
            examples/cuda_kernels_example.cpp
            src/cuda/cuda_kernels.cu
        )
        target_link_libraries(cuda_kernels_example PRIVATE
            ${TORCH_LIBRARIES}
            CUDA::cudart
            CUDA::cuda_driver
        )
        set_target_properties(cuda_kernels_example PROPERTIES
            CXX_STANDARD 17
            CUDA_STANDARD 17
            CUDA_STANDARD_REQUIRED ON
        )
        target_compile_options(cuda_kernels_example PRIVATE
            $<$<COMPILE_LANGUAGE:CUDA>:
                --expt-relaxed-constexpr
                --use_fast_math
                -arch=sm_60
            >
        )
        target_compile_definitions(cuda_kernels_example PRIVATE USE_CUDA)
        
        message(STATUS "Building CUDA example: cuda_kernels_example")
    endif()
    
    message(STATUS "Building examples: config_example, model_loader_example")
endif()

# Testing
if(BUILD_TESTS)
    enable_testing()
    
    # Add tests subdirectory with comprehensive tests
    add_subdirectory(tests)
    
    # Keep old test target for backwards compatibility (but make it minimal)
    find_package(GTest REQUIRED)

    add_executable(worker-tests-legacy
        tests/test_simple.cpp
    )

    target_link_libraries(worker-tests-legacy
        PRIVATE
            GTest::gtest
            GTest::gtest_main
            protobuf::libprotobuf
            gRPC::grpc++
    )

    if(Torch_FOUND)
        target_link_libraries(worker-tests-legacy PRIVATE ${TORCH_LIBRARIES})
    endif()

    include(GoogleTest)
    gtest_discover_tests(worker-tests-legacy)
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
