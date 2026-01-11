# API Integration Guide

Complete guide for integrating the Air Quality Agent API into frontend applications (React/Next.js/Vue).

## Quick Reference

### Endpoints

| Endpoint                                  | Method | Purpose                        | Use When                      |
| ----------------------------------------- | ------ | ------------------------------ | ----------------------------- |
| `/api/v1/agent/chat`                      | POST   | Simple request/response        | Standard chat interface       |
| `/api/v1/agent/chat/stream`               | POST   | SSE streaming                  | Real-time progress updates    |
| `/api/v1/sessions`                        | GET    | List sessions                  | Session management UI         |
| `/api/v1/sessions/{id}`                   | GET    | Get session details            | Session history and messages  |
| `/api/v1/sessions/{id}`                   | DELETE | Delete session                 | Clear conversation            |
| `/api/v1/sessions/new`                    | POST   | Create new session             | Start new conversation        |
| `/api/v1/health`                          | GET    | Health check                   | Service availability          |
| `/api/v1/visualization/charts/{filename}` | GET    | Serve generated chart images   | Display charts in markdown    |
| `/api/v1/visualization/capabilities`      | GET    | Get visualization capabilities | Check supported formats/types |

### Base URL

```
http://localhost:8000/api/v1
```

---

## 1. Simple Chat API (REST)

### Request Format

```typescript
const formData = new FormData();
formData.append("message", "What is PM2.5?");
formData.append("session_id", "optional-session-id"); // Optional
formData.append("style", "general"); // Optional: general|technical|executive|simple|policy
// Optional file upload:
// formData.append('file', fileObject);

const response = await fetch("http://localhost:8000/api/v1/agent/chat", {
  method: "POST",
  body: formData,
});

const data = await response.json();
```

### Response Format

```typescript
{
  "response": "PM2.5 refers to particulate matter...",
  "session_id": "abc-123-def",
  "tokens_used": 1234,
  "cost_estimate": 0.0012,
  "cached": false,
  "tools_used": ["get_city_air_quality"]
}
```

### React Hook Example

```typescript
import { useState } from "react";

export const useChat = () => {
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<string>("");

  const sendMessage = async (message: string, sessionId?: string) => {
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("message", message);
      if (sessionId) formData.append("session_id", sessionId);

      const res = await fetch("/api/v1/agent/chat", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      setResponse(data.response);
      return data;
    } catch (error) {
      console.error("Chat error:", error);
    } finally {
      setLoading(false);
    }
  };

  return { sendMessage, loading, response };
};
```

---

## 2. Streaming API (SSE)

### Why Use Streaming?

- ✅ Real-time progress updates
- ✅ Better perceived performance
- ✅ Transparent AI reasoning
- ✅ Modern chat UX (like ChatGPT/Claude)

### Event Types

| Event      | Description           | When Emitted      |
| ---------- | --------------------- | ----------------- |
| `thought`  | Agent reasoning steps | During processing |
| `response` | Final answer          | After completion  |
| `done`     | Stream complete       | End of stream     |
| `error`    | Error occurred        | On failure        |

### Streaming Request

```typescript
const formData = new FormData();
formData.append("message", "What is air quality in London?");
formData.append("session_id", sessionId); // Optional

const response = await fetch("http://localhost:8000/api/v1/agent/chat/stream", {
  method: "POST",
  body: formData,
});

// Parse SSE stream
const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const chunk = decoder.decode(value);
  // Process SSE events (see examples below)
}
```

### React Streaming Hook

```typescript
import { useState } from "react";

interface ThoughtEvent {
  type: string;
  title: string;
  details: any;
  timestamp: string;
  progress: number;
}

export const useStreamingChat = () => {
  const [loading, setLoading] = useState(false);
  const [thoughts, setThoughts] = useState<ThoughtEvent[]>([]);
  const [response, setResponse] = useState<string>("");

  const streamMessage = async (message: string, sessionId?: string) => {
    setLoading(true);
    setThoughts([]);
    setResponse("");

    try {
      const formData = new FormData();
      formData.append("message", message);
      if (sessionId) formData.append("session_id", sessionId);

      const res = await fetch("/api/v1/agent/chat/stream", {
        method: "POST",
        body: formData,
      });

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\\n");
        buffer = lines.pop() || "";

        for (let i = 0; i < lines.length; i++) {
          const line = lines[i].trim();

          if (line.startsWith("event: ")) {
            const eventType = line.substring(7);
            const dataLine = lines[i + 1];

            if (dataLine?.startsWith("data: ")) {
              const data = JSON.parse(dataLine.substring(6));

              if (eventType === "thought") {
                setThoughts((prev) => [...prev, data]);
              } else if (eventType === "response") {
                setResponse(data.data.response);
              } else if (eventType === "done") {
                setLoading(false);
              } else if (eventType === "error") {
                console.error("Stream error:", data);
                setLoading(false);
              }
            }
          }
        }
      }
    } catch (error) {
      console.error("Streaming error:", error);
      setLoading(false);
    }
  };

  return { streamMessage, loading, thoughts, response };
};
```

