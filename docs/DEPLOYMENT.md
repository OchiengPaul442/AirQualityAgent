# Deploying Aeris

This guide covers deploying **Aeris**, your Air Quality AI Assistant, to production environments.

## Meet Aeris

**Aeris** is your friendly, knowledgeable Air Quality AI Assistant dedicated to helping you understand air quality data, environmental health, and pollution monitoring. Simply address Aeris by name in your conversations!

## Production Requirements

### Minimum System Requirements

- **CPU:** 2 cores
- **RAM:** 4 GB
- **Storage:** 10 GB
- **Network:** Stable internet connection with low latency to AI provider APIs

### Recommended System Requirements

- **CPU:** 4+ cores
- **RAM:** 8+ GB
- **Storage:** 20+ GB
- **Network:** High bandwidth, low latency

### Software Requirements

- Python 3.10 or higher
- Redis server (recommended)
- PostgreSQL (recommended for production database)
- Nginx or another reverse proxy
- Process manager (systemd, supervisor, or PM2)

## Environment Configuration

### Production Environment Variables

Create a `.env` file with production settings:

```env
# AI Provider (choose one)
AI_PROVIDER=gemini
AI_MODEL=gemini-2.5-flash
AI_API_KEY=your_production_api_key

# Database
DATABASE_URL=postgresql://user:password@localhost/airquality_db

# Redis Cache
REDIS_ENABLED=true
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password

# Data Sources
WAQI_API_KEY=your_waqi_key
AIRQO_API_TOKEN=your_airqo_token

# Performance
CACHE_TTL_SECONDS=3600
```

## Deployment Methods

### Method 1: Docker Deployment (Recommended)

See the [Docker Guide](./DOCKER.md) for container-based deployment.

### Method 2: Traditional Server Deployment

#### Step 1: Set Up the Server

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
sudo apt install python3.10 python3.10-venv python3-pip -y

# Install Redis
sudo apt install redis-server -y

# Install PostgreSQL (optional but recommended)
sudo apt install postgresql postgresql-contrib -y
```

#### Step 2: Create Application User

```bash
sudo useradd -m -s /bin/bash airquality
sudo su - airquality
```

#### Step 3: Deploy Application

```bash
# Clone repository
git clone https://github.com/OchiengPaul442/AirQualityAgent.git
cd AirQualityAgent

# Create virtual environment
python3.10 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
nano .env  # Edit with production values
```

#### Step 4: Set Up Database

```bash
# For PostgreSQL
sudo -u postgres psql

CREATE DATABASE airquality_db;
CREATE USER airquality WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE airquality_db TO airquality;
\q
```

#### Step 5: Configure Process Manager

**Using systemd:**

Create `/etc/systemd/system/airquality.service`:

```ini
[Unit]
Description=Air Quality AI Agent
After=network.target

[Service]
Type=simple
User=airquality
WorkingDirectory=/home/airquality/AirQualityAgent
Environment="PATH=/home/airquality/AirQualityAgent/.venv/bin"
ExecStart=/home/airquality/AirQualityAgent/.venv/bin/python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable airquality
sudo systemctl start airquality
sudo systemctl status airquality
```

#### Step 6: Configure Nginx Reverse Proxy

Create `/etc/nginx/sites-available/airquality`:

```nginx
upstream airquality_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 10M;

    location / {
        proxy_pass http://airquality_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/airquality /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### Step 7: Set Up SSL (Recommended)

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d your-domain.com
```

## Scaling for Production

### Horizontal Scaling

Run multiple application instances behind a load balancer:

```bash
# Start multiple workers
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Load Balancing with Nginx

Update nginx configuration:

```nginx
upstream airquality_backend {
    least_conn;
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
}
```

### Redis Clustering

For high availability, set up Redis in cluster mode or use Redis Sentinel.

## Monitoring and Logging

### Application Logs

Configure structured logging in production:

```python
# Add to src/config.py
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### System Monitoring

Use tools like:

- **Prometheus + Grafana** for metrics
- **ELK Stack** (Elasticsearch, Logstash, Kibana) for log aggregation
- **Sentry** for error tracking

### Health Checks

Set up automated health checks:

```bash
# Add to crontab
*/5 * * * * curl -f http://localhost:8000/health || systemctl restart airquality
```

## Backup Strategy

### Database Backups

```bash
# Daily PostgreSQL backup
pg_dump airquality_db | gzip > backup_$(date +%Y%m%d).sql.gz

# Retention: keep last 30 days
find /path/to/backups -name "*.sql.gz" -mtime +30 -delete
```

### Configuration Backups

```bash
# Backup .env file (encrypted)
gpg -c .env
```

## Security Hardening

### Firewall Configuration

```bash
# Allow only necessary ports
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

### Environment Security

- Never commit `.env` files to version control
- Use secrets management (e.g., HashiCorp Vault, AWS Secrets Manager)
- Rotate API keys regularly
- Use strong passwords for database and Redis

### API Rate Limiting

Already implemented in the application (20 requests/60 seconds per IP).

## Performance Optimization

### Database Optimization

```sql
-- Create indexes for frequently queried fields
CREATE INDEX idx_session_id ON chat_sessions(session_id);
CREATE INDEX idx_created_at ON chat_sessions(created_at);
```

### Redis Configuration

Edit `/etc/redis/redis.conf`:

```conf
maxmemory 2gb
maxmemory-policy allkeys-lru
```

### Python Optimization

- Use uvicorn with multiple workers
- Enable HTTP/2 in nginx
- Implement connection pooling

## Troubleshooting

### Service Won't Start

```bash
# Check logs
sudo journalctl -u airquality -n 50

# Check process status
sudo systemctl status airquality
```

### High Memory Usage

```bash
# Monitor memory
htop

# Reduce workers or implement memory limits
```

### Slow Response Times

- Check Redis connection
- Review AI provider API latency
- Increase cache TTL for non-critical queries
- Add more worker processes

## Maintenance

### Regular Updates

```bash
# Pull latest changes
cd /home/airquality/AirQualityAgent
git pull

# Update dependencies
source .venv/bin/activate
pip install -r requirements.txt --upgrade

# Restart service
sudo systemctl restart airquality
```

### Log Rotation

Configure logrotate for application logs:

```
/var/log/airquality/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 airquality airquality
}
```

## Cost Optimization

### AI Provider Costs

- Monitor token usage via the API responses
- Implement aggressive caching for educational content
- Use cheaper models for simple queries
- Set up budget alerts with your AI provider

### Infrastructure Costs

- Use smaller instances initially and scale as needed
- Implement auto-scaling based on load
- Use managed Redis/PostgreSQL services for easier maintenance

## Support and Resources

For deployment assistance:

- GitHub Issues: [Report problems](https://github.com/OchiengPaul442/AirQualityAgent/issues)
- Documentation: Check other docs in this folder
