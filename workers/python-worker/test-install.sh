#!/bin/bash
# Test local installation of meshml-worker package

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "🧪 Testing MeshML Worker Package Installation"
echo ""

# Create a test virtual environment
echo "📦 Creating test virtual environment..."
python3 -m venv test_venv
source test_venv/bin/activate

echo ""
echo "📥 Installing package from local build..."
pip install dist/meshml_worker-*.whl

echo ""
echo "✅ Testing CLI commands..."

# Test CLI help
if meshml-worker --help > /dev/null 2>&1; then
    echo -e "${GREEN}✓ CLI installed correctly${NC}"
else
    echo -e "${RED}✗ CLI not working${NC}"
    deactivate
    rm -rf test_venv
    exit 1
fi

# Test Python import
echo ""
echo "🐍 Testing Python import..."
python3 << EOF
try:
    from meshml_worker import MeshMLWorker, WorkerConfig
    print("${GREEN}✓ Python imports working${NC}")
except ImportError as e:
    print("${RED}✗ Import failed: {e}${NC}")
    exit(1)
EOF

echo ""
echo "🔍 Testing package metadata..."
python3 << EOF
import meshml_worker
print(f"  Version: {meshml_worker.__version__}")
print(f"  Author: {meshml_worker.__author__}")
EOF

echo ""
echo -e "${GREEN}✓ All tests passed!${NC}"
echo ""
echo "📦 Package is ready for publication"

# Cleanup
deactivate
rm -rf test_venv

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Installation Test Complete"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