### Thought Event Structure

```typescript
{
  "type": "query_analysis",
  "title": "Understanding your question",
  "details": {
    "query_preview": "What's the air quality in...",
    "detected_intent": "air_quality_data",
    "complexity": "simple",
    "requires_external_data": true
  },
  "timestamp": "2026-01-10T10:30:00Z",
  "progress": 0.2
}
```

### Response Event Structure

```typescript
{
  "type": "response",
  "data": {
    "response": "# Air Quality in London\\n\\n...",
    "tools_used": ["get_city_air_quality"],
    "tokens_used": 1234,
    "cost_estimate": 0.0012,
    "cached": false,
    "session_id": "abc-123-..."
  }
}
```

---

## 3. Complete React Component Example

```typescript
import { useState } from "react";

export const ChatInterface = () => {
  const [message, setMessage] = useState("");
  const [sessionId, setSessionId] = useState<string>();
  const [loading, setLoading] = useState(false);
  const [thoughts, setThoughts] = useState<any[]>([]);
  const [response, setResponse] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim() || loading) return;

    setLoading(true);
    setThoughts([]);
    setResponse("");

    try {
      const formData = new FormData();
      formData.append("message", message);
      if (sessionId) formData.append("session_id", sessionId);

      const res = await fetch("/api/v1/agent/chat/stream", {
        method: "POST",
        body: formData,
      });

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\\n");
        buffer = lines.pop() || "";

        for (let i = 0; i < lines.length; i++) {
          const line = lines[i].trim();

          if (line.startsWith("event: ")) {
            const eventType = line.substring(7);
            const dataLine = lines[i + 1];

            if (dataLine?.startsWith("data: ")) {
              const data = JSON.parse(dataLine.substring(6));

              if (eventType === "thought") {
                setThoughts((prev) => [...prev, data]);
              } else if (eventType === "response") {
                setResponse(data.data.response);
                if (!sessionId) setSessionId(data.data.session_id);
              } else if (eventType === "done") {
                setLoading(false);
              }
            }
          }
        }
      }
    } catch (error) {
      console.error("Error:", error);
      setLoading(false);
    }

    setMessage("");
  };

  return (
    <div className="chat-container">
      <div className="messages">
        {thoughts.map((thought, i) => (
          <div key={i} className="thought-item">
            <div className="thought-title">{thought.title}</div>
            <div className="thought-progress">
              {(thought.progress * 100).toFixed(0)}%
            </div>
          </div>
        ))}
        {response && (
          <div
            className="response"
            dangerouslySetInnerHTML={{ __html: response }}
          />
        )}
      </div>

      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Ask about air quality..."
          disabled={loading}
        />
        <button type="submit" disabled={loading || !message.trim()}>
          {loading ? "Thinking..." : "Send"}
        </button>
      </form>
    </div>
  );
};
```

---

## 4. Session Management

### Create New Session

```typescript
const createSession = async () => {
  const res = await fetch("/api/v1/sessions/new", {
    method: "POST",
  });
  const data = await res.json();
  return data.session_id;
};
```

### Delete Session

```typescript
const deleteSession = async (sessionId: string) => {
  await fetch(`/api/v1/sessions/${sessionId}`, {
    method: "DELETE",
  });
};
```

---

## 5. File Upload

### With Chat Request

```typescript
const sendMessageWithFile = async (message: string, file: File) => {
  const formData = new FormData();
  formData.append("message", message);
  formData.append("file", file);

  const res = await fetch("/api/v1/agent/chat", {
    method: "POST",
    body: formData,
  });

  return await res.json();
};
```

### Supported File Types

- PDF documents
- CSV data files
- Excel spreadsheets (XLSX)

---

## 6. Error Handling

```typescript
try {
  const res = await fetch("/api/v1/agent/chat", {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Request failed");
  }

  const data = await res.json();
  return data;
} catch (error) {
  console.error("API Error:", error);
  // Show error to user
}
```

---

## 7. Performance Tips

### For <3 Second Responses

1. **Use Fast AI Provider**:

   - ✅ Gemini 1.5 Flash (recommended)
   - ✅ GPT-4 Turbo
   - ❌ Avoid Ollama in production (10-20s)

2. **Enable Request Caching**:

   - Duplicate queries return instantly
   - Check `cached: true` in response

3. **Use Appropriate Style**:

   - `simple` = Faster, shorter responses
   - `technical` = Slower, more detailed

4. **Monitor Performance**:
   - Check `tokens_used` and `cost_estimate`
   - Optimize message length

