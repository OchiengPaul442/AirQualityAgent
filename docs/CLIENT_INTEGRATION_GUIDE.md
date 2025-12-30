# Client-Side Integration Guide

## 🎯 How to Integrate Client-Side Session Management

This guide shows how to implement ChatGPT-style conversations with client-side history management for maximum cost efficiency.

---

## 📱 Implementation Examples

### **JavaScript/React Example**

```javascript
// ConversationManager.js
class ConversationManager {
  constructor(apiBaseUrl) {
    this.apiBaseUrl = apiBaseUrl;
    this.history = [];
    this.sessionId = this.generateSessionId();
  }

  generateSessionId() {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  async sendMessage(message, saveToDb = false) {
    // Add user message to history
    this.history.push({
      role: "user",
      content: message,
    });

    try {
      const response = await fetch(`${this.apiBaseUrl}/api/v1/agent/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: message,
          session_id: this.sessionId,
          history: this.history.slice(0, -1), // Send all except current message
          save_to_db: saveToDb,
        }),
      });

      const data = await response.json();

      // Add assistant response to history
      this.history.push({
        role: "assistant",
        content: data.response,
      });

      return {
        response: data.response,
        tokensUsed: data.tokens_used,
        cached: data.cached,
        toolsUsed: data.tools_used,
      };
    } catch (error) {
      console.error("Error sending message:", error);
      throw error;
    }
  }

  clearHistory() {
    this.history = [];
    this.sessionId = this.generateSessionId();
  }

  getHistory() {
    return [...this.history];
  }

  saveConversation() {
    // Save to local storage for persistence
    localStorage.setItem(
      `conversation_${this.sessionId}`,
      JSON.stringify({
        sessionId: this.sessionId,
        history: this.history,
        timestamp: Date.now(),
      })
    );
  }

  loadConversation(sessionId) {
    const saved = localStorage.getItem(`conversation_${sessionId}`);
    if (saved) {
      const data = JSON.parse(saved);
      this.sessionId = data.sessionId;
      this.history = data.history;
      return true;
    }
    return false;
  }
}

// Usage in React Component
function ChatComponent() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [manager] = useState(
    () => new ConversationManager("http://localhost:8000")
  );
  const [stats, setStats] = useState({ totalTokens: 0, cacheHits: 0 });

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage = input;
    setInput("");

    // Show user message immediately
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);

    try {
      const result = await manager.sendMessage(userMessage, false); // Don't save by default

      // Show assistant response
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: result.response,
        },
      ]);

      // Update stats
      setStats((prev) => ({
        totalTokens: prev.totalTokens + result.tokensUsed,
        cacheHits: prev.cacheHits + (result.cached ? 1 : 0),
      }));
    } catch (error) {
      console.error("Failed to send message:", error);
    }
  };

  const handleSaveConversation = async () => {
    // Save locally first
    manager.saveConversation();

    // Optionally save last message to database
    if (manager.history.length > 0) {
      const lastMessage = manager.history[manager.history.length - 1];
      await manager.sendMessage(lastMessage.content, true); // save_to_db=true
    }
  };

  const handleClearChat = () => {
    manager.clearHistory();
    setMessages([]);
    setStats({ totalTokens: 0, cacheHits: 0 });
  };

  return (
    <div>
      <div className="chat-container">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            {msg.content}
          </div>
        ))}
      </div>

      <div className="stats">
        <span>Tokens used: {stats.totalTokens}</span>
        <span>Cache hits: {stats.cacheHits}</span>
        <span>Cost saved: ~${(stats.cacheHits * 0.002).toFixed(3)}</span>
      </div>

      <div className="input-area">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === "Enter" && handleSend()}
          placeholder="Ask about air quality..."
        />
        <button onClick={handleSend}>Send</button>
        <button onClick={handleSaveConversation}>Save</button>
        <button onClick={handleClearChat}>Clear</button>
      </div>
    </div>
  );
}
```

---

### **Python Client Example**

```python
import requests
import json
from datetime import datetime
from typing import List, Dict, Optional

class AirQualityClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.history: List[Dict[str, str]] = []
        self.session_id = self._generate_session_id()
        self.stats = {"total_tokens": 0, "cache_hits": 0, "requests": 0}

    def _generate_session_id(self) -> str:
        from uuid import uuid4
        return f"session_{uuid4()}"

    def send_message(self, message: str, save_to_db: bool = False) -> Dict:
        """
        Send a message to the AI agent

        Args:
            message: User's message
            save_to_db: Whether to save this conversation to database

        Returns:
            Response data including answer, tokens used, cached status
        """
        # Add user message to local history
        self.history.append({
            "role": "user",
            "content": message
        })

        try:
            response = requests.post(
                f"{self.base_url}/api/v1/agent/chat",
                json={
                    "message": message,
                    "session_id": self.session_id,
                    "history": self.history[:-1],  # Send all except current
                    "save_to_db": save_to_db
                },
                timeout=60
            )
            response.raise_for_status()
            data = response.json()

            # Add assistant response to local history
            self.history.append({
                "role": "assistant",
                "content": data["response"]
            })

            # Update stats
            self.stats["total_tokens"] += data.get("tokens_used", 0)
            self.stats["cache_hits"] += 1 if data.get("cached") else 0
            self.stats["requests"] += 1

            return {
                "response": data["response"],
                "tokens_used": data.get("tokens_used", 0),
                "cached": data.get("cached", False),
                "tools_used": data.get("tools_used", [])
            }

        except requests.exceptions.RequestException as e:
            print(f"Error sending message: {e}")
            raise

    def clear_history(self):
        """Clear conversation history and start fresh"""
        self.history = []
        self.session_id = self._generate_session_id()

    def save_locally(self, filename: Optional[str] = None):
        """Save conversation to JSON file"""
        if filename is None:
            filename = f"conversation_{self.session_id}.json"

        with open(filename, 'w') as f:
            json.dump({
                "session_id": self.session_id,
                "history": self.history,
                "stats": self.stats,
                "timestamp": datetime.now().isoformat()
            }, f, indent=2)

    def load_from_file(self, filename: str):
        """Load conversation from JSON file"""
        with open(filename, 'r') as f:
            data = json.load(f)
            self.session_id = data["session_id"]
            self.history = data["history"]
            self.stats = data.get("stats", {"total_tokens": 0, "cache_hits": 0, "requests": 0})

    def get_stats(self) -> Dict:
        """Get conversation statistics"""
        return {
            **self.stats,
            "cache_hit_rate": self.stats["cache_hits"] / max(self.stats["requests"], 1),
            "estimated_cost": self.stats["total_tokens"] * 0.000002,  # Rough estimate
            "estimated_savings": self.stats["cache_hits"] * 0.002
        }


# Example usage
if __name__ == "__main__":
    client = AirQualityClient()

    print("🌍 Air Quality AI Agent")
    print("=" * 50)

    while True:
        user_input = input("\nYou: ").strip()

        if not user_input:
            continue

        if user_input.lower() in ['quit', 'exit']:
            # Ask if user wants to save before exiting
            save = input("Save conversation? (y/n): ").strip().lower()
            if save == 'y':
                client.save_locally()
                print(f"✅ Conversation saved!")

            stats = client.get_stats()
            print(f"\n📊 Session Stats:")
            print(f"  Requests: {stats['requests']}")
            print(f"  Tokens: {stats['total_tokens']}")
            print(f"  Cache hits: {stats['cache_hits']}")
            print(f"  Cost: ~${stats['estimated_cost']:.4f}")
            print(f"  Saved: ~${stats['estimated_savings']:.4f}")
            break

        if user_input.lower() == 'clear':
            client.clear_history()
            print("✅ Conversation cleared!")
            continue

        if user_input.lower() == 'save':
            save_db = input("Save to database? (y/n): ").strip().lower() == 'y'
            if save_db:
                # Resend last exchange with save flag
                result = client.send_message(client.history[-2]["content"], save_to_db=True)
            client.save_locally()
            print("✅ Conversation saved!")
            continue

        try:
            result = client.send_message(user_input, save_to_db=False)

            print(f"\n🤖 Agent: {result['response']}")

            if result['cached']:
                print("⚡ (cached response)")
            if result['tools_used']:
                print(f"🔧 Tools used: {', '.join(result['tools_used'])}")

            print(f"📊 Tokens: {result['tokens_used']}")

        except Exception as e:
            print(f"❌ Error: {e}")
```

---

### **Mobile App (Flutter) Example**

```dart
// conversation_manager.dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class Message {
  final String role;
  final String content;

  Message({required this.role, required this.content});

  Map<String, dynamic> toJson() => {
    'role': role,
    'content': content,
  };

  factory Message.fromJson(Map<String, dynamic> json) => Message(
    role: json['role'],
    content: json['content'],
  );
}

