# Redis Setup Guide for Air Quality AI Agent

## Overview

The agent now uses Redis for high-performance caching of API responses and analysis results. This significantly improves response times and reduces API calls.

## Benefits of Redis Caching

1. **Performance**: Sub-millisecond response times for cached data
2. **Cost Efficiency**: Reduces API calls to external services
3. **Scalability**: Handles high concurrent requests
4. **Persistence**: Optional disk persistence for cache durability
5. **Memory Efficiency**: Automatic TTL-based expiration

## Installation

### Option 1: Docker (Recommended)

```bash
# Pull Redis image
docker pull redis:latest

# Run Redis with persistence
docker run -d \
  --name airquality-redis \
  -p 6379:6379 \
  -v redis-data:/data \
  redis:latest redis-server --appendonly yes

# With password protection
docker run -d \
  --name airquality-redis \
  -p 6379:6379 \
  -v redis-data:/data \
  redis:latest redis-server --appendonly yes --requirepass your_password
```

### Option 2: Windows (MSI Installer)

1. Download Redis from: https://github.com/microsoftarchive/redis/releases
2. Install Redis MSI package
3. Redis will run as a Windows service on port 6379

### Option 3: Linux (APT)

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install redis-server

# Start Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Verify
redis-cli ping
# Should return: PONG
```

### Option 4: macOS (Homebrew)

```bash
brew install redis
brew services start redis

# Verify
redis-cli ping
```

## Configuration

### Environment Variables

Add to your `.env` file:

```env
# Redis Configuration
REDIS_ENABLED=true
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=         # Leave empty if no password

# Cache TTL (Time To Live)
CACHE_TTL_SECONDS=3600  # 1 hour
```

### Fallback Mode

If Redis is unavailable, the agent automatically falls back to in-memory caching without errors.

## Testing Redis

### 1. Test Connection

```bash
# Without password
redis-cli ping

# With password
redis-cli -a your_password ping
```

### 2. Test from Python

```python
from src.services.cache import get_cache

# Initialize cache
cache = get_cache()

# Test set/get
cache.set("test", "key", "value")
result = cache.get("test", "key")
print(f"Result: {result}")  # Should print: Result: value
```

### 3. Monitor Cache Activity

```bash
# Real-time monitoring
redis-cli monitor

# View all keys
redis-cli KEYS "airquality:*"

# Get cache statistics
redis-cli INFO stats
```

## Cache Namespaces

The agent organizes cache by namespace:

- `airquality:api:waqi:*` - WAQI API responses
- `airquality:api:airqo:*` - AirQo API responses
- `airquality:analysis:*` - Analysis results

## Cache Management

### Clear Specific Namespace

```python
from src.services.cache import get_cache

cache = get_cache()

# Clear all WAQI data
cache.clear_namespace("api:waqi")

# Clear all AirQo data
cache.clear_namespace("api:airqo")

# Clear all analysis results
cache.clear_namespace("analysis")
```

### Manual Cache Clear (CLI)

```bash
# Clear all air quality cache
redis-cli KEYS "airquality:*" | xargs redis-cli DEL

# Clear specific source
redis-cli KEYS "airquality:api:waqi:*" | xargs redis-cli DEL
```

## Performance Tuning

### Redis Configuration (redis.conf)

```conf
# Memory management
maxmemory 256mb
maxmemory-policy allkeys-lru

# Persistence (optional)
save 900 1
save 300 10
save 60 10000

# Performance
tcp-backlog 511
timeout 0
tcp-keepalive 300
```

### Application Settings

Adjust cache TTL based on data freshness requirements:

```env
# More frequent updates (5 minutes)
CACHE_TTL_SECONDS=300

# Longer cache (2 hours)
CACHE_TTL_SECONDS=7200

# Balance (1 hour - recommended)
CACHE_TTL_SECONDS=3600
```

## Production Deployment

### Redis Cloud Services

1. **Redis Labs**: https://redis.com/try-free/
2. **AWS ElastiCache**: https://aws.amazon.com/elasticache/
3. **Azure Cache for Redis**: https://azure.microsoft.com/services/cache/
4. **Google Cloud Memorystore**: https://cloud.google.com/memorystore

### Example: Redis Labs

```env
REDIS_ENABLED=true
REDIS_HOST=redis-12345.c1.us-east-1-1.ec2.cloud.redislabs.com
REDIS_PORT=12345
REDIS_DB=0
REDIS_PASSWORD=your_redis_password
```

## Security Best Practices

1. **Always use passwords in production**

   ```bash
   redis-cli CONFIG SET requirepass "strong_password"
   ```

2. **Bind to localhost only** (if not using remote)

   ```conf
   bind 127.0.0.1 ::1
   ```

3. **Disable dangerous commands**

   ```conf
   rename-command FLUSHDB ""
   rename-command FLUSHALL ""
   rename-command CONFIG ""
   ```

4. **Use TLS/SSL for remote connections**
   ```env
   REDIS_SSL=true
   ```

## Monitoring & Debugging

### Check Cache Hit Rate

```bash
redis-cli INFO stats | grep keyspace
```

### View Cache Size

```bash
redis-cli INFO memory
```

### Debug Cache Keys

```python
from src.services.cache import get_cache

cache = get_cache()

# Check if key exists
exists = cache.get("api:waqi", "some_key")
print(f"Cached: {exists is not None}")
```

## Troubleshooting

### Connection Refused

```
Error: Redis connection failed: Error 111 connecting to localhost:6379. Connection refused.
```

**Solution**: Start Redis service

```bash
# Linux
sudo systemctl start redis-server

# Docker
docker start airquality-redis

# Check if running
redis-cli ping
```

### Out of Memory

```
Error: OOM command not allowed when used memory > 'maxmemory'
```

**Solution**: Increase maxmemory or adjust policy

```bash
redis-cli CONFIG SET maxmemory 512mb
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

### Slow Response

**Solution**: Check Redis performance

```bash
redis-cli --latency
redis-cli --latency-history
redis-cli slowlog get 10
```

## Disabling Redis

To use in-memory caching only:

```env
REDIS_ENABLED=false
```

The agent will automatically fall back to Python dictionaries for caching.

## Performance Metrics

With Redis enabled:

- **Cache Hit**: ~1-2ms response time
- **Cache Miss**: ~100-500ms (API call + cache store)
- **Memory Usage**: ~10-50MB depending on cache size
- **Throughput**: 10,000+ requests/second

Without Redis (memory only):

- **Cache Hit**: ~0.1ms response time
- **Cache Miss**: ~100-500ms (API call + memory store)
- **Memory Usage**: Grows with process memory
- **Throughput**: Limited by process resources

## Best Practices

1. ✅ **Use Redis in production** for better performance
2. ✅ **Set appropriate TTL** based on data freshness needs
3. ✅ **Monitor cache hit rates** to optimize TTL
4. ✅ **Use password protection** in production
5. ✅ **Enable persistence** for important cached data
6. ✅ **Regular monitoring** with Redis CLI or monitoring tools
7. ✅ **Clear cache** after major data updates

## Example Usage

```python
from src.services.waqi_service import WAQIService

# Initialize service (with Redis caching)
waqi = WAQIService()

# First call - fetches from API (slow)
data1 = waqi.get_city_feed("london")  # ~200ms

# Second call - fetches from Redis (fast)
data2 = waqi.get_city_feed("london")  # ~1ms

# Same data, much faster!
assert data1 == data2
```

---

**Redis is optional but highly recommended for production deployments!**
