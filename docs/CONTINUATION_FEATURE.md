# Response Continuation Feature

## Overview

The Air Quality Agent now intelligently detects when responses are truncated and provides a seamless continuation mechanism for incomplete responses. This feature ensures users can get complete information without losing context.

## How It Works

### Backend Implementation

The system tracks response truncation at two levels:

1. **Provider-Level Truncation**: When the AI provider (OpenAI, Gemini, etc.) hits token limits
2. **Internal Truncation**: When responses exceed the configured `max_response_length` (default: 6000 chars)

### Response Fields

The `ChatResponse` model now includes three new fields:

```python
{
  "response": "...",  # The response text
  "session_id": "...",
  "requires_continuation": true,  # Whether continuation is needed
  "finish_reason": "length",       # Why generation stopped
  "truncated": true,               # Whether response was truncated
  // ... other fields
}
```

#### `requires_continuation` (boolean)

- `true`: Response was truncated and can be continued
- `false`: Response is complete
- Frontend should show a "Continue" button when `true`

#### `finish_reason` (string | null)

- `"stop"`: Generation completed naturally (response is complete)
- `"length"`: Truncated due to max_tokens limit
- `"content_filter"`: Stopped due to content filtering
- `null`: Not applicable (cached responses, errors, etc.)

#### `truncated` (boolean)

- `true`: Response was shortened (either by provider or internally)
- `false`: Response was not truncated

## Frontend Implementation

### Basic Implementation

```typescript
interface ChatResponse {
  response: string;
  session_id: string;
  requires_continuation?: boolean;
  finish_reason?: string | null;
  truncated?: boolean;
  // ... other fields
}

// Render the response
function renderMessage(response: ChatResponse) {
  const messageDiv = document.createElement("div");
  messageDiv.innerHTML = response.response; // Markdown rendered

  // Show continuation button if needed
  if (response.requires_continuation) {
    const continueBtn = document.createElement("button");
    continueBtn.textContent = "Continue ▶";
    continueBtn.onclick = () => continueResponse(response.session_id);
    messageDiv.appendChild(continueBtn);
  }

  return messageDiv;
}
```

### Continuation Request

When the user clicks "Continue", send a follow-up message:

```typescript
async function continueResponse(sessionId: string) {
  const response = await fetch("/api/v1/agent/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: "Please continue", // Simple continuation prompt
      session_id: sessionId, // CRITICAL: Include session ID
    }),
  });

  const data = await response.json();
  return data;
}
```

### React Example

```tsx
import React, { useState } from "react";
import ReactMarkdown from "react-markdown";

interface Message {
  role: "user" | "assistant";
  content: string;
  requires_continuation?: boolean;
  session_id?: string;
}

function ChatMessage({
  message,
  onContinue,
}: {
  message: Message;
  onContinue: () => void;
}) {
  return (
    <div className={`message ${message.role}`}>
      <ReactMarkdown>{message.content}</ReactMarkdown>

      {message.requires_continuation && (
        <button onClick={onContinue} className="continue-button">
          📝 Continue Response
        </button>
      )}
    </div>
  );
}

function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);

  const sendMessage = async (text: string) => {
    const response = await fetch("/api/v1/agent/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        session_id: sessionId,
      }),
    });

    const data = await response.json();
    setSessionId(data.session_id);

    setMessages([
      ...messages,
      {
        role: "assistant",
        content: data.response,
        requires_continuation: data.requires_continuation,
        session_id: data.session_id,
      },
    ]);
  };

  const handleContinue = () => {
    sendMessage("Please continue");
  };

  return (
    <div className="chat">
      {messages.map((msg, idx) => (
        <ChatMessage key={idx} message={msg} onContinue={handleContinue} />
      ))}
    </div>
  );
}
```

### Vue.js Example

```vue
<template>
  <div class="chat-container">
    <div
      v-for="(message, index) in messages"
      :key="index"
      :class="['message', message.role]"
    >
      <div v-html="renderMarkdown(message.content)"></div>

      <button
        v-if="message.requires_continuation"
        @click="continueResponse"
        class="continue-btn"
      >
        📝 Continue Response
      </button>
    </div>
  </div>
</template>

<script>
import { marked } from "marked";

export default {
  data() {
    return {
      messages: [],
      sessionId: null,
    };
  },
  methods: {
    renderMarkdown(text) {
      return marked(text);
    },

    async sendMessage(text) {
      const response = await fetch("/api/v1/agent/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          session_id: this.sessionId,
        }),
      });

      const data = await response.json();
      this.sessionId = data.session_id;

      this.messages.push({
        role: "assistant",
        content: data.response,
        requires_continuation: data.requires_continuation,
      });
    },

    continueResponse() {
      this.sendMessage("Please continue");
    },
  },
};
</script>
```

## Best Practices

### 1. **Session Management**

Always maintain the session ID across continuation requests:

