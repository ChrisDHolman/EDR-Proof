#!/bin/bash

# EDR-PROOF Hybrid System Startup Script
# This script starts all components for local development

set -e

echo "======================================"
echo "  EDR-PROOF Hybrid System Startup"
echo "======================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "Creating from template..."
    cp .env.example .env
    echo "✅ Created .env - Please edit with your credentials"
    echo "   Then run this script again."
    exit 1
fi

# Check if Redis is running
echo "Checking Redis..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis not running!"
    echo ""
    echo "Start Redis with one of these commands:"
    echo "  Docker:  docker run -d -p 6379:6379 redis:7-alpine"
    echo "  Linux:   sudo systemctl start redis"
    echo "  macOS:   brew services start redis"
    exit 1
fi
echo "✅ Redis is running"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo ""
    echo "Creating Python virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi

# Activate venv
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -q -r requirements.txt
echo "✅ Dependencies installed"

# Create log directory
mkdir -p logs

# Function to start a service in background
start_service() {
    local name=$1
    local command=$2
    local log_file="logs/${name}.log"

    echo "Starting $name..."
    nohup $command > "$log_file" 2>&1 &
    echo $! > "logs/${name}.pid"
    echo "✅ $name started (PID: $(cat logs/${name}.pid), log: $log_file)"
}

echo ""
echo "Starting services..."
echo "===================="

# Start FastAPI
start_service "fastapi" "python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload"

sleep 2

# Start Celery workers
start_service "celery-phase1" "celery -A tasks.celery_app worker --queues=phase1 --concurrency=10 --loglevel=info --hostname=phase1@%h"

sleep 2

start_service "celery-phase2" "celery -A tasks.celery_app worker --queues=phase2 --concurrency=10 --loglevel=info --hostname=phase2@%h"

sleep 2

start_service "celery-phase3" "celery -A tasks.celery_app worker --queues=phase3 --concurrency=5 --loglevel=info --hostname=phase3@%h"

sleep 2

# Start Flower (optional)
start_service "flower" "celery -A tasks.celery_app flower --port=5555"

echo ""
echo "======================================"
echo "  All services started successfully!"
echo "======================================"
echo ""
echo "Access points:"
echo "  📊 Dashboard: http://localhost:8000"
echo "  🌸 Flower:    http://localhost:5555"
echo ""
echo "View logs:"
echo "  tail -f logs/fastapi.log"
echo "  tail -f logs/celery-phase1.log"
echo "  tail -f logs/celery-phase2.log"
echo "  tail -f logs/celery-phase3.log"
echo ""
echo "Stop all services:"
echo "  ./stop.sh"
echo ""
