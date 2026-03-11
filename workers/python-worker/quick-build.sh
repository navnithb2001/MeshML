#!/bin/bash
# Quick build script without running tests
# Use for authentication changes testing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔨 Building MeshML Worker Package (skipping tests)..."
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if poetry is installed
if ! command -v poetry &> /dev/null; then
    echo -e "${RED}✗ Poetry is not installed${NC}"
    echo "  Install it with: curl -sSL https://install.python-poetry.org | python3 -"
    exit 1
fi

echo -e "${GREEN}✓ Poetry found${NC}"
echo ""

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf dist/ build/ *.egg-info
echo -e "${GREEN}✓ Clean complete${NC}"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
poetry install --no-interaction
echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# Build package
echo "🏗️  Building package..."
poetry build
echo -e "${GREEN}✓ Build complete${NC}"
echo ""

# Show what was built
echo "📦 Build artifacts:"
ls -lh dist/
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Build successful!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "📦 Package files created in dist/:"
for file in dist/*; do
    echo "  - $(basename $file) ($(du -h $file | cut -f1))"
done
echo ""
echo -e "${YELLOW}⚠️  Tests were skipped${NC}"
echo "   Run './build-package.sh' for full build with tests"
echo ""
echo "Next steps:"
echo "  1. Test install: ./test-install.sh"
echo "  2. Publish to TestPyPI: poetry publish -r testpypi"
echo "  3. Publish to PyPI: poetry publish"
