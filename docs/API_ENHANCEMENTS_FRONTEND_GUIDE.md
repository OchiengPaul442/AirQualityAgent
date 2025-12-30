# Air Quality Agent API: Recent Enhancements & Frontend Integration Guide

## Overview

This document outlines the recent enhancements to the Air Quality Agent API, focusing on production-ready session management, cost optimization, and intelligent error handling. These changes simplify frontend integration while improving system reliability and cost-effectiveness.

## Key Enhancements

### 1. Simplified Session Management

**Before:** Complex session handling with manual history passing and unclear lifecycle management.

**After:** Automatic session management with simple, RESTful endpoints.

#### New Session Endpoints

```http
GET /sessions
GET /sessions/{session_id}
DELETE /sessions/{session_id}
GET /sessions/{session_id}/messages
```

#### Automatic Behavior

- Sessions are created automatically when you send a chat message
- All messages are automatically saved to the database
- No manual session creation required
- Clean deletion with CASCADE DELETE removes all associated messages

### 2. Cost Optimization Features

**Context Limiting:** Chat endpoint now uses only the last 20 messages for AI context, reducing token costs while maintaining conversation continuity.

**Response Caching:** Frequently requested air quality data is cached for 5 minutes to avoid redundant API calls.

**Token Tracking:** Responses include approximate token usage for cost monitoring.

### 3. Intelligent Air Quality API

**Before:** Mixed successful and failed responses in a single payload.

**After:** Clean separation - only successful data is returned, or 404 with error details.

#### Response Patterns

**Success (200):**

```json
{
  "waqi": {
    /* WAQI data */
  },
  "airqo": {
    /* AirQo data */
  }
}
```

**Partial Success (200):**

```json
{
  "waqi": {
    /* WAQI data */
  }
  // AirQo failed, but WAQI succeeded
}
```

**Failure (404):**

```json
{
  "message": "No air quality data found for Kampala",
  "errors": {
    "waqi": "WAQI API error: timeout",
    "airqo": "No data available"
  },
  "suggestion": "Try a different city name or check if the location is covered by our data sources"
}
```

## Frontend Integration Guide

### Basic Chat Implementation

#### Starting a New Conversation

```javascript
// React/Vue/Angular - Start new chat
const startNewChat = async (message) => {
  const response = await fetch("/agent/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: message,
      // No session_id needed - server creates one
    }),
  });

  const data = await response.json();
  // data.session_id is now available for future messages
  return data;
};
```

#### Continuing a Conversation

```javascript
// React/Vue/Angular - Continue existing chat
const continueChat = async (message, sessionId) => {
  const response = await fetch("/agent/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: message,
      session_id: sessionId, // Continue this session
    }),
  });

  return await response.json();
};
```

#### Closing a Conversation

```javascript
// React/Vue/Angular - Clean up when user closes chat
const closeChat = async (sessionId) => {
  await fetch(`/sessions/${sessionId}`, {
    method: "DELETE",
  });
  // Session and all messages are deleted
};
```

### Session Management UI

#### Listing User Sessions

```javascript
// React/Vue/Angular - Show user's chat history
const loadChatHistory = async () => {
  const response = await fetch("/sessions?limit=20");
  const sessions = await response.json();

  // sessions = [
  //   {
  //     "id": "abc-123",
  //     "created_at": "2024-01-15T10:30:00Z",
  //     "message_count": 15,
  //     "updated_at": "2024-01-15T10:45:00Z"
  //   }
  // ]
  return sessions;
};
```

#### Loading Session Messages

```javascript
// React/Vue/Angular - Load full conversation
const loadConversation = async (sessionId) => {
  const response = await fetch(`/sessions/${sessionId}`);
  const session = await response.json();

  // session.messages contains full conversation history
  return session.messages;
};
```

### Air Quality Data Handling

#### Robust Error Handling

```javascript
// React/Vue/Angular - Query air quality with proper error handling
const getAirQuality = async (city) => {
  try {
    const response = await fetch("/air-quality/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ city: city }),
    });

    if (response.ok) {
      const data = await response.json();
      // data contains only successful API responses
      // data.waqi or data.airqo (or both)
      return { success: true, data };
    } else if (response.status === 404) {
      const error = await response.json();
      // Show user-friendly error message
      return {
        success: false,
        message: error.message,
        suggestion: error.suggestion,
      };
    } else {
      throw new Error(`HTTP ${response.status}`);
    }
  } catch (error) {
    return {
      success: false,
      message: "Network error - please try again",
    };
  }
};
```

### Complete React Component Example

