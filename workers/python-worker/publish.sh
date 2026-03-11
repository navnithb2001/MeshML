#!/bin/bash
#
# Publish MeshML Worker to PyPI
# Usage: ./publish.sh [testpypi|pypi]
#

set -e

TARGET="${1:-pypi}"
PACKAGE_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$PACKAGE_DIR"

echo "🚀 MeshML Worker Publishing Script"
echo "===================================="
echo ""

# Check if package is built
if [ ! -d "dist" ]; then
    echo "❌ Distribution files not found. Building package..."
    poetry build
else
    echo "✅ Distribution files found:"
    ls -lh dist/
fi

echo ""
echo "📦 Package Information:"
poetry version

echo ""
echo "🔍 Running pre-publish checks..."

# Run tests
echo "   - Running tests..."
if poetry run pytest --tb=no -q; then
    echo "   ✅ All tests passed"
else
    echo "   ❌ Tests failed! Aborting publish."
    exit 1
fi

echo ""

if [ "$TARGET" = "testpypi" ]; then
    echo "📤 Publishing to TestPyPI..."
    echo ""
    echo "⚠️  Make sure you have configured TestPyPI token:"
    echo "    poetry config repositories.testpypi https://test.pypi.org/legacy/"
    echo "    poetry config pypi-token.testpypi pypi-YOUR_TESTPYPI_TOKEN"
    echo ""
    read -p "Press Enter to continue or Ctrl+C to abort..."
    
    poetry publish -r testpypi
    
    echo ""
    echo "✅ Published to TestPyPI!"
    echo ""
    echo "Test installation with:"
    echo "  pip install --index-url https://test.pypi.org/simple/ meshml-worker"
    
elif [ "$TARGET" = "pypi" ]; then
    echo "📤 Publishing to PyPI (PRODUCTION)..."
    echo ""
    echo "⚠️  Make sure you have configured PyPI token:"
    echo "    poetry config pypi-token.pypi pypi-YOUR_PYPI_TOKEN"
    echo ""
    echo "⚠️  This will publish to PRODUCTION PyPI!"
    echo "    Version: $(poetry version -s)"
    echo "    This action cannot be undone."
    echo ""
    read -p "Are you sure you want to continue? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        echo "❌ Publish cancelled."
        exit 1
    fi
    
    poetry publish
    
    echo ""
    echo "🎉 Successfully published to PyPI!"
    echo ""
    echo "📦 Package: https://pypi.org/project/meshml-worker/"
    echo ""
    echo "Install with:"
    echo "  pip install meshml-worker"
    echo ""
    echo "Next steps:"
    echo "  1. Tag release: git tag v$(poetry version -s)"
    echo "  2. Push tag: git push origin v$(poetry version -s)"
    echo "  3. Create GitHub release"
    
else
    echo "❌ Invalid target: $TARGET"
    echo "Usage: $0 [testpypi|pypi]"
    exit 1
fi