```typescript
// ❌ Bad: Loses context
fetch("/api/v1/agent/chat", {
  body: JSON.stringify({ message: "Please continue" }),
});

// ✅ Good: Maintains context
fetch("/api/v1/agent/chat", {
  body: JSON.stringify({
    message: "Please continue",
    session_id: currentSessionId, // Include session ID
  }),
});
```

### 2. **User Experience**

- Show a clear "Continue" button when `requires_continuation` is true
- Disable the button during continuation to prevent duplicate requests
- Consider auto-continuing after a delay (optional)

```typescript
function renderContinueButton(sessionId: string) {
  const btn = document.createElement("button");
  btn.textContent = "📝 Continue Response";
  btn.disabled = false;

  btn.onclick = async () => {
    btn.disabled = true; // Prevent duplicate clicks
    btn.textContent = "Continuing...";

    try {
      await continueResponse(sessionId);
    } finally {
      btn.disabled = false;
      btn.textContent = "📝 Continue Response";
    }
  };

  return btn;
}
```

### 3. **Visual Indicators**

Provide clear visual feedback:

```css
.message.truncated {
  border-bottom: 2px dashed #ffa500;
  padding-bottom: 1rem;
}

.continue-button {
  margin-top: 1rem;
  padding: 0.5rem 1rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  transition: transform 0.2s;
}

.continue-button:hover {
  transform: translateY(-2px);
}

.continue-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
```

### 4. **Alternative Approaches**

Instead of just "Continue", offer users multiple options:

```typescript
function renderTruncationOptions(sessionId: string) {
  const container = document.createElement("div");
  container.className = "truncation-options";

  container.innerHTML = `
    <p class="truncation-notice">
      📝 This response was truncated. What would you like to do?
    </p>
    <div class="option-buttons">
      <button onclick="continueResponse('${sessionId}')">
        ▶ Continue
      </button>
      <button onclick="summarize('${sessionId}')">
        📋 Get Summary
      </button>
      <button onclick="askSpecific()">
        🎯 Ask Specific Question
      </button>
    </div>
  `;

  return container;
}
```

## API Contract

### Request

```json
POST /api/v1/agent/chat

{
  "message": "Please continue",
  "session_id": "uuid-of-current-session"
}
```

### Response

```json
{
  "response": "...",
  "session_id": "same-uuid",
  "requires_continuation": false, // May still be true if continuation is also long
  "finish_reason": "stop",
  "truncated": false,
  "tools_used": [],
  "tokens_used": 1234,
  "cached": false,
  "message_count": 5
}
```

## Testing

### Test Cases

1. **Normal Response (No Truncation)**

```typescript
const response = await chat("What is PM2.5?");
expect(response.requires_continuation).toBe(false);
expect(response.finish_reason).toBe("stop");
expect(response.truncated).toBe(false);
```

2. **Truncated Response**

```typescript
const response = await chat(
  "Explain air quality in great detail with all pollutants, health effects, global statistics, and recommendations."
);
expect(response.requires_continuation).toBe(true);
expect(response.finish_reason).toBe("length");
expect(response.truncated).toBe(true);
expect(response.response).toContain("Continue");
```

3. **Continuation Request**

```typescript
const initial = await chat("Long detailed question...");
expect(initial.requires_continuation).toBe(true);

const continuation = await chat("Please continue", initial.session_id);
// Continuation should pick up where it left off
expect(continuation.response).not.toBe(initial.response);
```

## Troubleshooting

### Issue: Continuation loses context

**Solution**: Ensure session_id is included in continuation request

### Issue: Continuation just repeats the same content

**Solution**: Check that conversation history is properly maintained in the database

### Issue: Multiple truncations in a row

**Solution**: Encourage users to ask more focused questions or request summaries

## Configuration

Backend configuration in [settings.py](d:\projects\agents\AirQualityAgent\shared\config\settings.py):

```python
# Maximum response length before internal truncation
max_response_length = 6000  # characters

# AI provider token limits (set in environment)
AI_MAX_TOKENS = 2048  # Default max tokens per response
```

To adjust truncation behavior, modify `max_response_length` in `AgentService.__init__()`:

```python
self.max_response_length = 8000  # Increase for longer responses
```

## Migration Guide

If you have an existing frontend, follow these steps:

1. **Update API Client** - Handle new response fields
2. **Add UI Components** - Create continuation button
3. **Test Thoroughly** - Verify session management works
4. **Deploy Backend First** - Ensure backward compatibility
5. **Update Frontend** - Roll out new UI features

## Related Documentation

- [API Guide](./API_GUIDE.md) - Complete API reference
- [Architecture](./ARCHITECTURE.md) - System design overview
- [Developer Guide](./DEVELOPER_GUIDE.md) - Development setup

## Support

For issues or questions:

- Check logs for `finish_reason` and `truncated` values
- Verify session IDs are maintained correctly
- Ensure database connection is stable (conversation history required)
