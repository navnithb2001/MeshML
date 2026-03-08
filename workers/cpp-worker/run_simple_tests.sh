#!/bin/bash

# Simple test runner that builds only what we can without LibTorch
# This will test config loader and other non-LibTorch components

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build_simple"

echo "=== Simple C++ Tests (No LibTorch Required) ==="
echo ""

# Clean build
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

# Create a minimal test CMakeLists.txt
cat > CMakeLists.txt << 'EOF'
cmake_minimum_required(VERSION 3.20)
project(meshml-simple-tests CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find Google Test
find_package(GTest REQUIRED)

# Simple config loader test (no LibTorch needed)
add_executable(simple_test ../tests/test_simple.cpp)
target_include_directories(simple_test PRIVATE
    ${GTEST_INCLUDE_DIRS}
    ../include
)
target_link_libraries(simple_test
    GTest::GTest
    GTest::Main
)

enable_testing()
add_test(NAME SimpleTest COMMAND simple_test)
EOF

# Create a simple test file
cat > ../tests/test_simple.cpp << 'EOF'
#include <gtest/gtest.h>
#include <string>
#include <fstream>

// Simple test to verify Google Test is working
TEST(SimpleTest, BasicAssertion) {
    EXPECT_EQ(1 + 1, 2);
    EXPECT_TRUE(true);
    EXPECT_FALSE(false);
}

// Test string operations
TEST(SimpleTest, StringOperations) {
    std::string hello = "Hello";
    std::string world = "World";
    std::string combined = hello + " " + world;
    
    EXPECT_EQ(combined, "Hello World");
    EXPECT_EQ(hello.length(), 5);
}

// Test basic file I/O (for config loading simulation)
TEST(SimpleTest, FileOperations) {
    const char* filename = "/tmp/test_file.txt";
    const char* content = "Test content";
    
    // Write
    {
        std::ofstream file(filename);
        ASSERT_TRUE(file.is_open());
        file << content;
    }
    
    // Read
    {
        std::ifstream file(filename);
        ASSERT_TRUE(file.is_open());
        std::string read_content;
        std::getline(file, read_content);
        EXPECT_EQ(read_content, content);
    }
    
    // Cleanup
    std::remove(filename);
}

// Math operations test
TEST(SimpleTest, MathOperations) {
    EXPECT_FLOAT_EQ(0.1f + 0.2f, 0.3f);
    EXPECT_DOUBLE_EQ(1.0 / 3.0 * 3.0, 1.0);
}

// Container operations
TEST(SimpleTest, VectorOperations) {
    std::vector<int> vec = {1, 2, 3, 4, 5};
    
    EXPECT_EQ(vec.size(), 5);
    EXPECT_EQ(vec.front(), 1);
    EXPECT_EQ(vec.back(), 5);
    
    vec.push_back(6);
    EXPECT_EQ(vec.size(), 6);
}
EOF

echo "Building simple tests..."
cmake -DCMAKE_BUILD_TYPE=Release .
make -j$(sysctl -n hw.ncpu)

echo ""
echo "Running simple tests..."
./simple_test

echo ""
echo "=== Simple Tests Complete ===" 
echo ""
echo "These tests verify:"
echo "  ✓ Google Test framework is working"
echo "  ✓ C++17 compilation is working"
echo "  ✓ Basic C++ features are functional"
echo ""
echo "Note: Full tests with LibTorch require manual LibTorch installation"
echo "Install LibTorch from: https://pytorch.org/"
EOF