class ConversationManager {
  final String baseUrl;
  List<Message> history = [];
  String sessionId;
  Map<String, dynamic> stats = {
    'totalTokens': 0,
    'cacheHits': 0,
    'requests': 0,
  };

  ConversationManager(this.baseUrl) : sessionId = _generateSessionId();

  static String _generateSessionId() {
    return 'session_${DateTime.now().millisecondsSinceEpoch}';
  }

  Future<Map<String, dynamic>> sendMessage(String message, {bool saveToDb = false}) async {
    // Add user message to history
    history.add(Message(role: 'user', content: message));

    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/v1/agent/chat'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'message': message,
          'session_id': sessionId,
          'history': history.sublist(0, history.length - 1).map((m) => m.toJson()).toList(),
          'save_to_db': saveToDb,
        }),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);

        // Add assistant response to history
        history.add(Message(role: 'assistant', content: data['response']));

        // Update stats
        stats['totalTokens'] += data['tokens_used'] ?? 0;
        stats['cacheHits'] += data['cached'] == true ? 1 : 0;
        stats['requests'] += 1;

        return {
          'response': data['response'],
          'tokensUsed': data['tokens_used'] ?? 0,
          'cached': data['cached'] ?? false,
          'toolsUsed': data['tools_used'] ?? [],
        };
      } else {
        throw Exception('Failed to send message: ${response.statusCode}');
      }
    } catch (e) {
      print('Error sending message: $e');
      rethrow;
    }
  }

  void clearHistory() {
    history.clear();
    sessionId = _generateSessionId();
    stats = {'totalTokens': 0, 'cacheHits': 0, 'requests': 0};
  }

  Future<void> saveLocally() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('conversation_$sessionId', jsonEncode({
      'sessionId': sessionId,
      'history': history.map((m) => m.toJson()).toList(),
      'stats': stats,
      'timestamp': DateTime.now().toIso8601String(),
    }));
  }

  Future<bool> loadFromLocal(String sessionId) async {
    final prefs = await SharedPreferences.getInstance();
    final String? saved = prefs.getString('conversation_$sessionId');

    if (saved != null) {
      final data = jsonDecode(saved);
      this.sessionId = data['sessionId'];
      history = (data['history'] as List).map((m) => Message.fromJson(m)).toList();
      stats = data['stats'];
      return true;
    }
    return false;
  }

  Map<String, dynamic> getStats() {
    final cacheHitRate = stats['requests'] > 0
        ? stats['cacheHits'] / stats['requests']
        : 0.0;

    return {
      ...stats,
      'cacheHitRate': cacheHitRate,
      'estimatedCost': stats['totalTokens'] * 0.000002,
      'estimatedSavings': stats['cacheHits'] * 0.002,
    };
  }
}
```

---

## 🎯 Key Points

### **1. Always Send History**

```javascript
{
    "message": "Current message",
    "history": [
        {"role": "user", "content": "Previous question"},
        {"role": "assistant", "content": "Previous answer"}
    ]
}
```

### **2. Don't Save by Default**

```javascript
{
    "save_to_db": false  // ← Default behavior for cost savings
}
```

### **3. Save Important Conversations**

```javascript
// Only when user explicitly saves
{
    "save_to_db": true  // ← User clicked "Save" button
}
```

### **4. Track Usage**

```javascript
const stats = {
  totalTokens: response.tokens_used,
  cached: response.cached,
  costSavings: cacheHits * 0.002,
};
```

---

## 💡 Best Practices

### ✅ DO:

- Store history client-side (localStorage, SharedPreferences, AsyncStorage)
- Send full history with each request
- Clear history when user starts new conversation
- Show token usage to users
- Implement "Save Conversation" as explicit action
- Cache responses client-side for offline access

### ❌ DON'T:

- Save every message to database by default
- Send history longer than ~20 messages (truncate older ones)
- Store sensitive information in conversation history
- Make users log in just to chat
- Block UI while sending (use optimistic updates)

---

## 📊 Expected Results

With proper client-side implementation:

- **90% reduction** in database storage costs
- **Instant loading** - no database queries for history
- **Better UX** - conversations persist across sessions
- **Privacy** - data stays on device unless saved
- **Scalability** - stateless backend can handle millions

---

**Last Updated:** December 30, 2025
