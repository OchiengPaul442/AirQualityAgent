# Docker Deployment Guide for Aeris

This guide explains how to deploy **Aeris**, your Air Quality AI Assistant, using Docker.

## Meet Aeris

**Aeris** is your friendly, knowledgeable Air Quality AI Assistant dedicated to helping you understand air quality data, environmental health, and pollution monitoring. Simply address Aeris by name in your conversations!

## Prerequisites

- Docker Engine 20.10 or higher
- Docker Compose 2.0 or higher
- At least 2GB of free RAM
- At least 5GB of free disk space

## Quick Start

### 1. Create Environment File

Create a `.env` file in the project root:

```env
# AI Provider (choose one)
AI_PROVIDER=gemini
AI_MODEL=gemini-2.5-flash
AI_API_KEY=your_api_key_here

# Data Sources (optional but recommended)
WAQI_API_KEY=your_waqi_key
AIRQO_API_TOKEN=your_airqo_token

# Redis
REDIS_ENABLED=true
REDIS_PASSWORD=secure_redis_password

# Cache
CACHE_TTL_SECONDS=3600
```

### 2. Build and Start

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Check service status
docker-compose ps
```

### 3. Access the API

The API will be available at:

- **API:** http://localhost:8000
- **Health Check:** http://localhost:8000/health
- **API Docs:** http://localhost:8000/api/v1/docs

### 4. Stop Services

```bash
# Stop services
docker-compose down

# Stop and remove volumes (data will be lost)
docker-compose down -v
```

## Configuration Options

### Using Different AI Providers

**Google Gemini:**

```env
AI_PROVIDER=gemini
AI_MODEL=gemini-2.5-flash
AI_API_KEY=your_gemini_key
```

**OpenAI:**

```env
AI_PROVIDER=openai
AI_MODEL=gpt-4o
AI_API_KEY=your_openai_key
OPENAI_BASE_URL=https://api.openai.com/v1
```

**Ollama (Local):**

```bash
# Start with Ollama service
docker-compose --profile ollama up -d

# Pull a model
docker exec -it airquality-ollama ollama pull llama3.2

# Configure in .env
AI_PROVIDER=ollama
AI_MODEL=llama3.2
OLLAMA_BASE_URL=http://ollama:11434
```

### Scaling Workers

Modify the `docker-compose.yml` command:

```yaml
command:
  [
    "uvicorn",
    "src.api.main:app",
    "--host",
    "0.0.0.0",
    "--port",
    "8000",
    "--workers",
    "4",
  ]
```

### Using PostgreSQL Instead of SQLite

Add PostgreSQL service to `docker-compose.yml`:

```yaml
postgres:
  image: postgres:15-alpine
  environment:
    POSTGRES_DB: airquality_db
    POSTGRES_USER: airquality
    POSTGRES_PASSWORD: secure_password
  volumes:
    - postgres-data:/var/lib/postgresql/data
  networks:
    - airquality-network
```

Update `.env`:

```env
DATABASE_URL=postgresql://airquality:secure_password@postgres:5432/airquality_db
```

## Production Deployment

### 1. Use Multi-Stage Build

The provided Dockerfile already uses multi-stage builds for optimization.

### 2. Enable Redis Password

Always set a strong Redis password in production:

```env
REDIS_PASSWORD=very_secure_random_password_here
```

### 3. Set Resource Limits

Update `docker-compose.yml`:

```yaml
services:
  airquality-agent:
    deploy:
      resources:
        limits:
          cpus: "2"
          memory: 4G
        reservations:
          cpus: "1"
          memory: 2G
