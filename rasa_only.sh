#!/bin/bash

echo "🤖 Starting Rasa Services Only..."

# Load environment variables
source .env 2>/dev/null || echo "Warning: .env file not found"

# Activate virtual environment if not already activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    if [ -d "venv" ]; then
        source venv/bin/activate
        echo "✅ Virtual environment activated"
    else
        echo "❌ Virtual environment not found. Please create one first."
        exit 1
    fi
fi

# Train the model
echo "🎯 Training Rasa model..."
rasa train --quiet

# Kill any existing Rasa processes
echo "🧹 Cleaning up existing Rasa processes..."
pkill -f "rasa run actions" 2>/dev/null
pkill -f "rasa run" 2>/dev/null  

# Start action server in background
echo "⚡ Starting action server..."
rasa run actions --port 5055 > logs/actions.log 2>&1 &
ACTION_PID=$!

# Wait for action server to start
echo "⏳ Waiting for action server to start..."
sleep 5

# Start Rasa server in background
echo "🤖 Starting Rasa server..."
rasa run --enable-api --cors "*" --port 5005 --credentials credentials.yml > logs/rasa.log 2>&1 &
RASA_PID=$!

# Wait for Rasa server to start
echo "⏳ Waiting for Rasa server to start..."
sleep 8

echo ""
echo "🎉 Rasa Services Started!"
echo "=================================="
echo "🔧 Action Server: Port 5055"
echo "🤖 Rasa Server: Port 5005" 
echo "📋 Action Server Log: logs/actions.log"
echo "📋 Rasa Server Log: logs/rasa.log"
echo "=================================="
echo ""
echo "💡 Usage:"
echo "- Test Rasa API: curl http://localhost:5005/webhooks/rest/webhook -d '{\"message\":\"hello\"}'"
echo "- View logs: tail -f logs/rasa.log or tail -f logs/actions.log"
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Shutting down Rasa services..."
    kill $ACTION_PID 2>/dev/null
    kill $RASA_PID 2>/dev/null
    pkill -f "rasa run" 2>/dev/null
    echo "✅ All Rasa services stopped"
    exit 0
}

# Set trap for cleanup
trap cleanup SIGINT SIGTERM

# Monitor Rasa services
echo "📊 Monitoring Rasa services... (Press Ctrl+C to stop)"
echo "Action Server and Rasa Server are running..."

# Keep monitoring
while true; do
    sleep 5
    # Check if services are still running
    if ! ps -p $ACTION_PID > /dev/null 2>&1; then
        echo "❌ Action server stopped"
        break
    fi
    if ! ps -p $RASA_PID > /dev/null 2>&1; then
        echo "❌ Rasa server stopped"
        break
    fi
done
