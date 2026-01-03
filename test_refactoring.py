"""
Test script to verify refactored agent service functionality.

Run this script to ensure all modules work correctly:
    python test_refactoring.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def test_imports():
    """Test that all modules can be imported."""
    print("=" * 60)
    print("Testing Imports...")
    print("=" * 60)
    
    try:
        from src.services.agent.cost_tracker import CostTracker
        print("✓ CostTracker imported")
        
        from src.services.agent.tool_executor import ToolExecutor
        print("✓ ToolExecutor imported")
        
        from src.services.providers.base_provider import BaseAIProvider
        print("✓ BaseAIProvider imported")
        
        from src.services.providers.gemini_provider import GeminiProvider
        print("✓ GeminiProvider imported")
        
        from src.services.providers.openai_provider import OpenAIProvider
        print("✓ OpenAIProvider imported")
        
        from src.services.providers.ollama_provider import OllamaProvider
        print("✓ OllamaProvider imported")
        
        from src.services.prompts.system_instructions import (
            get_response_parameters,
            get_system_instruction,
        )
        print("✓ System instructions imported")
        
        from src.services.tool_definitions.gemini_tools import get_all_tools
        print("✓ Gemini tools imported")
        
        from src.services.tool_definitions.openai_tools import get_all_tools
        print("✓ OpenAI tools imported")
        
        from src.utils.api.sanitizer import sanitize_sensitive_data
        print("✓ Sanitizer imported")
        
        from src.services.agent_service import AgentService
        print("✓ AgentService imported")
        
        print("\n✅ All imports successful!\n")
        return True
        
    except Exception as e:
        print(f"\n❌ Import failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_cost_tracker():
    """Test CostTracker functionality."""
    print("=" * 60)
    print("Testing CostTracker...")
    print("=" * 60)
    
    try:
        from src.services.agent.cost_tracker import CostTracker
        
        tracker = CostTracker()
        
        # Test initial state (returns tuple: (bool, Optional[str]))
        within_limits, error_msg = tracker.check_limits()
        assert within_limits == True, f"Should pass limits initially: {error_msg}"
        print("✓ Initial limits check passed")
        
        # Track some usage
        tracker.track_usage(tokens_used=1000, estimated_cost=0.002)
        print("✓ Usage tracked successfully")
        
        # Get status
        status = tracker.get_status()
        assert status["total_tokens"] == 1000, "Token count mismatch"
        assert abs(status["total_cost"] - 0.002) < 0.0001, "Cost mismatch"
        print(f"✓ Status retrieved: {status['total_tokens']} tokens, ${status['total_cost']:.4f}")
        
        # Test reset
        tracker.reset()
        status = tracker.get_status()
        assert status["total_tokens"] == 0, "Reset failed"
        print("✓ Reset successful")
        
        print("\n✅ CostTracker tests passed!\n")
        return True
        
    except Exception as e:
        print(f"\n❌ CostTracker test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_sanitizer():
    """Test sanitizer utility."""
    print("=" * 60)
    print("Testing Sanitizer...")
    print("=" * 60)
    
    try:
        from src.utils.api.sanitizer import sanitize_sensitive_data

        # Test data with sensitive information
        data = {
            "api_key": "sk-12345abcde",
            "token": "ghp_secrettoken",
            "results": [
                {"id": 1, "api_key": "another_key", "value": 100}
            ],
            "safe_data": "This is safe",
        }
        
        # Sanitize (token and api_key are sensitive by default)
        cleaned = sanitize_sensitive_data(data)
        
        # Verify sanitization
        assert cleaned["api_key"] == "[REDACTED]", "api_key not sanitized"
        assert cleaned["token"] == "[REDACTED]", "token not sanitized"
        assert cleaned["results"][0]["api_key"] == "[REDACTED]", "nested api_key not sanitized"
        assert cleaned["safe_data"] == "This is safe", "safe data was modified"
        
        print("✓ Sensitive data sanitized correctly")
        print(f"✓ Original api_key: {data['api_key']}")
        print(f"✓ Cleaned api_key: {cleaned['api_key']}")
        print(f"✓ Original token: {data['token']}")
        print(f"✓ Cleaned token: {cleaned['token']}")
        
        print("\n✅ Sanitizer tests passed!\n")
        return True
        
    except Exception as e:
        print(f"\n❌ Sanitizer test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_system_instructions():
    """Test system instructions module."""
    print("=" * 60)
    print("Testing System Instructions...")
    print("=" * 60)
    
    try:
        from src.services.prompts.system_instructions import (
            get_response_parameters,
            get_system_instruction,
        )

        # Test getting instruction
        instruction = get_system_instruction(style="general")
        assert len(instruction) > 500, "Instruction too short"
        assert "Aeris" in instruction, "Missing Aeris identity"
        print(f"✓ System instruction retrieved ({len(instruction)} chars)")
        
        # Test response parameters
        params = get_response_parameters(style="technical")
        assert "temperature" in params, "Missing temperature"
        assert "top_p" in params, "Missing top_p"
        assert params["temperature"] == 0.4, "Wrong temperature for technical style"
        print(f"✓ Response parameters: temp={params['temperature']}, top_p={params['top_p']}")
        
        # Test custom suffix
        custom_instruction = get_system_instruction(
            style="general",
            custom_suffix="\n\nAdditional context: Test data"
        )
        assert "Test data" in custom_instruction, "Custom suffix not added"
        print("✓ Custom suffix added correctly")
        
        print("\n✅ System instructions tests passed!\n")
        return True
        
    except Exception as e:
        print(f"\n❌ System instructions test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_tool_definitions():
    """Test tool definitions modules."""
    print("=" * 60)
    print("Testing Tool Definitions...")
    print("=" * 60)
    
    try:
        from src.services.tool_definitions.gemini_tools import get_all_tools as get_gemini_tools
        from src.services.tool_definitions.openai_tools import get_all_tools as get_openai_tools

        # Test Gemini tools
        gemini_tools = get_gemini_tools()
        assert len(gemini_tools) > 0, "No Gemini tools found"
        print(f"✓ Gemini tools loaded: {len(gemini_tools)} tools")
        
        # Test OpenAI tools
        openai_tools = get_openai_tools()
        assert len(openai_tools) > 0, "No OpenAI tools found"
        print(f"✓ OpenAI tools loaded: {len(openai_tools)} tools")
        
        # Verify tool structure
        first_tool = openai_tools[0]
        assert "type" in first_tool, "Missing type field"
        assert first_tool["type"] == "function", "Wrong type"
        assert "function" in first_tool, "Missing function field"
        print("✓ Tool structure valid")
        
        print("\n✅ Tool definitions tests passed!\n")
        return True
        
    except Exception as e:
        print(f"\n❌ Tool definitions test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_agent_service_init():
    """Test AgentService initialization."""
    print("=" * 60)
    print("Testing AgentService Initialization...")
    print("=" * 60)
    
    try:
        from src.services.agent_service import AgentService

        # Try to initialize
        agent = AgentService()
        print("✓ AgentService initialized")
        
        # Check components
        assert agent.cost_tracker is not None, "CostTracker not initialized"
        print("✓ CostTracker present")
        
        assert agent.tool_executor is not None, "ToolExecutor not initialized"
        print("✓ ToolExecutor present")
        
        assert agent.provider is not None, "Provider not initialized"
        print(f"✓ Provider initialized: {type(agent.provider).__name__}")
        
        # Check services
        assert agent.waqi is not None, "WAQI service missing"
        assert agent.airqo is not None, "AirQo service missing"
        assert agent.weather is not None, "Weather service missing"
        print("✓ All services initialized")
        
        # Test appreciation detection
        is_appreciation = agent._is_appreciation_message("thank you")
        assert is_appreciation == True, "Failed to detect appreciation"
        print("✓ Appreciation detection works")
        
        is_not_appreciation = agent._is_appreciation_message("What is the air quality?")
        assert is_not_appreciation == False, "False positive appreciation detection"
        print("✓ Non-appreciation correctly identified")
        
        # Test cache key generation
        cache_key = agent._generate_cache_key("test message", [])
        assert len(cache_key) == 32, "Cache key wrong length (should be MD5)"
        print(f"✓ Cache key generated: {cache_key[:16]}...")
        
        print("\n✅ AgentService initialization tests passed!\n")
        return True
        
    except Exception as e:
        print(f"\n❌ AgentService initialization test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


async def test_appreciation_message():
    """Test appreciation message handling."""
    print("=" * 60)
    print("Testing Appreciation Message Handling...")
    print("=" * 60)
    
    try:
        from src.services.agent_service import AgentService
        
        agent = AgentService()
        
        # Test appreciation message (should not call AI)
        response = await agent.process_message("thank you")
        
        assert "response" in response, "Missing response field"
        assert response["tokens_used"] == 0, "Should use 0 tokens for appreciation"
        assert response["cost_estimate"] == 0.0, "Should cost $0 for appreciation"
        assert "welcome" in response["response"].lower(), "Wrong appreciation response"
        
        print(f"✓ Response: {response['response']}")
        print(f"✓ Tokens: {response['tokens_used']}")
        print(f"✓ Cost: ${response['cost_estimate']}")
        
        print("\n✅ Appreciation message handling tests passed!\n")
        return True
        
    except Exception as e:
        print(f"\n❌ Appreciation message test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("REFACTORING VERIFICATION TEST SUITE")
    print("=" * 60 + "\n")
    
    results = []
    
    # Run synchronous tests
    results.append(("Imports", test_imports()))
    results.append(("CostTracker", test_cost_tracker()))
    results.append(("Sanitizer", test_sanitizer()))
    results.append(("System Instructions", test_system_instructions()))
    results.append(("Tool Definitions", test_tool_definitions()))
    results.append(("AgentService Init", test_agent_service_init()))
    
    # Run async tests
    results.append(("Appreciation Messages", await test_appreciation_message()))
    
    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print("\n" + "=" * 60)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60 + "\n")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Refactoring successful!\n")
        return True
    else:
        print(f"⚠️  {total - passed} test(s) failed. Please review errors above.\n")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
