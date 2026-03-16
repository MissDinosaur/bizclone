#!/bin/bash
# BizClone Docker Startup Script
# This script handles building and starting the BizClone application with PostgreSQL

set -e

echo "================================"
echo "BizClone Docker Setup"
echo "================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    echo "Please install Docker from: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    echo "Please install Docker Compose from: https://docs.docker.com/compose/install/"
    exit 1
fi

echo -e "${GREEN}✓ Docker and Docker Compose found${NC}"
echo ""

# Create necessary directories
mkdir -p data logs config/gmail

echo "Creating directories..."
echo -e "${GREEN}✓ directories ready${NC}"
echo ""

# Build and start services
echo "Building and starting services..."
docker-compose up -d --build

echo ""
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}================================${NC}"
echo ""

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 10

# Check service status
echo ""
echo "Service Status:"
docker-compose ps

echo ""
echo -e "${YELLOW}Database Credentials:${NC}"
echo "  Username: bizclone_user"
echo "  Host: postgres (from container)"
echo "  Host: localhost (from host machine)"
echo "  Port: 5432"
echo ""

echo -e "${YELLOW}Application URLs:${NC}"
echo "  API Docs: http://localhost:8000/docs"
echo "  Alternative: http://localhost:8000/redoc"
echo ""

echo -e "${YELLOW}Useful Commands:${NC}"
echo "  View logs:        docker-compose logs -f"
echo "  Stop services:    docker-compose down"
echo "  Restart services: docker-compose restart"
echo "  Access database:  docker-compose exec postgres psql -U bizclone_user -d bizclone_db"
echo "  Access bash:      docker-compose exec bizclone /bin/bash"
echo ""

# Show application logs
echo -e "${YELLOW}Showing application logs (press Ctrl+C to exit):${NC}"
echo ""
docker-compose logs -f bizclone
