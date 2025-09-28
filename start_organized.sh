#!/bin/bash

# Health Awareness Chatbot - Organized Startup Script
# Logs go to logs/ directory, YAML configs are in yaml_configs/

echo "🏥 Starting Health Awareness Chatbot (Organized Structure)"
echo "========================================================="

# Kill existing processes
echo "🧹 Cleaning up existing processes..."
pkill -f "rasa\|ngrok\|whatsapp_webhook" 2>/dev/null || true
sleep 2

# Ensure directories exist
mkdir -p logs
mkdir -p yaml_configs

# Navigate to project directory and activate venv
cd /home/akuro/pr
source venv/bin/activate

echo "🚀 Starting services with organized log structure..."

# Start Rasa action server with logs in logs/
nohup rasa run actions --port 5055 --debug > logs/actions.log 2>&1 &
echo "✅ Action server starting (logs/actions.log)"

# Wait for action server
sleep 5

# Start Rasa server with logs in logs/
nohup rasa run --enable-api --cors "*" --port 5005 --debug > logs/rasa.log 2>&1 &
echo "✅ Rasa server starting (logs/rasa.log)"

# Wait for Rasa server
sleep 5

# Start WhatsApp webhook with logs in logs/
nohup python whatsapp_webhook.py > logs/webhook.log 2>&1 &
echo "✅ Webhook server starting (logs/webhook.log)"

# Wait for webhook
sleep 3

# Start ngrok with logs in logs/
nohup ngrok http 5000 > logs/ngrok.log 2>&1 &
echo "✅ Ngrok tunnel starting (logs/ngrok.log)"

# Wait for ngrok
sleep 8

echo ""
echo "📊 SERVICE STATUS:"
echo "=================="
ps aux | grep -E "(rasa|ngrok|webhook)" | grep -v grep | awk '{print "✅ " $11 " " $12 " " $13}'

echo ""
echo "🌐 WEBHOOK URL:"
echo "==============="
WEBHOOK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*"' | head -1 | cut -d'"' -f4)
echo "📱 Twilio Webhook: ${WEBHOOK_URL}/whatsapp"

echo ""
echo "📂 ORGANIZED STRUCTURE:"
echo "======================"
echo "📋 Logs: ./logs/"
echo "📱 Webhook: ./whatsapp_webhook.py"

echo ""
echo "🎉 Health Bot Ready with Organized Structure!"
echo "============================================="
