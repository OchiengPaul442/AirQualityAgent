# Document Upload & Analysis API Guide

## Overview

Upload and analyze PDF, CSV, or Excel files with **in-memory processing** for cost-effective analysis. Files are **never stored** on the server - processed entirely in RAM and immediately discarded.

**Key Benefits:**

- ✅ **No Server Storage** - Zero disk usage, pure in-memory
- ✅ **8MB Limit** - Optimized for cost and performance
- ✅ **Secure** - Files discarded after processing
- ✅ **Fast** - Streaming chunks prevent memory spikes

---

## Quick Start

### Endpoint

```
POST /api/v1/air-quality/query
Content-Type: multipart/form-data
```

### Parameters

- `document` (file, optional) - PDF/CSV/Excel file, max 8MB
- `city` (string, optional) - City name
- `latitude`/`longitude` (numbers, optional) - Coordinates
- `include_forecast` (boolean, optional) - Include forecasts

### Supported Files

| Type  | Extensions      | Max Size | Best For         |
| ----- | --------------- | -------- | ---------------- |
| PDF   | `.pdf`          | 8MB      | Reports, papers  |
| CSV   | `.csv`          | 8MB      | Time-series data |
| Excel | `.xlsx`, `.xls` | 8MB      | Multi-sheet data |

---

## Code Examples

### Python

```python
import requests

# Client-side validation
import os
file_path = 'air_quality_data.csv'
if os.path.getsize(file_path) > 8 * 1024 * 1024:
    print("Error: File exceeds 8MB limit")
    exit(1)

# Upload
with open(file_path, 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/v1/air-quality/query',
        data={'city': 'Kampala', 'include_forecast': True},
        files={'document': f}
    )

result = response.json()
print("Air Quality:", result.get('waqi'))
print("Document:", result.get('document'))
```

### JavaScript/React

```javascript
import React, { useState } from "react";

function FileUpload() {
  const MAX_SIZE = 8 * 1024 * 1024; // 8MB

  const handleSubmit = async (e) => {
    e.preventDefault();
    const file = e.target.file.files[0];

    // Client-side validation
    if (file.size > MAX_SIZE) {
      alert("File must be under 8MB");
      return;
    }

    const formData = new FormData();
    formData.append("city", "Kampala");
    formData.append("document", file);

    try {
      const res = await fetch("/api/v1/air-quality/query", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const error = await res.json();
        alert(error.detail);
        return;
      }

      const data = await res.json();
      console.log("Results:", data);
    } catch (err) {
      alert("Upload failed: " + err.message);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input type="file" name="file" accept=".pdf,.csv,.xlsx,.xls" />
      <small>Max 8MB</small>
      <button type="submit">Upload & Analyze</button>
    </form>
  );
}
```

### Vue 3

```vue
<template>
  <form @submit.prevent="upload">
    <input type="file" @change="handleFile" accept=".pdf,.csv,.xlsx,.xls" />
    <p v-if="error" class="error">{{ error }}</p>
    <small>Max 8MB</small>
    <button type="submit" :disabled="!file">Upload</button>
  </form>
</template>

<script setup>
import { ref } from "vue";

const file = ref(null);
const error = ref("");
const MAX_SIZE = 8 * 1024 * 1024;

const handleFile = (e) => {
  const f = e.target.files[0];
  if (f.size > MAX_SIZE) {
    error.value = "File exceeds 8MB";
    return;
  }
  error.value = "";
  file.value = f;
};

const upload = async () => {
  const formData = new FormData();
  formData.append("city", "Kampala");
  formData.append("document", file.value);

  const res = await fetch("/api/v1/air-quality/query", {
    method: "POST",
    body: formData,
  });

  const data = await res.json();
  console.log("Results:", data);
};
</script>
```

### cURL

```bash
# Upload CSV
curl -X POST "http://localhost:8000/api/v1/air-quality/query" \
  -F "city=Nairobi" \
  -F "document=@data.csv"

# Upload Excel with forecast
curl -X POST "http://localhost:8000/api/v1/air-quality/query" \
  -F "latitude=-1.2864" \
  -F "longitude=36.8172" \
  -F "include_forecast=true" \
  -F "document=@report.xlsx"
```

