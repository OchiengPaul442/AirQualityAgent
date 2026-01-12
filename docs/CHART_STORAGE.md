# Chart Storage System

This document explains the chart storage system implemented in Aeris-AQ.

## Overview

Charts are stored using a dual-backend approach:

- **Primary**: Cloudinary (cloud CDN storage)
- **Fallback**: Local filesystem

Charts are organized by session ID for automatic cleanup when sessions are deleted.

## Configuration

Add these environment variables to `.env`:

```env
# Cloudinary Configuration (Optional - falls back to local storage if not set)
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

## How It Works

### 1. Chart Generation

When a chart is requested:

1. The visualization service generates the chart as PNG bytes
2. The chart storage service saves it:
   - Tries Cloudinary first (if configured)
   - Falls back to local filesystem if Cloudinary fails or is not configured
3. Returns a URL in the format:
   - **Cloudinary**: `https://res.cloudinary.com/{cloud_name}/image/upload/...`
   - **Local**: `/charts/{session_id}/{filename}.png`

### 2. Storage Organization

**Cloudinary Structure:**

```
aeris-aq/
  charts/
    {session_id}/
      chart_{timestamp}_{hash}.png
      chart_{timestamp}_{hash}.png
```

**Local Structure:**

```
charts/
  {session_id}/
    chart_{timestamp}_{hash}.png
    chart_{timestamp}_{hash}.png
  default/  # For charts without session_id
```

### 3. Automatic Cleanup

Charts are automatically cleaned up:

**On Session Deletion:**

- When `DELETE /api/v1/sessions/{session_id}` is called
- All charts for that session are deleted from both Cloudinary and local storage

**On Startup:**

- Charts older than 24 hours are automatically deleted
- Prevents disk space issues from abandoned sessions

## API Usage

### Serving Charts

Charts are served via:

**Local Storage:**

```
GET /charts/{session_id}/{filename}
```

**Cloudinary:**

```
Direct CDN URL returned by the API
```

### Session Management with Charts

```python
# Create a session and generate charts
POST /api/v1/agent/chat
{
  "message": "Create a chart of PM2.5 data",
  "session_id": "abc-123"
}

# Response includes chart URL
{
  "response": "Here's your chart: ![Chart](/charts/abc-123/chart_20260112_123456_abc123.png)"
}

# Delete session and cleanup charts
DELETE /api/v1/sessions/abc-123
```

## Implementation Details

### Chart Storage Service

Located in `infrastructure/storage/chart_storage.py`:

```python
from infrastructure.storage.chart_storage import get_chart_storage_service

storage = get_chart_storage_service()

# Save a chart
result = storage.save_chart(
    chart_bytes=png_bytes,
    session_id="abc-123",
    chart_type="line"
)
# Returns: {"url": "...", "backend": "cloudinary", "session_id": "abc-123"}

# Delete session charts
cleanup = storage.delete_session_charts("abc-123")
# Returns: {"deleted": 5, "errors": 0, "message": "Deleted 5 charts"}

# Cleanup old charts
count = storage.cleanup_old_charts(max_age_hours=24)
```

### Visualization Service Integration

The visualization service automatically uses chart storage:

```python
from infrastructure.api.visualization import get_visualization_service

viz = get_visualization_service()

result = viz.generate_chart(
    data=data,
    chart_type="line",
    session_id="abc-123",  # Required for proper organization
    output_format="file"  # Use "file" for URL, "base64" for inline
)
```

## Benefits

1. **Scalability**: Cloudinary provides CDN-backed storage
2. **Reliability**: Automatic fallback to local storage
3. **Clean Organization**: Session-based folders for easy management
4. **Automatic Cleanup**: No manual intervention needed
5. **Cost Effective**: Free tier of Cloudinary is sufficient for most use cases

## Cloudinary Free Tier

- Storage: 25 GB
- Bandwidth: 25 GB/month
- Transformations: 25,000/month

For Aeris-AQ, this is typically sufficient for:

- ~100,000 charts (assuming 250KB each)
- Thousands of daily users

## Troubleshooting

### Charts not displaying

1. **Check Cloudinary configuration**:

   ```bash
   # Verify environment variables are set
   echo $CLOUDINARY_CLOUD_NAME
   ```

2. **Check local fallback**:

   ```bash
   # Verify charts directory exists
   ls charts/
   ```

3. **Check logs**:
   ```
   Look for "✓ Cloudinary storage initialized" or fallback messages
   ```

### Cleanup not working

1. **Verify storage service is tracking charts**:

   - Charts must be created through the visualization service
   - Direct file creation bypasses tracking

2. **Check session deletion**:
   - Ensure `DELETE /sessions/{session_id}` is called
   - Check logs for cleanup confirmation

## Migration from Old System

If migrating from the old chart storage system:

1. **Remove old static file mounting**:

   ```python
   # Remove this from main.py
   app.mount("/charts", StaticFiles(directory="charts"), name="charts")
   ```

2. **Update chart serving endpoint**:

   ```python
   # Update to session-based serving
   @app.get("/charts/{session_id}/{filename}")
   ```

3. **Clean up old charts**:
   ```bash
   # Remove old flat chart structure
   rm charts/*.png
   ```

## Future Enhancements

Potential improvements:

- Add Azure Blob Storage as another backend option
- Implement chart compression before upload
- Add chart metadata for analytics
- Support different image formats (SVG, WebP)
- Add chart sharing with public URLs
