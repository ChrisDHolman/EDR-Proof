#!/bin/bash

# EDR-PROOF Hybrid System Shutdown Script

echo "======================================"
echo "  Stopping EDR-PROOF Services"
echo "======================================"
echo ""

# Function to stop a service
stop_service() {
    local name=$1
    local pid_file="logs/${name}.pid"

    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        echo "Stopping $name (PID: $pid)..."
        kill $pid 2>/dev/null || echo "  ⚠️  Process not found"
        rm "$pid_file"
    else
        echo "No PID file for $name"
    fi
}

# Stop all services
stop_service "fastapi"
stop_service "celery-phase1"
stop_service "celery-phase2"
stop_service "celery-phase3"
stop_service "flower"

# Also kill any remaining celery workers
echo ""
echo "Cleaning up any remaining Celery workers..."
pkill -f "celery.*worker" 2>/dev/null || echo "  No Celery workers found"

echo ""
echo "✅ All services stopped"
echo ""
