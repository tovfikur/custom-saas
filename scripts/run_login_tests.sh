#!/bin/bash
set -e

echo "🐳 Docker Login Testing Workflow"
echo "================================="

# Function to check if a service is ready
check_service() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    echo "⏳ Waiting for $service_name to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f -s "$url" > /dev/null 2>&1; then
            echo "✅ $service_name is ready!"
            return 0
        fi
        
        echo "   Attempt $attempt/$max_attempts - $service_name not ready yet..."
        sleep 2
        ((attempt++))
    done
    
    echo "❌ $service_name failed to start within expected time"
    return 1
}

# Cleanup function
cleanup() {
    echo "🧹 Cleaning up test environment..."
    docker-compose --profile test down
}

# Set trap to cleanup on script exit
trap cleanup EXIT

echo "🚀 Step 1: Starting test services..."
docker-compose --profile test up -d test-postgres redis

echo "⏳ Waiting for test database to be ready..."
sleep 5

echo "🚀 Step 2: Setting up test database and users..."
cd "$(dirname "$0")/.."
python scripts/setup_test_users.py

if [ $? -ne 0 ]; then
    echo "❌ Failed to setup test database"
    exit 1
fi

echo "🚀 Step 3: Starting test backend service..."
docker-compose --profile test up -d test-backend

# Check if test backend is ready
if ! check_service "http://localhost:8001/docs" "Test Backend"; then
    echo "❌ Test backend failed to start"
    docker-compose --profile test logs test-backend
    exit 1
fi

echo "🚀 Step 4: Running login tests..."
python tests/test_login.py

if [ $? -eq 0 ]; then
    echo "🎉 All tests passed successfully!"
else
    echo "❌ Tests failed!"
    exit 1
fi

echo "✅ Testing workflow completed!"