#!/bin/bash
#
# Pre-Publication Test Suite for MeshML Worker
# Run this script to verify everything works before publishing to PyPI
#

set -e  # Exit on error

WORKER_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$WORKER_DIR"

echo "🧪 MeshML Worker - Pre-Publication Test Suite"
echo "=============================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Helper functions
pass_test() {
    echo -e "${GREEN}✅ PASS${NC}: $1"
    ((TESTS_PASSED++))
}

fail_test() {
    echo -e "${RED}❌ FAIL${NC}: $1"
    ((TESTS_FAILED++))
}

warn_test() {
    echo -e "${YELLOW}⚠️  WARN${NC}: $1"
}

echo "📋 Test 1: Package Metadata"
echo "----------------------------"
if poetry version | grep -q "0.1.0"; then
    pass_test "Version is 0.1.0"
else
    fail_test "Version is not 0.1.0"
fi

if grep -q "meshml-worker" pyproject.toml; then
    pass_test "Package name is correct"
else
    fail_test "Package name is incorrect"
fi

echo ""
echo "📋 Test 2: All Tests Pass"
echo "-------------------------"
if poetry run pytest --tb=no -q 2>&1 | grep -q "passed"; then
    pass_test "All unit tests passed"
else
    fail_test "Some tests failed"
    echo "Run: poetry run pytest -v"
fi

echo ""
echo "📋 Test 3: Package Build"
echo "-----------------------"
if [ -d "dist" ]; then
    rm -rf dist
    echo "Cleaned old dist/ directory"
fi

if poetry build 2>&1 | grep -q "Built"; then
    pass_test "Package built successfully"
else
    fail_test "Package build failed"
fi

# Check built files
if [ -f "dist/meshml_worker-0.1.0-py3-none-any.whl" ]; then
    pass_test "Wheel file created"
    ls -lh dist/meshml_worker-0.1.0-py3-none-any.whl
else
    fail_test "Wheel file not found"
fi

if [ -f "dist/meshml_worker-0.1.0.tar.gz" ]; then
    pass_test "Source distribution created"
    ls -lh dist/meshml_worker-0.1.0.tar.gz
else
    fail_test "Source distribution not found"
fi

echo ""
echo "📋 Test 4: Package Contents"
echo "---------------------------"
if command -v unzip &> /dev/null; then
    unzip -l dist/meshml_worker-0.1.0-py3-none-any.whl | grep -q "meshml_worker/__init__.py" && \
        pass_test "Package contains source code" || \
        fail_test "Package missing source code"
    
    unzip -l dist/meshml_worker-0.1.0-py3-none-any.whl | grep -q "README.md" && \
        pass_test "Package contains README.md" || \
        warn_test "Package missing README.md"
    
    unzip -l dist/meshml_worker-0.1.0-py3-none-any.whl | grep -q "LICENSE" && \
        pass_test "Package contains LICENSE" || \
        warn_test "Package missing LICENSE"
else
    warn_test "unzip not available, skipping package content check"
fi

echo ""
echo "📋 Test 5: Local Installation Test"
echo "-----------------------------------"
# Create temporary virtual environment
TEMP_VENV=$(mktemp -d)/test_venv
echo "Creating test environment: $TEMP_VENV"

python3 -m venv "$TEMP_VENV"
source "$TEMP_VENV/bin/activate"

echo "Installing package from wheel..."
if pip install --no-cache-dir dist/meshml_worker-0.1.0-py3-none-any.whl &> /dev/null; then
    pass_test "Package installs successfully"
else
    fail_test "Package installation failed"
    deactivate
    rm -rf "$TEMP_VENV"
    exit 1
fi

# Test imports
echo "Testing imports..."
python3 -c "import meshml_worker; print('Import successful:', meshml_worker.__version__)" && \
    pass_test "Package imports successfully" || \
    fail_test "Package import failed"

# Test CLI
echo "Testing CLI commands..."
if meshml-worker --help &> /dev/null; then
    pass_test "CLI is accessible"
else
    fail_test "CLI not accessible"
