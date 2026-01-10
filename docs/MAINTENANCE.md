# AERIS-AQ Maintenance and Operations Guide

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Troubleshooting](#troubleshooting)
3. [Performance Tuning](#performance-tuning)
4. [Updating Dependencies](#updating-dependencies)
5. [Database Management](#database-management)
6. [Monitoring](#monitoring)
7. [Security](#security)
8. [Backup and Recovery](#backup-and-recovery)

## Daily Operations

### Health Check Procedure

**Automated Health Check**:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "healthy",
  "database": "connected",
  "cache": "operational",
  "timestamp": "2026-01-10T12:00:00Z"
}
```

**Manual Verification**:

1. Check server logs: `tail -f logs/app.log`
2. Verify database: `sqlite3 data/aeris_agent.db "SELECT COUNT(*) FROM sessions;"`
3. Test API endpoint: Send test query via curl or Postman
4. Check disk space: `df -h`
5. Monitor memory usage: `free -h`

### Log Rotation

Logs are stored in `logs/` directory:

- `app.log`: Application logs
- `errors.json`: Structured error logs
- `access.log`: API access logs

**Rotation Schedule**:

- Rotate daily at midnight
- Keep 30 days of history
- Compress logs older than 7 days

**Manual Rotation**:

```bash
cd logs
mv app.log app.log.$(date +%Y%m%d)
touch app.log
gzip app.log.$(date -d '7 days ago' +%Y%m%d)
find . -name "*.gz" -mtime +30 -delete
```

### Session Cleanup

**Automatic Cleanup**: Runs every 24 hours via background task

**Manual Cleanup**:

```python
from src.db.repository import AgentRepository

async def cleanup_old_sessions():
    repo = AgentRepository()
    deleted_count = await repo.cleanup_old_sessions(days_old=30)
    print(f"Deleted {deleted_count} old sessions")
```

## Troubleshooting

### Common Issues

#### Issue 1: API Not Responding

**Symptoms**:

- Timeout errors
- 503 Service Unavailable
- Connection refused

**Diagnosis**:

```bash
# Check if server is running
ps aux | grep uvicorn

# Check port availability
netstat -an | grep 8000

# Check logs
tail -n 100 logs/errors.json
```

**Solutions**:

1. Restart server: `./start_server.sh`
2. Check database: `sqlite3 data/aeris_agent.db ".tables"`
3. Verify environment variables: `cat .env | grep -v '#'`
4. Check disk space: `df -h`

#### Issue 2: Tool Execution Failures

**Symptoms**:

- "Tool execution failed" errors
- Missing data in responses
- Circuit breaker warnings

**Diagnosis**:

```bash
# Check tool executor logs
grep "Tool execution failed" logs/app.log

# Verify API keys
echo $WAQI_API_KEY
echo $AIRQO_API_KEY

# Test external API directly
curl "https://api.waqi.info/feed/london/?token=$WAQI_API_KEY"
```

**Solutions**:

1. Verify API keys in `.env`
2. Check API rate limits
3. Reset circuit breaker: restart server
4. Update base URLs if changed

#### Issue 3: High Latency

**Symptoms**:

- Response time > 30s
- Timeout errors
- Slow tool execution

**Diagnosis**:

```bash
# Check concurrent requests
grep "Concurrent requests" logs/app.log

# Monitor tool execution time
grep "tool execution time" logs/app.log | tail -20

# Check database size
du -sh data/aeris_agent.db
```

**Solutions**:

1. Enable parallel execution (already implemented)
2. Increase cache TTL
3. Optimize database queries
4. Add connection pooling
5. Scale horizontally (add more servers)

#### Issue 4: Model Not Responding

**Symptoms**:

- "Model unavailable" errors
- Empty responses
- Provider connection errors

**Diagnosis**:

```bash
# Check Ollama status (if using local models)
ollama list
curl http://localhost:11434/api/tags

# Check cloud provider API
curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models
```

**Solutions**:

1. Restart Ollama: `ollama serve`
2. Pull model: `ollama pull qwen2.5:3b`
3. Verify API keys for cloud providers
4. Switch to fallback provider in `.env`

#### Issue 5: Database Locked

**Symptoms**:

- "database is locked" errors
- SQLite busy timeout
- Failed writes

**Diagnosis**:

```bash
# Check for stale locks
fuser data/aeris_agent.db

# Check database integrity
sqlite3 data/aeris_agent.db "PRAGMA integrity_check;"
```

**Solutions**:

1. Close all connections: restart server
2. Increase busy timeout in config
3. Migrate to PostgreSQL for production
4. Enable WAL mode: `sqlite3 data/aeris_agent.db "PRAGMA journal_mode=WAL;"`

### Debug Mode

**Enable Debug Logging**:

```python
# In src/config.py
LOG_LEVEL = "DEBUG"
```

**Run in Debug Mode**:

```bash
uvicorn src.api.main:app --reload --log-level debug
```

**Analyze Logs**:

```bash
# Filter by session
grep "session_id=test-123" logs/app.log

# Filter by error
grep "ERROR" logs/app.log | tail -50

# Count errors by type
grep "ERROR" logs/app.log | cut -d':' -f4 | sort | uniq -c
```

## Performance Tuning

### Configuration Optimization

**File**: `src/config.py`

```python
# Connection pool settings
MAX_CONNECTIONS = 100  # Increase for high traffic
CONNECTION_TIMEOUT = 30  # Seconds

# Cache settings
CACHE_TTL = 300  # 5 minutes for air quality data
CACHE_MAX_SIZE = 1000  # Maximum cached items

# Session settings (based on Anthropic best practices)
MAX_MESSAGES_PER_SESSION = 100  # Prevents context overflow & cost escalation
SESSION_LIMIT_WARNING_THRESHOLD = 90  # Warn before hitting limit
SESSION_CLEANUP_DAYS = 30  # Archive old sessions
DISABLE_SESSION_LIMIT = false  # Set true ONLY for testing (see below)

# Model settings
TEMPERATURE = 0.7  # Lower for more deterministic
MAX_TOKENS = 2000  # Adjust based on use case
```

**⚠️ DISABLE_SESSION_LIMIT Flag**:

This flag bypasses session message limits. Use ONLY in controlled environments:

✅ **When to enable**:

- Comprehensive automated test suites (CI/CD pipelines)
- Development/debugging sessions requiring many iterations
- Performance benchmarking across extended conversations

❌ **When to disable** (default):

- Production deployments (always keep disabled)
- User-facing applications (cost and quality protection)
- Any environment with real user traffic

**Impact of disabling**:

- Token costs grow exponentially (each message includes full history)
- Model performance degrades (oversized context windows)
- Response quality suffers (loss of conversational focus)
- No protection against runaway costs

**Testing Example**:

```bash
# In .env.local for test environment
DISABLE_SESSION_LIMIT=true

# Run comprehensive tests
python tests/comprehensive_test_suite.py

# CRITICAL: Never deploy with this enabled!
```

### Database Optimization

**Enable WAL Mode** (Write-Ahead Logging):

```bash
sqlite3 data/aeris_agent.db "PRAGMA journal_mode=WAL;"
```

**Create Indexes**:

```sql
CREATE INDEX IF NOT EXISTS idx_sessions_created
  ON sessions(created_at);

CREATE INDEX IF NOT EXISTS idx_messages_session
  ON messages(session_id, created_at);
```

**Vacuum Database** (monthly):

```bash
sqlite3 data/aeris_agent.db "VACUUM;"
```

### AI Provider Optimization

#### Ollama (Local Models)

**Low-End Model Optimization**: The system automatically detects and optimizes for low-end models (1B-3B parameters):

**Automatic Optimizations Applied**:

```python
# When model name contains ":1b", ":3b", or ":0.5b"
max_tokens = 800        # vs 1200 for larger models
temperature = 0.35      # vs 0.45
top_p = 0.8            # vs 0.9
top_k = 40             # limited vocabulary
history = 8 messages   # vs 32 for larger models
retry_delay = 2.0s     # vs 1.0s
```

**Performance Tuning**:

```bash
# In .env file
AI_MODEL=qwen2.5:3b

# Ollama configuration (optional)
# Edit ~/.ollama/config.json
{
  "num_ctx": 8192,        # Context window (default: 2048)
  "num_thread": 8,        # CPU threads
  "num_gpu": 1,           # GPU layers (0 = CPU only)
  "temperature": 0.35     # Override default
}
```

**Memory Management**:

- **3B models**: ~2GB RAM required
- **7B models**: ~4GB RAM required
- **13B+ models**: ~8GB+ RAM required

**GPU Acceleration** (optional):

```bash
# Install CUDA support for Ollama
# Windows: Download from Ollama website
# Linux: Run with CUDA-enabled Docker image

# Verify GPU usage
nvidia-smi  # Check GPU memory usage during inference
```

#### OpenAI Compatible APIs

**Rate Limit Management**:

```python
# In src/config.py
OPENAI_MAX_RETRIES = 5
OPENAI_RETRY_DELAY = 2.0  # seconds
OPENAI_TIMEOUT = 60       # request timeout
```

**Cost Optimization**:

- Use caching aggressively (5-minute TTL for air quality data)
- Route simple queries to cheaper models (GPT-3.5-turbo vs GPT-4o)
- Set conservative max_tokens limits per style preset

#### Gemini Provider

**Quota Management**:

```python
# Monitor rate limits in logs
grep "GEMINI RATE LIMIT" logs/app.log

# Implement backoff strategy
GEMINI_RETRY_DELAY = 2.0
GEMINI_MAX_RETRIES = 3
```

**Context Window Optimization**:

- Gemini automatically truncates context intelligently
- Start new sessions after 50+ messages to prevent token overflow
- Use session cleanup endpoint: `DELETE /sessions/{session_id}`

### Caching Strategy

**Current Implementation**: In-memory cache with TTL

**Recommended Production Setup**:

```python
# Install Redis
pip install redis

# Update cache.py
import redis

cache = redis.Redis(
    host='localhost',
    port=6379,
    decode_responses=True
)

# Cache with TTL
cache.setex(key, ttl_seconds, value)
```

## Updating Dependencies

### Python Dependencies

**Check for Updates**:

```bash
pip list --outdated
```

**Update Safely**:

```bash
# 1. Backup current environment
pip freeze > requirements.backup.txt

# 2. Update dependencies
pip install --upgrade fastapi uvicorn

# 3. Test thoroughly
python tests/comprehensive_test_suite.py

# 4. Rollback if needed
pip install -r requirements.backup.txt
```

### Model Updates

**Ollama Models**:

```bash
# List available models
ollama list

# Pull new version
ollama pull qwen2.5:3b

# Remove old version
ollama rm old-model:tag

# Verify model works
curl http://localhost:11434/api/generate -d '{
  "model": "qwen2.5:3b",
  "prompt": "Test",
  "stream": false
}'
```

**Recommended Local Models by Use Case**:

**Low-End Hardware (2-4GB VRAM)**:

- `qwen2.5:3b` - Best quality for 3B size (recommended)
- `phi-3-mini` - Microsoft's efficient 3B model
- `gemma:2b` - Google's lightweight option

**Mid-Range Hardware (6-8GB VRAM)**:

- `qwen2.5:7b` - Excellent balance of quality/speed
- `mistral:7b` - Strong reasoning capabilities
- `llama3:8b` - Meta's latest 8B model

**High-End Hardware (12GB+ VRAM)**:

- `qwen2.5:14b` - Best quality without cloud
- `mixtral:8x7b` - MoE for complex reasoning
- `llama3:70b` - Enterprise-grade quality

**Cloud Models**:
Update model names in `.env`:

```bash
OPENAI_MODEL=gpt-4o-2024-11-20
GEMINI_MODEL=gemini-2.0-flash-exp
```

## Database Management

### Backup Procedure

**Automated Backup** (recommended):

```bash
#!/bin/bash
# backup.sh
BACKUP_DIR="/backups/aeris_agent"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR
sqlite3 data/aeris_agent.db ".backup $BACKUP_DIR/db_$DATE.db"
gzip $BACKUP_DIR/db_$DATE.db

# Keep only last 30 days
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete
```

**Schedule with Cron**:

```bash
crontab -e
# Add: 0 2 * * * /path/to/backup.sh
```

### Restore Procedure

```bash
# Stop server
pkill -f uvicorn

# Restore from backup
gunzip backups/aeris_agent/db_20260110_020000.db.gz
mv data/aeris_agent.db data/aeris_agent.db.old
cp backups/aeris_agent/db_20260110_020000.db data/aeris_agent.db

# Verify integrity
sqlite3 data/aeris_agent.db "PRAGMA integrity_check;"

# Restart server
./start_server.sh
```

### Migration to PostgreSQL

**When to Migrate**:

- More than 10,000 sessions
- Concurrent users > 50
- Write operations > 100/second

**Migration Steps**:

```bash
# 1. Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# 2. Create database
sudo -u postgres createdb aeris_agent

# 3. Update config
# src/config.py
DATABASE_URL = "postgresql://user:pass@localhost/aeris_agent"

# 4. Run migration
python scripts/migrate_sqlite_to_postgres.py

# 5. Test thoroughly
python tests/comprehensive_test_suite.py
```

## Monitoring

### Key Metrics

**Application Metrics**:

- Request rate: requests/second
- Response time: p50, p95, p99
- Error rate: errors/total requests
- Tool usage: calls per tool
- Session duration: messages per session

**System Metrics**:

- CPU usage: percentage
- Memory usage: MB/GB
- Disk usage: GB
- Network I/O: MB/s
- Database size: GB

### Monitoring Tools

**Prometheus + Grafana** (recommended):

```python
# Install
pip install prometheus-client

# Add to main.py
from prometheus_client import Counter, Histogram, generate_latest

request_count = Counter('http_requests_total', 'Total HTTP requests')
request_duration = Histogram('http_request_duration_seconds', 'HTTP request duration')

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

**Simple Logging-Based Monitoring**:

```bash
# Request rate
grep "HTTP Request" logs/access.log | wc -l

# Error rate
grep "ERROR" logs/app.log | wc -l

# Average response time
grep "response_time" logs/app.log | awk '{sum+=$NF; n++} END {print sum/n}'
```

### Alerting

**Set Up Alerts** (recommended thresholds):

- Error rate > 5%: Critical
- Response time p95 > 30s: Warning
- Disk usage > 80%: Warning
- CPU usage > 90%: Critical
- Failed logins > 10/min: Security alert

## Security

### Security Checklist

**Weekly**:

- [ ] Review access logs for suspicious activity
- [ ] Check for failed authentication attempts
- [ ] Verify API key rotation schedule
- [ ] Scan for dependency vulnerabilities: `pip-audit`

**Monthly**:

- [ ] Update dependencies with security patches
- [ ] Review and update firewall rules
- [ ] Audit user permissions
- [ ] Test backup restoration

**Quarterly**:

- [ ] Penetration testing
- [ ] Security audit
- [ ] Update SSL/TLS certificates
- [ ] Review and update security policies

### Vulnerability Scanning

```bash
# Scan Python dependencies
pip install pip-audit
pip-audit

# Scan for secrets in code
pip install detect-secrets
detect-secrets scan

# Check for outdated packages
pip list --outdated --format=json
```

### API Key Rotation

```bash
# 1. Generate new keys from provider
# 2. Update .env file
WAQI_API_KEY=new_key_here

# 3. Restart server
./start_server.sh

# 4. Verify functionality
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test", "message": "Test query"}'

# 5. Delete old keys from provider dashboard
```

## Backup and Recovery

### Disaster Recovery Plan

**RTO** (Recovery Time Objective): 4 hours
**RPO** (Recovery Point Objective): 24 hours

**Recovery Steps**:

1. Provision new server (if needed)
2. Install dependencies: `pip install -r requirements.txt`
3. Restore database from latest backup
4. Restore .env file from secure storage
5. Start server: `./start_server.sh`
6. Verify functionality: run test suite
7. Monitor logs for errors

### Backup Verification

**Monthly Verification**:

```bash
# 1. Extract latest backup
gunzip -c backups/latest.db.gz > test_restore.db

# 2. Verify integrity
sqlite3 test_restore.db "PRAGMA integrity_check;"

# 3. Check record count
sqlite3 test_restore.db "SELECT COUNT(*) FROM sessions;"

# 4. Cleanup
rm test_restore.db
```

## Emergency Contacts

**On-Call Rotation**:

- Primary: [Name] - [Phone] - [Email]
- Secondary: [Name] - [Phone] - [Email]
- Escalation: [Manager] - [Phone] - [Email]

**External Support**:

- Hosting Provider: [Support URL]
- Database Support: [Support URL]
- AI Provider Support: [Support URL]

## Runbook

### Server Restart

```bash
# 1. Check current status
ps aux | grep uvicorn

# 2. Graceful shutdown
pkill -SIGTERM -f uvicorn
sleep 5

# 3. Verify stopped
ps aux | grep uvicorn

# 4. Start server
./start_server.sh

# 5. Verify started
curl http://localhost:8000/health

# 6. Monitor logs
tail -f logs/app.log
```

### Database Corruption

```bash
# 1. Stop server
pkill -f uvicorn

# 2. Backup current database
cp data/aeris_agent.db data/aeris_agent.db.corrupt

# 3. Try to repair
sqlite3 data/aeris_agent.db <<EOF
PRAGMA integrity_check;
REINDEX;
VACUUM;
PRAGMA integrity_check;
EOF

# 4. If repair fails, restore from backup
gunzip -c backups/latest.db.gz > data/aeris_agent.db

# 5. Restart server
./start_server.sh
```

### High Load Response

```bash
# 1. Identify bottleneck
top -p $(pgrep -f uvicorn)
iostat -x 1
netstat -an | grep 8000 | wc -l

# 2. Scale up
# Option A: Increase worker processes
uvicorn src.api.main:app --workers 4

# Option B: Add load balancer + more servers
# (requires infrastructure changes)

# 3. Enable rate limiting
# Update config.py:
RATE_LIMIT_ENABLED = True
RATE_LIMIT_PER_MINUTE = 60

# 4. Monitor improvement
watch 'curl -s http://localhost:8000/health | jq'
```

## Version Control

### Release Checklist

**Before Release**:

- [ ] Run full test suite: `python tests/comprehensive_test_suite.py`
- [ ] Run lint checks: `python -m ruff check src/`
- [ ] Update CHANGELOG.md
- [ ] Update version in `src/__init__.py`
- [ ] Tag release: `git tag v2.10.1`

**After Release**:

- [ ] Deploy to staging
- [ ] Run smoke tests
- [ ] Deploy to production
- [ ] Monitor for 24 hours
- [ ] Update documentation

### Rollback Procedure

```bash
# 1. Identify last working version
git tag -l

# 2. Checkout previous version
git checkout v2.10.0

# 3. Restore database if needed
gunzip -c backups/pre_upgrade.db.gz > data/aeris_agent.db

# 4. Restart server
./start_server.sh

# 5. Verify functionality
python tests/comprehensive_test_suite.py
```

## Additional Resources

- Architecture Documentation: `docs/ARCHITECTURE.md`
- API Documentation: `http://localhost:8000/docs`
- Test Suite: `tests/comprehensive_test_suite.py`
- Configuration: `src/config.py`
- Logs: `logs/app.log`, `logs/errors.json`
