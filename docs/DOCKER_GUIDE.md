# Docker Deployment Guide for BizClone

BizClone requires **PostgreSQL**.

## Prerequisites

- Docker (v20.10+)
- Docker Compose (v2.0+)

## Quick Start

### 1. Build and Start Services

```bash
# Build Docker image and start all services (PostgreSQL + BizClone)
docker-compose up -d --build
```

### 2. Verify Services are Running

```bash
# Check service status
docker-compose ps

# View application logs
docker-compose logs -f bizclone

# View database logs
docker-compose logs -f postgres
```

### 3. Database Access

Connect to PostgreSQL database:

```bash
# Using docker-compose, postgres_db is the service name
docker-compose exec postgres_db psql -U bizclone_user -d bizclone_db


# Or from your machine (if PostgreSQL client installed)
psql -h localhost -p 5433 -U bizclone_user -d bizclone_db
```

Default credentials:
- **Username**: bizclone_user
- **Password**
- **Database**
- **Port**: `5433`

## Common Commands

### Stop Services

```bash
docker-compose down
```

### Stop and Remove Volumes (Clean Database)

```bash
docker-compose down -v
```

### View Logs

```bash
# Application logs
docker-compose logs -f bizclone

# Database logs
docker-compose logs -f postgres_db

# All logs
docker-compose logs -f
```

### Restart Services

```bash
docker-compose restart
```

### Rebuild Image (after code changes)

```bash
docker-compose up -d --build
```

### Execute Commands in Container

```bash
# Run Python script in app container
docker-compose exec bizclone python script.py

# Access app shell
docker-compose exec bizclone /bin/bash

# Access database
docker-compose exec postgres_db psql -U bizclone_user -d bizclone_db
```

## Environment Configuration

**For Docker (Automatic)**

Uses `.env` with:
- All services properly configured


## Data Persistence

- **PostgreSQL data**: Stored in Docker volume `postgres_data` (persistent across restarts)
- **Application data**: Stored in `./data` directory (mounted from host)
- **Logs**: Stored in `./logs` directory (mounted from host)

To clean all data:
```bash
docker-compose down -v
```

## Troubleshooting

### Database Connection Failed

```bash
# Check if PostgreSQL is running and healthy
docker-compose ps postgres_db

# View PostgreSQL logs
docker-compose logs postgres_db

# Test database connectivity
docker-compose exec postgres_db pg_isready -U bizclone_user -d bizclone_db
```

### Application Won't Start

```bash
# Check logs
docker-compose logs bizclone

# Rebuild image
docker-compose up -d --build

# Check if port 8000 is available
# If not, stop any running service on port 8000
```

### Permission Denied Errors

```bash
# For Linux users, you might need to use sudo
sudo docker-compose up -d --build

# Or add your user to docker group
sudo usermod -aG docker $USER
newgrp docker
```


## Example: Multi-Environment Setup

```bash
# Development (uses .env)
docker-compose -f docker-compose.yml up -d

# Staging (uses separate compose file)
docker-compose -f docker-compose.staging.yml up -d

# Production (uses separate compose file with production settings)
docker-compose -f docker-compose.prod.yml up -d
```

## Network Architecture

```
┌─────────────────────────────────────┐
│      Docker Network (bizclone)      │
├─────────────────────────────────────┤
│                                     │
│  ┌─────────────┐   ┌─────────────┐ │
│  │  BizClone   │   │ PostgreSQL  │ │
│  │  (Port 8000)├──┤ (Port 5433) │ │
│  └─────────────┘   └─────────────┘ │
│                                     │
│  Service: bizclone ↔ Service: postgres
│                                     │
└─────────────────────────────────────┘
        ↓
    Host Machine
    (Port 8000, 5433 exposed)
```

## Health Checks

Both services have health checks configured:

```bash
# Check application health
docker-compose exec bizclone curl http://localhost:8000/health

# Check database health
docker-compose exec postgres_db pg_isready -U bizclone_user -d bizclone_db
```

## Notes

- All containers restart automatically unless stopped
- Logs are preserved in `./logs` directory
- Database survives container restarts (persistent volume)
- To reset everything: `docker-compose down -v && docker-compose up -d --build`