---

## Response Format

### Success

```json
{
  "waqi": { "aqi": 65, ... },
  "document": {
    "filename": "data.csv",
    "file_type": "csv",
    "content": "CSV File: data.csv\nRows: 100, Columns: 5\n...",
    "metadata": {
      "rows": 100,
      "columns": 5,
      "column_names": ["date", "pm25", "pm10", "aqi"]
    },
    "truncated": false
  }
}
```

### Errors

```json
// Too large
{ "detail": "File size exceeds 8MB limit. Please upload a smaller file." }

// Wrong type
{ "detail": "Unsupported file type: .docx. Allowed: PDF, CSV, Excel (.xlsx, .xls)" }
```

---

## Best Practices

### Client-Side Validation (Required)

```javascript
// Always validate BEFORE uploading
const MAX_SIZE = 8 * 1024 * 1024;
const ALLOWED = ["pdf", "csv", "xlsx", "xls"];

if (file.size > MAX_SIZE) {
  alert("File exceeds 8MB limit");
  return;
}

const ext = file.name.split(".").pop().toLowerCase();
if (!ALLOWED.includes(ext)) {
  alert("Unsupported file type");
  return;
}
```

### Progress Indicator

```javascript
const xhr = new XMLHttpRequest();
xhr.upload.addEventListener("progress", (e) => {
  const percent = (e.loaded / e.total) * 100;
  console.log(`Upload: ${percent}%`);
});
```

### Error Handling

```javascript
try {
  const res = await fetch("/api/v1/air-quality/query", {
    method: "POST",
    body: formData,
  });

  if (res.status === 413) {
    alert("File too large (max 8MB)");
  } else if (!res.ok) {
    const error = await res.json();
    alert(error.detail);
  } else {
    const data = await res.json();
    // Process success
  }
} catch (err) {
  alert("Network error: " + err.message);
}
```

### Memory Management

```javascript
// After upload, release references
fileInput.value = "";
file = null;
```

---

## Performance

### Benchmarks

| File Type | Size | Process Time | RAM Usage |
| --------- | ---- | ------------ | --------- |
| PDF       | 2MB  | 1-2s         | ~4MB      |
| CSV       | 5MB  | 2-3s         | ~10MB     |
| Excel     | 8MB  | 3-5s         | ~16MB     |

### Server-Side (Automatic)

- ✅ Streaming: 1MB chunks
- ✅ In-memory: No disk I/O
- ✅ Auto-cleanup: Immediate memory release
- ✅ Early rejection: Size validated during upload

### Client-Side (Your Responsibility)

- Compress files before upload
- Sample large datasets
- Use CSV over Excel for simple data
- Implement retry logic

---

## Security

1. **Whitelist**: Only PDF/CSV/Excel
2. **Size Limit**: 8MB enforced
3. **No Storage**: Never written to disk
4. **Immediate Cleanup**: Memory freed instantly
5. **Streaming Validation**: Size checked during upload

---

## Troubleshooting

### File Too Large

```python
# Sample CSV to reduce size
import pandas as pd
df = pd.read_csv('large.csv')
df.sample(n=10000).to_csv('sample.csv', index=False)
```

### Unsupported Type

- Word → Export as PDF
- Text → Save as CSV
- Google Sheets → Download as Excel

### Processing Failed

- Check file isn't corrupted
- Remove password protection from PDF
- Use standard Excel format (not macros)
- Validate CSV format

---

## FAQ

**Q: Are files stored?**
A: No. Processed in RAM only, never saved.

**Q: Multiple files at once?**
A: No. One file per request.

**Q: What happens after processing?**
A: Memory released immediately.

**Q: Password-protected PDFs?**
A: Not supported.

**Q: Rate limits?**
A: 20 requests/minute.

**Q: Can I exceed 8MB?**
A: No. Hard limit for cost optimization.

**Q: Recommended size?**
A: Under 5MB for best performance.

---

**Version**: 2.2.0  
**Max File Size**: 8MB  
**Processing**: In-Memory (Zero Disk Storage)