---

## 8. TypeScript Types

```typescript
// Request
interface ChatRequest {
  message: string;
  session_id?: string;
  style?: "general" | "technical" | "executive" | "simple" | "policy";
  latitude?: number;
  longitude?: number;
  file?: File;
}

// Response
interface ChatResponse {
  response: string;
  session_id: string;
  tokens_used: number;
  cost_estimate: number;
  cached: boolean;
  tools_used: string[];
}

// Thought Event
interface ThoughtEvent {
  type:
    | "query_analysis"
    | "tool_selection"
    | "tool_execution"
    | "data_retrieval"
    | "response_synthesis"
    | "complete";
  title: string;
  details: Record<string, any>;
  timestamp: string;
  progress: number;
}

// Streaming Response
interface StreamResponse {
  type: "response";
  data: ChatResponse;
}
```

---

## 9. Best Practices

### Do's ✅

- Use streaming for better UX
- Show progress indicators
- Cache session IDs
- Handle errors gracefully
- Display cost/token metrics

### Don'ts ❌

- Don't send huge files (>10MB)
- Don't spam requests without debouncing
- Don't ignore error events
- Don't forget to close EventSource
- Don't use polling instead of streaming

---

## 10. Testing

### cURL Example

```bash
# Simple chat
curl -X POST http://localhost:8000/api/v1/agent/chat \\
  -F "message=What is PM2.5?"

# Streaming
curl -X POST http://localhost:8000/api/v1/agent/chat/stream \\
  -F "message=Air quality in London" \\
  --no-buffer
```

### Postman Setup

1. Create POST request to `/api/v1/agent/chat/stream`
2. Set Body → form-data
3. Add `message` field
4. Send and view SSE stream

---

## 6. Chart Visualization

The API automatically generates and embeds charts in markdown responses when analyzing data. Charts are served as PNG files for reliable rendering across different markdown viewers.

### Chart Generation

Charts are automatically generated when the agent processes data analysis requests. The response includes markdown image links that point to the chart files.

**Example Response with Chart**:

```json
{
  "response": "Here's the PM2.5 trend analysis:\n\n![Generated Chart](http://localhost:8000/api/v1/visualization/charts/PM2-5-Trend-20260111-120000-123456.png)\n\nThe data shows...",
  "session_id": "abc-123",
  "tools_used": ["generate_chart", "get_city_air_quality"]
}
```

### Serving Chart Images

**Endpoint**: `GET /api/v1/visualization/charts/{filename}`

**Purpose**: Serves generated chart PNG files for markdown image rendering.

**Parameters**:

- `filename`: The chart filename (PNG only, path traversal protected)

**Example**:

```bash
curl -O "http://localhost:8000/api/v1/visualization/charts/chart-20260111-120000.png"
```

**Response**: PNG image file with `Content-Type: image/png` and `Content-Disposition: inline`

### Visualization Capabilities

**Endpoint**: `GET /api/v1/visualization/capabilities`

**Purpose**: Get information about supported visualization formats and chart types.

**Response**:

```json
{
  "supported_formats": ["csv", "xlsx", "xls", "pdf"],
  "supported_chart_types": [
    "line",
    "bar",
    "scatter",
    "histogram",
    "box",
    "heatmap",
    "pie",
    "area",
    "violin"
  ],
  "description": "Create dynamic visualizations from CSV, Excel, PDF files or search results"
}
```

### Chart Storage

- Charts are stored in `/app/data/charts/` (configurable via `CHART_STORAGE_DIR`)
- Files are automatically cleaned up (TTL: 1 hour)
- Filenames include timestamp for uniqueness
- Cross-origin support via absolute URLs (configurable via `PUBLIC_BASE_URL`)

### Frontend Integration

**Markdown Rendering**: Charts render automatically in markdown viewers that support images.

**React Example**:

```typescript
// The response already contains markdown with image links
const response = await fetch("/api/v1/agent/chat", {
  method: "POST",
  body: formData,
});

const data = await response.json();

// Render with a markdown component that supports images
<ReactMarkdown>{data.response}</ReactMarkdown>;
```

**Cross-Origin Support**: If your frontend is on a different domain, set `PUBLIC_BASE_URL` environment variable to ensure chart URLs are absolute.

---

## Summary

- **Simple Chat**: Use `/chat` for standard request/response
- **Streaming**: Use `/chat/stream` for real-time updates
- **Performance**: Use Gemini/OpenAI for <3s responses
- **Sessions**: Persist conversation context across requests
- **Files**: Upload documents for analysis
- **Error Handling**: Always handle errors gracefully

For more details, see:

- [Performance Guide](PERFORMANCE_GUIDE.md)
- [Architecture Guide](ARCHITECTURE.md)