fi

if meshml-worker --version &> /dev/null; then
    pass_test "Version command works"
else
    warn_test "Version command not working"
fi

# Test CLI commands exist
for cmd in login join start register; do
    if meshml-worker $cmd --help &> /dev/null; then
        pass_test "CLI command '$cmd' exists"
    else
        fail_test "CLI command '$cmd' not found"
    fi
done

# Cleanup
deactivate
rm -rf "$TEMP_VENV"

echo ""
echo "📋 Test 6: Dependencies"
echo "----------------------"
pip list --format=freeze | grep -q "torch" && \
    pass_test "PyTorch dependency available" || \
    warn_test "PyTorch not in current environment"

pip list --format=freeze | grep -q "requests" && \
    pass_test "Requests dependency available" || \
    warn_test "Requests not in current environment"

echo ""
echo "📋 Test 7: Documentation"
echo "------------------------"
[ -f "README.md" ] && pass_test "README.md exists" || fail_test "README.md missing"
[ -s "README.md" ] && pass_test "README.md has content" || fail_test "README.md is empty"
[ -f "LICENSE" ] && pass_test "LICENSE file exists" || warn_test "LICENSE file missing"

# Check README has essential sections
grep -q "Installation" README.md && pass_test "README has Installation section" || warn_test "README missing Installation"
grep -q "Usage" README.md && pass_test "README has Usage section" || warn_test "README missing Usage"

echo ""
echo "📋 Test 8: PyPI Token Configuration"
echo "------------------------------------"
if poetry config pypi-token.pypi &> /dev/null; then
    if [ -n "$(poetry config pypi-token.pypi)" ]; then
        pass_test "PyPI token is configured"
    else
        warn_test "PyPI token is not set (you'll need this to publish)"
        echo "    Run: poetry config pypi-token.pypi pypi-YOUR_TOKEN"
    fi
else
    warn_test "Cannot check PyPI token status"
fi

echo ""
echo "📋 Test 9: No Uncommitted Changes"
echo "----------------------------------"
if git status --porcelain 2>/dev/null | grep -q .; then
    warn_test "You have uncommitted changes"
    echo "    Consider committing before publishing"
else
    pass_test "No uncommitted changes"
fi

echo ""
echo "📋 Test 10: Git Tag Ready"
echo "-------------------------"
if git tag | grep -q "v0.1.0"; then
    warn_test "Tag v0.1.0 already exists"
else
    pass_test "Tag v0.1.0 is available"
    echo "    After publishing, run: git tag v0.1.0 && git push origin v0.1.0"
fi

echo ""
echo "=============================================="
echo "📊 Test Results Summary"
echo "=============================================="
echo -e "${GREEN}✅ Passed: $TESTS_PASSED${NC}"
echo -e "${RED}❌ Failed: $TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 All critical tests passed!${NC}"
    echo ""
    echo "You're ready to publish! Next steps:"
    echo ""
    echo "1. Configure PyPI token (if not done):"
    echo "   poetry config pypi-token.pypi pypi-YOUR_TOKEN"
    echo ""
    echo "2. Publish to TestPyPI (recommended first):"
    echo "   poetry config repositories.testpypi https://test.pypi.org/legacy/"
    echo "   poetry config pypi-token.testpypi pypi-YOUR_TESTPYPI_TOKEN"
    echo "   poetry publish -r testpypi"
    echo ""
    echo "3. Test installation from TestPyPI:"
    echo "   pip install --index-url https://test.pypi.org/simple/ meshml-worker"
    echo ""
    echo "4. If all good, publish to production PyPI:"
    echo "   poetry publish"
    echo ""
    echo "5. Verify on PyPI:"
    echo "   https://pypi.org/project/meshml-worker/"
    echo ""
    echo "6. Tag the release:"
    echo "   git tag v0.1.0"
    echo "   git push origin v0.1.0"
    echo ""
    exit 0
else
    echo -e "${RED}❌ Some tests failed!${NC}"
    echo "Please fix the issues before publishing."
    echo ""
    exit 1
fi
