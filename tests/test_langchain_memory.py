"""
Test LangChain memory integration
"""

from src.services.session.langchain_memory import create_session_memory


def test_window_memory():
    """Test window memory keeps last N messages."""
    memory = create_session_memory("test-session-1", use_summarization=False)
    
    # Add 10 messages
    for i in range(10):
        memory.add_user_message(f"User message {i}")
        memory.add_ai_message(f"AI response {i}")
    
    # Check history
    history = memory.get_history()
    assert len(history) <= 40  # Max messages limit
    
    # Verify latest messages are present
    assert "User message 9" in [msg["content"] for msg in history]
    
    memory.clear()
    print("✅ Window memory test passed")


def test_token_count():
    """Test token counting works."""
    memory = create_session_memory("test-session-2", use_summarization=False, max_tokens=500)
    
    # Add messages
    memory.add_user_message("What's the air quality?")
    memory.add_ai_message("The AQI is 42 in London")
    
    # Check token count
    token_count = memory.get_token_count()
    assert token_count is not None
    assert token_count > 0
    
    memory.clear()
    print("✅ Token counting test passed")


def test_conversation_flow():
    """Test realistic conversation flow."""
    session_id = "test-conversation-flow"
    memory = create_session_memory(session_id, max_tokens=2000)
    
    # Simulate air quality conversation
    conversation = [
        ("What's the air quality in London?", "The current AQI in London is 42 (Good). PM2.5: 12 µg/m³."),
        ("How about New York?", "New York has an AQI of 68 (Moderate). PM2.5: 18 µg/m³."),
        ("Which is better?", "London has better air quality with AQI 42 vs New York's 68."),
    ]
    
    for user_msg, ai_msg in conversation:
        memory.add_user_message(user_msg)
        memory.add_ai_message(ai_msg)
    
    # Check history
    history = memory.get_history()
    assert len(history) == 6  # 3 user + 3 AI messages
    
    # Verify order
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"
    
    # Check token tracking
    token_count = memory.get_token_count()
    assert token_count is not None
    assert token_count > 0
    print(f"✅ Conversation flow test passed ({token_count} tokens tracked)")
    
    memory.clear()


def test_memory_clear():
    """Test memory clearing."""
    session_id = "test-clear-session"
    memory = create_session_memory(session_id)
    
    # Add messages
    memory.add_user_message("Test message")
    memory.add_ai_message("Test response")
    
    # Verify messages exist
    history = memory.get_history()
    assert len(history) == 2
    
    # Clear memory
    memory.clear()
    
    # Verify cleared
    history_after = memory.get_history()
    assert len(history_after) == 0
    print("✅ Memory clear test passed")


if __name__ == "__main__":
    print("Running LangChain memory tests...\n")
    test_window_memory()
    test_token_count()
    test_conversation_flow()
    test_memory_clear()
    print("\n🎉 All LangChain memory tests passed!")
