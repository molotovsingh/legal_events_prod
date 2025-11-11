#!/bin/bash

# Start Local Development Environment
# This script starts the API and frontend servers for local development

set -e

echo "🚀 Starting Legal Events Production - Local Development"
echo "========================================================"

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
    echo "✅ Loaded .env file"
else
    echo "❌ No .env file found!"
    exit 1
fi

# Check if PostgreSQL is running
if ! pgrep -x "postgres" > /dev/null; then
    echo "❌ PostgreSQL is not running!"
    echo "Start it with: brew services start postgresql@15"
    exit 1
fi
echo "✅ PostgreSQL is running"

# Check if database exists
if ! psql -U legal_user -d legal_events -c "SELECT 1" > /dev/null 2>&1; then
    echo "⚠️  Database 'legal_events' not accessible"
    echo "Run the setup commands first (see README)"
    exit 1
fi
echo "✅ Database is accessible"

# Start API server
echo ""
echo "Starting API server on http://localhost:8000..."
cd "$(dirname "$0")"
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload > /tmp/api_server.log 2>&1 &
API_PID=$!
echo "✅ API server started (PID: $API_PID)"

# Wait for API to be ready
echo "Waiting for API to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ API is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ API failed to start. Check logs: tail -f /tmp/api_server.log"
        kill $API_PID 2>/dev/null || true
        exit 1
    fi
    sleep 1
done

# Start frontend server
echo ""
echo "Starting frontend server on http://localhost:3000..."
python3 -m http.server 3000 --directory frontend > /tmp/frontend_server.log 2>&1 &
FRONTEND_PID=$!
echo "✅ Frontend server started (PID: $FRONTEND_PID)"

# Display access information
echo ""
echo "========================================================"
echo "✅ All services started successfully!"
echo "========================================================"
echo ""
echo "📋 Access URLs:"
echo "   Frontend:  http://localhost:3000/index.html"
echo "   API:       http://localhost:8000"
echo "   API Docs:  http://localhost:8000/docs"
echo ""
echo "🔐 Default Login:"
echo "   Email:     dev@localhost"
echo "   Password:  devpass123"
echo ""
echo "📝 Logs:"
echo "   API:       tail -f /tmp/api_server.log"
echo "   Frontend:  tail -f /tmp/frontend_server.log"
echo ""
echo "🛑 To stop servers:"
echo "   kill $API_PID $FRONTEND_PID"
echo ""
echo "Press Ctrl+C to stop all services"
echo "========================================================"

# Save PIDs to file for easy cleanup
echo "$API_PID" > /tmp/legal_events_api.pid
echo "$FRONTEND_PID" > /tmp/legal_events_frontend.pid

# Wait for Ctrl+C
trap 'echo ""; echo "🛑 Stopping services..."; kill $API_PID $FRONTEND_PID 2>/dev/null; rm -f /tmp/legal_events_*.pid; echo "✅ Stopped"; exit 0' INT TERM

# Keep script running
wait
