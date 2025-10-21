#!/bin/bash
# Legal Events v2 Startup Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}     Legal Events Extraction v2 - Setup Script     ${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed!${NC}"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    # Try docker compose (newer version)
    if ! docker compose version &> /dev/null; then
        echo -e "${RED}❌ Docker Compose is not installed!${NC}"
        echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
        exit 1
    fi
    # Use docker compose instead of docker-compose
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Function to wait for a service to be healthy
wait_for_service() {
    local service=$1
    local max_attempts=30
    local attempt=0
    
    echo -n "Waiting for $service to be ready..."
    
    while [ $attempt -lt $max_attempts ]; do
        if $COMPOSE_CMD ps | grep -q "$service.*healthy"; then
            echo -e " ${GREEN}✓${NC}"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo -e " ${RED}✗${NC}"
    echo -e "${RED}$service failed to start!${NC}"
    return 1
}

# Parse command line arguments
COMMAND=${1:-"start"}

case $COMMAND in
    start)
        echo -e "${YELLOW}🚀 Starting Legal Events v2...${NC}"
        echo ""
        
        # Check if .env exists in repo root
        if [ ! -f "./.env" ]; then
            echo -e "${YELLOW}⚠️  No .env file found in repo root${NC}"
            echo "Creating template .env file..."
            cat > ./.env.template << EOF
# API Keys (add your keys here)
OPENROUTER_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here

# Flask Secret (generate a random one for production)
FLASK_SECRET_KEY=dev-secret-key-change-in-production

# JWT Secret (generate a random one for production)
JWT_SECRET_KEY=your-secret-key-change-in-production

# API Keys for basic auth (change these!)
API_KEY_ADMIN=admin-key-change-me
API_KEY_USER=user-key-change-me
EOF
            echo -e "${YELLOW}Please copy .env.template to .env and add your API keys${NC}"
            echo ""
        fi
        
        # Start services
        echo "Starting services with Docker Compose..."
        $COMPOSE_CMD up -d
        
        echo ""
        echo "Waiting for services to be healthy..."
        
        # Wait for each service
        wait_for_service "postgres"
        wait_for_service "redis"
        wait_for_service "minio"
        
        # Wait a bit more for API to fully initialize
        echo -n "Initializing API..."
        sleep 5
        echo -e " ${GREEN}✓${NC}"
        
        echo ""
        echo -e "${GREEN}✅ Legal Events v2 is running!${NC}"
        echo ""
        echo "🌐 Services:"
        echo "   • API:        http://localhost:8000"
        echo "   • API Docs:   http://localhost:8000/docs"
        echo "   • MinIO:      http://localhost:9001 (minioadmin/minioadmin123)"
        echo ""
        echo "📝 Quick Test:"
        echo "   curl http://localhost:8000/health"
        echo ""
        echo "🛑 To stop:  ./start.sh stop"
        echo "📊 To monitor: ./start.sh logs"
        ;;
        
    stop)
        echo -e "${YELLOW}🛑 Stopping Legal Events v2...${NC}"
        $COMPOSE_CMD down
        echo -e "${GREEN}✅ Services stopped${NC}"
        ;;
        
    restart)
        echo -e "${YELLOW}🔄 Restarting Legal Events v2...${NC}"
        $0 stop
        sleep 2
        $0 start
        ;;
        
    logs)
        echo -e "${YELLOW}📊 Showing logs (Ctrl+C to exit)...${NC}"
        $COMPOSE_CMD logs -f
        ;;
        
    status)
        echo -e "${YELLOW}📊 Service Status:${NC}"
        $COMPOSE_CMD ps
        ;;
        
    clean)
        echo -e "${RED}⚠️  This will delete all data!${NC}"
        read -p "Are you sure? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Stopping services..."
            $COMPOSE_CMD down -v
            echo -e "${GREEN}✅ All data cleaned${NC}"
        else
            echo "Cancelled"
        fi
        ;;
        
    shell-api)
        echo "Opening shell in API container..."
        docker exec -it legal_events_api /bin/bash
        ;;
        
    shell-worker)
        echo "Opening shell in worker container..."
        docker exec -it legal_events_worker /bin/bash
        ;;
        
    test)
        echo -e "${YELLOW}🧪 Running tests...${NC}"
        
        # Test health endpoint
        echo -n "Testing health endpoint..."
        if curl -s http://localhost:8000/health | grep -q "healthy"; then
            echo -e " ${GREEN}✓${NC}"
        else
            echo -e " ${RED}✗${NC}"
        fi
        
        # Test API docs
        echo -n "Testing API docs..."
        if curl -s http://localhost:8000/docs | grep -q "swagger"; then
            echo -e " ${GREEN}✓${NC}"
        else
            echo -e " ${RED}✗${NC}"
        fi
        
        echo -e "${GREEN}✅ Tests complete${NC}"
        ;;
        
    *)
        echo "Legal Events v2 Management Script"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  start      - Start all services"
        echo "  stop       - Stop all services"
        echo "  restart    - Restart all services"
        echo "  logs       - Show logs (follow mode)"
        echo "  status     - Show service status"
        echo "  clean      - Stop and remove all data"
        echo "  shell-api  - Open shell in API container"
        echo "  shell-worker - Open shell in worker container"
        echo "  test       - Run basic health tests"
        echo ""
        ;;
esac
