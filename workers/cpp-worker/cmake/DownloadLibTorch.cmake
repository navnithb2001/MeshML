# DownloadLibTorch.cmake
# Automatically downloads LibTorch based on platform

function(download_libtorch)
    set(LIBTORCH_DIR "${CMAKE_BINARY_DIR}/libtorch")
    
    # Determine platform and URL
    if(APPLE)
        if(CMAKE_SYSTEM_PROCESSOR MATCHES "arm64")
            # Apple Silicon (M1/M2)
            set(LIBTORCH_URL "https://download.pytorch.org/libtorch/cpu/libtorch-macos-arm64-2.0.1.zip")
        else()
            # Intel Mac
            set(LIBTORCH_URL "https://download.pytorch.org/libtorch/cpu/libtorch-macos-x86_64-2.0.1.zip")
        endif()
    elseif(UNIX)
        # Linux
        if(USE_CUDA)
            set(LIBTORCH_URL "https://download.pytorch.org/libtorch/cu118/libtorch-cxx11-abi-shared-with-deps-2.0.1%2Bcu118.zip")
        else()
            set(LIBTORCH_URL "https://download.pytorch.org/libtorch/cpu/libtorch-cxx11-abi-shared-with-deps-2.0.1%2Bcpu.zip")
        endif()
    elseif(WIN32)
        # Windows
        if(USE_CUDA)
            set(LIBTORCH_URL "https://download.pytorch.org/libtorch/cu118/libtorch-win-shared-with-deps-2.0.1%2Bcu118.zip")
        else()
            set(LIBTORCH_URL "https://download.pytorch.org/libtorch/cpu/libtorch-win-shared-with-deps-2.0.1%2Bcpu.zip")
        endif()
    else()
        message(FATAL_ERROR "Unsupported platform for automatic LibTorch download")
    endif()
    
    # Download and extract if not already present
    if(NOT EXISTS "${LIBTORCH_DIR}")
        message(STATUS "Downloading LibTorch from ${LIBTORCH_URL}")
        file(DOWNLOAD
            "${LIBTORCH_URL}"
            "${CMAKE_BINARY_DIR}/libtorch.zip"
            SHOW_PROGRESS
            TIMEOUT 600
        )
        
        message(STATUS "Extracting LibTorch...")
        file(ARCHIVE_EXTRACT
            INPUT "${CMAKE_BINARY_DIR}/libtorch.zip"
            DESTINATION "${CMAKE_BINARY_DIR}"
        )
        
        file(REMOVE "${CMAKE_BINARY_DIR}/libtorch.zip")
        message(STATUS "LibTorch downloaded and extracted to ${LIBTORCH_DIR}")
    endif()
    
    # Set CMAKE_PREFIX_PATH so find_package can locate LibTorch
    list(APPEND CMAKE_PREFIX_PATH "${LIBTORCH_DIR}")
    set(CMAKE_PREFIX_PATH "${CMAKE_PREFIX_PATH}" PARENT_SCOPE)
endfunction()
