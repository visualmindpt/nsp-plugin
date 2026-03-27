#!/bin/bash
# NSP Plugin - Deployment Script
# Deploy application to production using Docker

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="nsp-plugin"
DOCKER_COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}NSP Plugin - Deployment Script${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not installed. Please install Docker first.${NC}"
    exit 1
fi

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not installed. Please install Docker Compose first.${NC}"
    exit 1
fi

# Function to check if models exist
check_models() {
    echo -e "${YELLOW}Checking for trained models...${NC}"
    if [ ! -f "models/best_preset_classifier.pth" ] || [ ! -f "models/best_refinement_model.pth" ]; then
        echo -e "${RED}❌ Trained models not found in models/ directory${NC}"
        echo -e "${YELLOW}Please train models first:${NC}"
        echo -e "  python train/train_models_v2.py"
        exit 1
    fi
    echo -e "${GREEN}✓ Models found${NC}"
}

# Function to create .env file if doesn't exist
create_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        echo -e "${YELLOW}Creating default .env file...${NC}"
        cat > "$ENV_FILE" <<EOF
# NSP Plugin Environment Variables
LOG_LEVEL=INFO
MAX_WORKERS=4
ENABLE_MONITORING=true
ENABLE_CACHE=true
SERVER_PORT=5001
EOF
        echo -e "${GREEN}✓ .env file created${NC}"
    fi
}

# Function to build Docker image
build_image() {
    echo -e "${YELLOW}Building Docker image...${NC}"
    docker build -t ${PROJECT_NAME}:latest . || {
        echo -e "${RED}❌ Docker build failed${NC}"
        exit 1
    }
    echo -e "${GREEN}✓ Docker image built successfully${NC}"
}

# Function to start services
start_services() {
    local PROFILE=$1
    echo -e "${YELLOW}Starting services...${NC}"

    if [ -n "$PROFILE" ]; then
        docker-compose --profile $PROFILE up -d || docker compose --profile $PROFILE up -d
    else
        docker-compose up -d || docker compose up -d
    fi

    echo -e "${GREEN}✓ Services started${NC}"
}

# Function to check health
check_health() {
    echo -e "${YELLOW}Waiting for services to be healthy...${NC}"
    local MAX_ATTEMPTS=30
    local ATTEMPT=0

    while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
        if curl -f http://localhost:5001/health &> /dev/null; then
            echo -e "${GREEN}✓ API is healthy${NC}"
            return 0
        fi
        ATTEMPT=$((ATTEMPT + 1))
        echo -n "."
        sleep 2
    done

    echo -e "${RED}❌ API health check failed${NC}"
    return 1
}

# Function to show logs
show_logs() {
    echo -e "${YELLOW}Recent logs:${NC}"
    docker-compose logs --tail=50 api || docker compose logs --tail=50 api
}

# Main deployment flow
main() {
    local MODE=${1:-"basic"}  # basic, monitoring, or cache

    echo ""
    echo -e "${YELLOW}Deployment mode: ${MODE}${NC}"
    echo ""

    # Pre-deployment checks
    check_models
    create_env_file

    # Build and deploy
    build_image

    case $MODE in
        monitoring)
            start_services "monitoring"
            ;;
        cache)
            start_services "cache"
            ;;
        full)
            # Start all profiles
            docker-compose --profile monitoring --profile cache up -d || docker compose --profile monitoring --profile cache up -d
            ;;
        *)
            start_services ""
            ;;
    esac

    # Post-deployment checks
    check_health

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✓ Deployment completed successfully!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "API Server: ${GREEN}http://localhost:5001${NC}"
    echo -e "Health Check: ${GREEN}http://localhost:5001/health${NC}"

    if [ "$MODE" = "monitoring" ] || [ "$MODE" = "full" ]; then
        echo -e "Prometheus: ${GREEN}http://localhost:9090${NC}"
        echo -e "Grafana: ${GREEN}http://localhost:3000${NC} (admin/admin)"
    fi

    echo ""
    echo -e "${YELLOW}Useful commands:${NC}"
    echo -e "  View logs:    docker-compose logs -f api"
    echo -e "  Stop services: docker-compose down"
    echo -e "  Restart API:  docker-compose restart api"
    echo ""
}

# Parse arguments
case ${1:-""} in
    -h|--help)
        echo "Usage: $0 [MODE]"
        echo ""
        echo "Modes:"
        echo "  basic      - Start only API server (default)"
        echo "  monitoring - Start API + Prometheus + Grafana"
        echo "  cache      - Start API + Redis cache"
        echo "  full       - Start all services"
        echo ""
        echo "Examples:"
        echo "  $0              # Basic deployment"
        echo "  $0 monitoring   # With monitoring"
        echo "  $0 full         # Full stack"
        exit 0
        ;;
    *)
        main ${1:-"basic"}
        ;;
esac
