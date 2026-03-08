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