```jsx
import { useState, useEffect } from "react";

function AirQualityChat() {
  const [messages, setMessages] = useState([]);
  const [currentMessage, setCurrentMessage] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  // Load existing sessions on mount
  useEffect(() => {
    loadChatHistory();
  }, []);

  const loadChatHistory = async () => {
    try {
      const response = await fetch("/sessions?limit=10");
      const sessions = await response.json();
      // Display sessions in UI for user selection
    } catch (error) {
      console.error("Failed to load chat history:", error);
    }
  };

  const sendMessage = async () => {
    if (!currentMessage.trim()) return;

    setIsLoading(true);
    try {
      const response = await fetch("/agent/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: currentMessage,
          session_id: sessionId, // null for new session
        }),
      });

      const data = await response.json();

      // Update UI with new messages
      setMessages((prev) => [
        ...prev,
        {
          role: "user",
          content: currentMessage,
          timestamp: new Date(),
        },
        {
          role: "assistant",
          content: data.response,
          timestamp: new Date(),
        },
      ]);

      // Store session ID for future messages
      setSessionId(data.session_id);
      setCurrentMessage("");
    } catch (error) {
      console.error("Chat error:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const closeSession = async () => {
    if (sessionId) {
      try {
        await fetch(`/sessions/${sessionId}`, { method: "DELETE" });
        setSessionId(null);
        setMessages([]);
      } catch (error) {
        console.error("Failed to close session:", error);
      }
    }
  };

  return (
    <div className="chat-container">
      <div className="messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            {msg.content}
          </div>
        ))}
      </div>

      <div className="input-area">
        <input
          value={currentMessage}
          onChange={(e) => setCurrentMessage(e.target.value)}
          onKeyPress={(e) => e.key === "Enter" && sendMessage()}
          placeholder="Ask about air quality..."
          disabled={isLoading}
        />
        <button onClick={sendMessage} disabled={isLoading}>
          {isLoading ? "Sending..." : "Send"}
        </button>
        {sessionId && (
          <button onClick={closeSession} className="close-btn">
            Close Chat
          </button>
        )}
      </div>
    </div>
  );
}

export default AirQualityChat;
```

## API Response Models

### ChatRequest (Simplified)

```typescript
interface ChatRequest {
  message: string; // Required: The user's message
  session_id?: string; // Optional: Continue existing session
}
```

### ChatResponse (Enhanced)

```typescript
interface ChatResponse {
  response: string; // AI assistant's response
  session_id: string; // Session ID for this conversation
  tools_used?: string[]; // APIs/tools called
  tokens_used?: number; // Approximate token count
  cached: boolean; // Whether response was cached
  message_count?: number; // Total messages in session
}
```

### Session Object

```typescript
interface Session {
  id: string; // Unique session identifier
  created_at: string; // ISO timestamp
  updated_at: string; // ISO timestamp
  message_count: number; // Total messages
  messages?: Message[]; // Full message history (when requested)
}
```

## Best Practices

### 1. Session Lifecycle Management

- **Create:** Sessions are created automatically on first message
- **Continue:** Always include `session_id` in subsequent requests
- **Close:** Call `DELETE /sessions/{session_id}` when user closes chat
- **List:** Use `GET /sessions` to show chat history

### 2. Error Handling

- **Air Quality:** Check HTTP status - 200 means success, 404 means no data
- **Chat:** Standard HTTP error codes with descriptive messages
- **Rate Limiting:** Handle 429 responses with retry logic

### 3. Performance Optimization

- **Caching:** Air quality responses are cached for 5 minutes
- **Context Limiting:** Only last 20 messages sent to AI
- **Rate Limiting:** 20 requests per minute per IP

### 4. Cost Monitoring

- Track `tokens_used` in responses
- Monitor `cached` flag to understand cache hit rates
- Use `message_count` to track conversation length

## Migration from Previous Version

### What Changed

1. **ChatRequest** no longer requires `history` parameter
2. **Air quality responses** no longer include error fields mixed with data
3. **Session management** is now automatic
4. **New endpoints** for session CRUD operations

### Migration Steps

1. Remove manual history management from frontend
2. Update air quality error handling to check HTTP status
3. Add session cleanup calls when users close chats
4. Remove any manual session creation logic

### Backward Compatibility

The API maintains backward compatibility for the core chat functionality. Existing integrations will continue to work, but new features provide better performance and reliability.

## Testing the Enhanced API

### Using curl

```bash
# Start a new conversation
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the air quality in New York?"}'

# Continue the conversation
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What about Los Angeles?", "session_id": "abc-123"}'

# List all sessions
curl http://localhost:8000/sessions

# Delete a session
curl -X DELETE http://localhost:8000/sessions/abc-123

# Query air quality
curl -X POST http://localhost:8000/air-quality/query \
  -H "Content-Type: application/json" \
  -d '{"city": "London"}'
```

This enhanced API provides a robust, cost-effective foundation for building air quality chat applications with excellent user experience and simplified frontend integration.</content>
<parameter name="filePath">d:\projects\agents\AirQualityAgent\docs\API_ENHANCEMENTS_FRONTEND_GUIDE.md