```

### 4. Use Nginx Reverse Proxy

Create `nginx.conf`:

```nginx
upstream airquality {
    server airquality-agent:8000;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://airquality;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Add to `docker-compose.yml`:

```yaml
nginx:
  image: nginx:alpine
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./nginx.conf:/etc/nginx/conf.d/default.conf
    - ./ssl:/etc/nginx/ssl
  depends_on:
    - airquality-agent
  networks:
    - airquality-network
```

### 5. Enable SSL/TLS

Use Certbot for Let's Encrypt certificates:

```bash
docker run -it --rm --name certbot \
  -v "/etc/letsencrypt:/etc/letsencrypt" \
  -v "/var/lib/letsencrypt:/var/lib/letsencrypt" \
  certbot/certbot certonly --standalone \
  -d your-domain.com
```

## Monitoring and Maintenance

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f airquality-agent

# Last 100 lines
docker-compose logs --tail=100 airquality-agent
```

### Check Resource Usage

```bash
docker stats
```

### Update Application

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose up -d --build

# Check logs
docker-compose logs -f
```

### Backup Data

```bash
# Backup SQLite database
docker cp airquality-agent:/app/chat_sessions.db ./backup/

# Backup Redis data
docker exec airquality-redis redis-cli --rdb /data/dump.rdb SAVE
docker cp airquality-redis:/data/dump.rdb ./backup/
```

### Restore Data

```bash
# Restore SQLite
docker cp ./backup/chat_sessions.db airquality-agent:/app/

# Restore Redis
docker cp ./backup/dump.rdb airquality-redis:/data/
docker-compose restart redis
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs airquality-agent

# Check if port is in use
netstat -ano | findstr :8000  # Windows
lsof -i :8000                  # Linux/Mac
```

### High Memory Usage

- Reduce number of workers
- Implement memory limits in docker-compose.yml
- Check for memory leaks in logs

### Redis Connection Issues

```bash
# Test Redis connection
docker exec -it airquality-redis redis-cli ping

# Check Redis logs
docker-compose logs redis
```

### AI Provider API Errors

- Verify API key is correct
- Check internet connectivity from container
- Review rate limits with your provider

### Database Connection Issues

When running the application in Docker, you may encounter connection errors when trying to connect to a database running on your host machine (localhost).

**Error Example:**

```
(psycopg2.OperationalError) connection to server at "localhost" (::1), port 5432 failed: Connection refused
```

**Root Cause:** In Docker, `localhost` refers to the container itself, not your host machine. The container cannot reach host services using `localhost`.

**Solutions:**

#### Option 1: Connect to Host Database (Recommended)

Use `host.docker.internal` instead of `localhost` to access services on your host machine:

```bash
# Override DATABASE_URL when running container
docker run -p 8000:8000 --env-file .env \
  -e DATABASE_URL="postgresql://user:password@host.docker.internal:5432/database" \
  airqualityagent
```

Or update your `.env` file:

```env
DATABASE_URL=postgresql://user:password@host.docker.internal:5432/database
```

**Note:** Your application includes smart URL parsing that handles passwords containing `@` symbols, so you don't need to manually URL-encode them.

#### Option 2: Use Built-in SQLite Database

If you don't need to connect to an external database, use the default SQLite database which is self-contained within the container:

```env
# Comment out or remove DATABASE_URL to use SQLite
# DATABASE_URL=postgresql://...
```

The application will automatically use `sqlite:///./data/chat_sessions.db` when no `DATABASE_URL` is specified.

#### Option 3: Add Database to Docker Compose

For development, add your database as a service in `docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: airquality
      POSTGRES_PASSWORD: secure_password
      POSTGRES_DB: airquality_db
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks:
      - airquality-network

  airquality-agent:
    # ... existing config
    environment:
      - DATABASE_URL=postgresql://airquality:secure_password@postgres:5432/airquality_db
    depends_on:
      - postgres
```

**Testing Connection:**

```bash
# Test database connectivity from container
docker exec -it airquality-agent python -c "
import os
from sqlalchemy import create_engine
engine = create_engine(os.getenv('DATABASE_URL'))
try:
    with engine.connect() as conn:
        print('✓ Database connection successful')
except Exception as e:
    print(f'✗ Database connection failed: {e}')
"
```

## Best Practices

1. **Always use `.env` for secrets** - Never commit API keys to version control
2. **Use specific image tags** - Avoid `latest` in production
3. **Implement health checks** - Already configured in docker-compose.yml
4. **Set resource limits** - Prevent containers from consuming all resources
5. **Regular backups** - Automate database and Redis backups
6. **Monitor logs** - Set up log aggregation (ELK, Splunk, etc.)
7. **Use networks** - Isolate services using Docker networks
8. **Non-root user** - Already implemented in Dockerfile
9. **Multi-stage builds** - Reduce image size (already implemented)
10. **Regular updates** - Keep base images and dependencies updated

## Docker Image Size Optimization

Our Dockerfile implements several optimizations:

- **Multi-stage build**: Separates build and runtime environments
- **Slim base image**: Uses `python:3.10-slim` (not full Python image)
- **No cache**: `--no-cache-dir` flag for pip
- **Minimal runtime deps**: Only installs necessary packages
- **Single layer copies**: Combines commands to reduce layers
- **Virtual environment**: Isolates dependencies

Final image size: ~300-400MB (vs 1GB+ without optimization)

## Security Considerations

1. **Use secrets management** for production (Docker Secrets, Vault)
2. **Scan images** regularly for vulnerabilities:
   ```bash
   docker scan airquality-agent
   ```
3. **Update base images** regularly
4. **Limit container privileges** (already using non-root user)
5. **Use private registries** for production images
6. **Implement network policies** to restrict container communication

## Performance Tuning

### For High Traffic

```yaml
services:
  airquality-agent:
    command:
      [
        "uvicorn",
        "src.api.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--workers",
        "8",
        "--backlog",
        "2048",
      ]
    deploy:
      replicas: 3
```

### For Low Resource Environments

```yaml
services:
  airquality-agent:
    command:
      [
        "uvicorn",
        "src.api.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--workers",
        "1",
      ]
    deploy:
      resources:
        limits:
          memory: 1G
```

## Cloud Deployment

### AWS ECS

Use the Dockerfile with ECS Task Definitions.

### Google Cloud Run

```bash
# Build and push
gcloud builds submit --tag gcr.io/PROJECT_ID/airquality-agent

# Deploy
gcloud run deploy airquality-agent \
  --image gcr.io/PROJECT_ID/airquality-agent \
  --platform managed \
  --region us-central1 \
  --set-env-vars AI_API_KEY=xxx
```

### Azure Container Instances

```bash
az container create \
  --resource-group myResourceGroup \
  --name airquality-agent \
  --image airquality-agent:latest \
  --dns-name-label airquality \
  --ports 8000
```

## Support

For issues related to Docker deployment:

- Check the [Deployment Guide](./DEPLOYMENT.md)
- Review Docker logs: `docker-compose logs`
- Report issues on GitHub
