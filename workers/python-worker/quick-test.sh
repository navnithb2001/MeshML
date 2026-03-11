#!/bin/bash
#
# Quick Pre-Publication Test for MeshML Worker
#

WORKER_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$WORKER_DIR"

echo "🧪 MeshML Worker - Quick Pre-Publication Test"
echo "=============================================="
echo ""

# Test 1: Run all tests
echo "📋 Test 1: Running test suite..."
if poetry run pytest --tb=no -q; then
    echo "✅ All tests passed!"
else
    echo "❌ Tests failed! Fix before publishing."
    exit 1
fi

echo ""
echo "📋 Test 2: Building package..."
rm -rf dist/
if poetry build; then
    echo "✅ Package built successfully!"
else
    echo "❌ Build failed!"
    exit 1
fi

echo ""
echo "📋 Test 3: Checking built files..."
ls -lh dist/
if [ -f "dist/meshml_worker-0.1.0-py3-none-any.whl" ] && [ -f "dist/meshml_worker-0.1.0.tar.gz" ]; then
    echo "✅ Both wheel and source distribution created!"
else
    echo "❌ Missing distribution files!"
    exit 1
fi

echo ""
echo "📋 Test 4: Testing local installation..."
# Create temporary virtual environment
TEMP_VENV=$(mktemp -d)/test_venv
echo "Creating test environment..."

python3 -m venv "$TEMP_VENV"
source "$TEMP_VENV/bin/activate"

echo "Installing from wheel..."
pip install --quiet --no-cache-dir dist/meshml_worker-0.1.0-py3-none-any.whl

echo "Testing imports..."
python3 << 'EOF'
try:
    import meshml_worker
    print(f"✅ Import successful! Version: {meshml_worker.__version__}")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    exit(1)
EOF

echo "Testing CLI..."
if meshml-worker --help > /dev/null 2>&1; then
    echo "✅ CLI works!"
else
    echo "❌ CLI not accessible!"
    deactivate
    rm -rf "$TEMP_VENV"
    exit 1
fi

# Test all CLI commands
echo "Testing CLI commands..."
for cmd in login join start status config init; do
    if meshml-worker $cmd --help > /dev/null 2>&1; then
        echo "  ✅ meshml-worker $cmd"
    else
        echo "  ❌ meshml-worker $cmd not found!"
        deactivate
        rm -rf "$TEMP_VENV"
        exit 1
    fi
done

# Cleanup
deactivate
rm -rf "$TEMP_VENV"

echo ""
echo "=============================================="
echo "✅ ALL TESTS PASSED!"
echo "=============================================="
echo ""
echo "Your package is ready to publish! 🎉"
echo ""
echo "Next steps:"
echo ""
echo "1️⃣  Configure your PyPI token:"
echo "   poetry config pypi-token.pypi pypi-YOUR_TOKEN"
echo ""
echo "2️⃣  Test on TestPyPI first (RECOMMENDED):"
echo "   poetry config repositories.testpypi https://test.pypi.org/legacy/"
echo "   poetry config pypi-token.testpypi pypi-YOUR_TESTPYPI_TOKEN"
echo "   poetry publish -r testpypi"
echo ""
echo "   Then test install:"
echo "   pip install --index-url https://test.pypi.org/simple/ meshml-worker"
echo ""
echo "3️⃣  If TestPyPI works, publish to production:"
echo "   poetry publish"
echo ""
echo "4️⃣  Verify on PyPI:"
echo "   https://pypi.org/project/meshml-worker/"
echo ""
echo "5️⃣  Tag the release:"
echo "   git tag v0.1.0"
echo "   git push origin v0.1.0"
echo ""
