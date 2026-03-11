#!/bin/bash
# MeshML Worker Package Build and Publish Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔨 Building MeshML Worker Package..."
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
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
poetry install
echo ""

# Run tests
echo "🧪 Running tests..."
if poetry run pytest; then
    echo -e "${GREEN}✓ All tests passed${NC}"
else
    echo -e "${RED}✗ Tests failed${NC}"
    echo "  Fix tests before publishing"
    exit 1
fi
echo ""

# Build package
echo "🏗️  Building package..."
poetry build
echo ""

# Show build artifacts
echo -e "${GREEN}✓ Package built successfully!${NC}"
echo ""
echo "📦 Build artifacts:"
ls -lh dist/
echo ""

# Publish instructions
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Next Steps"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "To publish to TestPyPI (for testing):"
echo -e "${YELLOW}  poetry publish -r testpypi${NC}"
echo ""
echo "To publish to PyPI (production):"
echo -e "${YELLOW}  poetry publish${NC}"
echo ""
echo "To test the package locally:"
echo -e "${YELLOW}  pip install dist/meshml_worker-*.whl${NC}"
echo ""
echo "To configure PyPI credentials:"
echo -e "${YELLOW}  poetry config pypi-token.pypi <your-token>${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
