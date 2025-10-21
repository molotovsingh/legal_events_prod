#!/bin/bash
# Quick Start Script for Legal Events v2

set -e

echo "
╔══════════════════════════════════════════════════════════════╗
║          Legal Events Extraction v2 - Quick Start           ║
╚══════════════════════════════════════════════════════════════╝
"

# Check if we're in the v2 directory
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Error: Please run this script from the v2 directory"
    echo "   cd v2"
    echo "   ./quickstart.sh"
    exit 1
fi

# Step 1: Check for .env file
echo "📋 Step 1: Checking environment configuration..."
if [ ! -f "../.env" ]; then
    echo "⚠️  No .env file found. Creating template..."
    cat > ../.env << EOF
# Legal Events v2 Configuration
# Add at least ONE of these API keys:

# Recommended - OpenRouter (supports many models)
OPENROUTER_API_KEY=

# Alternative providers (optional)
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GEMINI_API_KEY=
DEEPSEEK_API_KEY=

# Security (change these for production!)
JWT_SECRET_KEY=dev-secret-key-$(date +%s)
API_KEY_ADMIN=admin-key-$(date +%s)
EOF
    
    echo ""
    echo "⚠️  IMPORTANT: You must add at least one API key!"
    echo ""
    echo "   1. Edit the file: ../.env"
    echo "   2. Add your API key(s)"
    echo "   3. Run this script again"
    echo ""
    echo "   Recommended: Get an OpenRouter key from https://openrouter.ai/"
    echo ""
    exit 1
else
    # Check if any API key is set
    if grep -q "API_KEY=." ../.env; then
        echo "✅ Environment file found with API keys"
    else
        echo "⚠️  Warning: No API keys detected in ../.env"
        echo "   The system may not work without at least one LLM API key!"
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Please add an API key to ../.env and try again"
            exit 1
        fi
    fi
fi

# Step 2: Check Docker
echo ""
echo "📋 Step 2: Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed!"
    echo ""
    echo "Please install Docker Desktop from:"
    echo "   https://www.docker.com/products/docker-desktop"
    echo ""
    exit 1
fi

if ! docker ps &> /dev/null; then
    echo "❌ Docker is not running!"
    echo ""
    echo "Please start Docker Desktop and try again"
    exit 1
fi

echo "✅ Docker is installed and running"

# Step 3: Start services
echo ""
echo "📋 Step 3: Starting services..."
echo ""

# Use the start script
chmod +x start.sh
./start.sh start

# Step 4: Wait for services
echo ""
echo "📋 Step 4: Waiting for services to be ready..."
echo "   This may take 1-2 minutes on first run..."
echo ""

# Simple wait
sleep 10

# Step 5: Run tests
echo ""
echo "📋 Step 5: Running system tests..."
echo ""

# Make test script executable
chmod +x test_system.py

# Check if Python is available
if command -v python3 &> /dev/null; then
    python3 test_system.py
elif command -v python &> /dev/null; then
    python test_system.py
else
    echo "⚠️  Python not found, skipping tests"
    echo "   You can test manually by visiting http://localhost:8000/health"
fi

# Step 6: Show access information
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    🎉 System is Ready!                      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "📌 Access Points:"
echo ""
echo "   Web Interface:  http://localhost:3000"
echo "   API Docs:       http://localhost:8000/docs"
echo "   MinIO Console:  http://localhost:9001"
echo "                   Username: minioadmin"
echo "                   Password: minioadmin123"
echo ""
echo "📚 Quick Start Guide:"
echo ""
echo "   1. Open the web interface: http://localhost:3000"
echo "   2. Click 'Create Client' and enter a name"
echo "   3. Click 'Create Case' using the client ID"
echo "   4. Select PDF files and click 'Process Documents'"
echo "   5. Watch the progress and download results!"
echo ""
echo "🛠️  Useful Commands:"
echo ""
echo "   View logs:      ./start.sh logs"
echo "   Stop system:    ./start.sh stop"
echo "   Restart:        ./start.sh restart"
echo "   Check status:   ./start.sh status"
echo ""
echo "📖 Documentation:"
echo ""
echo "   See README.md for detailed API examples"
echo "   See IMPLEMENTATION_SUMMARY.md for system overview"
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Your legal document processing system is ready! 🚀      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Open browser (optional, works on Mac/Linux)
if command -v open &> /dev/null; then
    echo "Opening web interface in browser..."
    open http://localhost:3000
elif command -v xdg-open &> /dev/null; then
    echo "Opening web interface in browser..."
    xdg-open http://localhost:3000
fi

echo "Press Ctrl+C to stop viewing logs..."
./start.sh logs
