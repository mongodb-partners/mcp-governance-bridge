#!/bin/bash
# run_tests.sh

echo "🧪 Running MCP Governance Bridge Test Suite"
echo "=============================================="

# Set test environment
export PYTHONPATH="$(pwd):$PYTHONPATH"
export MONGODB_URI="mongodb://localhost:27017/mcp_governance_test"
export TESTING=true

# Install test dependencies if not already installed
pip install pytest pytest-asyncio pytest-mock pytest-cov

# Run tests with coverage
echo "📊 Running tests with coverage..."
pytest tests/ \
    --verbose \
    --asyncio-mode=auto \
    --cov=app \
    --cov=core \
    --cov=database \
    --cov=utils \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    --junit-xml=test-results.xml

echo ""
echo "✅ Test results:"
echo "   - Coverage report: htmlcov/index.html"
echo "   - JUnit XML: test-results.xml"
echo ""
echo "🚀 Test run complete!"