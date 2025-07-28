 #!/bin/bash
# launch.sh

# Function to cleanup background processes
cleanup() {
    echo "🛑 Shutting down services..."
    if [ ! -z "$MAIN_PID" ]; then
        kill $MAIN_PID 2>/dev/null
    fi
    if [ ! -z "$DASHBOARD_PID" ]; then
        kill $DASHBOARD_PID 2>/dev/null
    fi
    exit 0
}

# Setup signal handlers
trap cleanup SIGINT SIGTERM

echo "🚀 Starting MCP Governance Bridge..."

# Start main app in background
uv run app/main.py &
MAIN_PID=$!

# Wait a moment for main app to start
sleep 2

echo "🎨 Starting Dashboard..."

# Start dashboard in background
uv run streamlit run dashboard/streamlit_dashboard.py --server.port=8501 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false &
DASHBOARD_PID=$!

echo ""
echo "=================================================="
echo "🏛️  MCP Governance Bridge Running"
echo "=================================================="
echo "📊 Dashboard: http://localhost:8501"
echo "🔧 Main App: Running in background"
echo "❌ Press Ctrl+C to stop all services"
echo "=================================================="

# Wait for both processes
wait $MAIN_PID $DASHBOARD_PID