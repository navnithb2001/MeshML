#!/bin/bash

# MeshML C++ Worker Test Runner
# This script builds and runs all tests for the C++ worker

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"

# Default options
BUILD_TYPE="Release"
USE_CUDA=OFF
RUN_BENCHMARKS=OFF
GENERATE_COVERAGE=OFF
CLEAN_BUILD=OFF
FILTER=""

# Help message
function show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Build and run tests for MeshML C++ Worker

OPTIONS:
    -h, --help              Show this help message
    -d, --debug             Build in Debug mode (default: Release)
    -c, --cuda              Enable CUDA support
    -b, --benchmarks        Run performance benchmarks (slow)
    -g, --coverage          Generate code coverage report (requires Debug mode)
    -f, --filter PATTERN    Run only tests matching PATTERN
    -C, --clean             Clean build directory before building
    -v, --verbose           Verbose output

EXAMPLES:
    $0                                    # Run all tests (Release build)
    $0 --debug --coverage                 # Debug build with coverage
    $0 --cuda                             # Run tests with CUDA support
    $0 --filter ConfigLoaderTest.*        # Run only config loader tests
    $0 --benchmarks                       # Run including benchmarks
    $0 --clean --debug                    # Clean build in Debug mode

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -d|--debug)
            BUILD_TYPE="Debug"
            shift
            ;;
        -c|--cuda)
            USE_CUDA=ON
            shift
            ;;
        -b|--benchmarks)
            RUN_BENCHMARKS=ON
            shift
            ;;
        -g|--coverage)
            GENERATE_COVERAGE=ON
            BUILD_TYPE="Debug"
            shift
            ;;
        -f|--filter)
            FILTER="$2"
            shift 2
            ;;
        -C|--clean)
            CLEAN_BUILD=ON
            shift
            ;;
        -v|--verbose)
            set -x
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Print configuration
echo -e "${BLUE}=== MeshML C++ Worker Test Runner ===${NC}"
echo -e "${BLUE}Configuration:${NC}"
echo -e "  Build Type: ${GREEN}${BUILD_TYPE}${NC}"
echo -e "  CUDA Support: ${GREEN}${USE_CUDA}${NC}"
echo -e "  Run Benchmarks: ${GREEN}${RUN_BENCHMARKS}${NC}"
echo -e "  Generate Coverage: ${GREEN}${GENERATE_COVERAGE}${NC}"
if [ -n "$FILTER" ]; then
    echo -e "  Test Filter: ${GREEN}${FILTER}${NC}"
fi
echo ""

# Clean build if requested
if [ "$CLEAN_BUILD" = "ON" ]; then
    echo -e "${YELLOW}Cleaning build directory...${NC}"
    rm -rf "$BUILD_DIR"
fi

# Create build directory
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

# Configure CMake
echo -e "${BLUE}Configuring CMake...${NC}"
CMAKE_ARGS=(
    "-DCMAKE_BUILD_TYPE=${BUILD_TYPE}"
    "-DBUILD_TESTS=ON"
    "-DUSE_CUDA=${USE_CUDA}"
)

if [ "$GENERATE_COVERAGE" = "ON" ]; then
    CMAKE_ARGS+=("-DCMAKE_CXX_FLAGS=--coverage")
fi

cmake "${CMAKE_ARGS[@]}" ..

# Build
echo -e "${BLUE}Building...${NC}"
NPROC=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
make -j"${NPROC}"

# Run tests
echo -e "${BLUE}Running tests...${NC}"

GTEST_ARGS=()
if [ -n "$FILTER" ]; then
    GTEST_ARGS+=("--gtest_filter=${FILTER}")
fi

if [ "$RUN_BENCHMARKS" = "ON" ]; then
    GTEST_ARGS+=("--gtest_also_run_disabled_tests")
    GTEST_ARGS+=("--gtest_filter=*DISABLED_*")
fi

# Run the tests
if [ -f "./tests/meshml_tests" ]; then
    ./tests/meshml_tests "${GTEST_ARGS[@]}"
    TEST_RESULT=$?
else
    echo -e "${RED}Error: Test executable not found!${NC}"
    exit 1
fi

# Check test result
if [ $TEST_RESULT -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
else
    echo -e "${RED}✗ Some tests failed!${NC}"
    exit $TEST_RESULT
fi

# Generate coverage report if requested
if [ "$GENERATE_COVERAGE" = "ON" ]; then
    echo -e "${BLUE}Generating coverage report...${NC}"
    
    # Check for required tools
    if ! command -v lcov &> /dev/null; then
        echo -e "${RED}Error: lcov not found. Install with: brew install lcov${NC}"
        exit 1
    fi
    
    if ! command -v genhtml &> /dev/null; then
        echo -e "${RED}Error: genhtml not found. Install with: brew install lcov${NC}"
        exit 1
    fi
    
    # Generate coverage
    lcov --directory . --capture --output-file coverage.info
    lcov --remove coverage.info '/usr/*' '*/tests/*' '*/build/*' --output-file coverage.info.cleaned
    genhtml -o coverage coverage.info.cleaned
    
    echo -e "${GREEN}Coverage report generated in: ${BUILD_DIR}/coverage/index.html${NC}"
    
    # Try to open the report
    if command -v open &> /dev/null; then
        open coverage/index.html
    elif command -v xdg-open &> /dev/null; then
        xdg-open coverage/index.html
    fi
fi

# Print summary
echo ""
echo -e "${GREEN}=== Test Summary ===${NC}"
echo -e "Build directory: ${BUILD_DIR}"
echo -e "Test executable: ${BUILD_DIR}/tests/meshml_tests"
echo ""

# Print quick commands for re-running
echo -e "${BLUE}Quick commands:${NC}"
echo -e "  Re-run all tests:        cd ${BUILD_DIR} && ctest --output-on-failure"
echo -e "  Re-run specific test:    ${BUILD_DIR}/tests/meshml_tests --gtest_filter=TestName"
echo -e "  Clean and rebuild:       $0 --clean"
echo ""

exit 0
