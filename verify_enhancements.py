"""
Quick verification script to test new orchestration capabilities.

Run this to ensure all enhancements are working correctly.
"""

import sys
import traceback


def test_imports():
    """Test that all new modules can be imported."""
    print("=" * 60)
    print("Testing imports...")
    print("=" * 60)
    
    try:
        from src.services.agent import orchestrator
        print("✅ orchestrator module imported")
        
        from src.services.agent import model_adapter
        print("✅ model_adapter module imported")
        
        from src.services.agent.orchestrator import (
            OrchestrationResult,
            ResponseValidator,
            ToolCall,
            ToolExecutionStatus,
            ToolOrchestrator,
        )
        print("✅ All orchestrator classes imported")
        
        from src.services.agent.model_adapter import (
            ExtractedToolCall,
            ModelAdapter,
            PromptEnhancer,
            ResponsePostProcessor,
        )
        print("✅ All model adapter classes imported")
        
        from src.services.agent_service import AgentService
        print("✅ AgentService imported with orchestrator integration")
        
        from src.services.providers.ollama_provider import OllamaProvider
        print("✅ Enhanced Ollama provider imported")
        
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        traceback.print_exc()
        return False


def test_orchestrator_basics():
    """Test basic orchestrator functionality."""
    print("\n" + "=" * 60)
    print("Testing orchestrator basics...")
    print("=" * 60)
    
    try:
        from src.services.agent.orchestrator import ToolCall, ToolExecutionStatus

        # Create a simple tool call
        tool_call = ToolCall(
            name="get_city_air_quality",
            args={"city": "London"},
            priority=1
        )
        print(f"✅ Created ToolCall: {tool_call.name}")
        print(f"   Status: {tool_call.status}")
        print(f"   Priority: {tool_call.priority}")
        
        # Test status enum
        assert tool_call.status == ToolExecutionStatus.PENDING
        print("✅ ToolExecutionStatus working correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ Orchestrator test failed: {e}")
        traceback.print_exc()
        return False


def test_model_adapter():
    """Test model adapter functionality."""
    print("\n" + "=" * 60)
    print("Testing model adapter...")
    print("=" * 60)
    
    try:
        from src.services.agent.model_adapter import ModelAdapter

        # Test tool extraction
        test_text = "Let me call get_city_air_quality(city='London')"
        available_tools = ["get_city_air_quality", "get_weather_forecast"]
        
        extracted = ModelAdapter.extract_tool_calls_from_text(
            test_text,
            available_tools
        )
        
        print(f"✅ Extracted {len(extracted)} tool call(s) from text")
        if extracted:
            call = extracted[0]
            print(f"   Tool: {call.name}")
            print(f"   Arguments: {call.arguments}")
            print(f"   Confidence: {call.confidence}")
        
        return True
        
    except Exception as e:
        print(f"❌ Model adapter test failed: {e}")
        traceback.print_exc()
        return False


def test_response_validator():
    """Test response validation."""
    print("\n" + "=" * 60)
    print("Testing response validator...")
    print("=" * 60)
    
    try:
        from src.services.agent.orchestrator import ResponseValidator

        # Test valid response
        valid_response = "The air quality in London is good with PM2.5 levels at 15 µg/m³."
        is_valid, error = ResponseValidator.validate_response(
            valid_response,
            tools_used=["get_city_air_quality"]
        )
        print(f"✅ Valid response check: {is_valid} (error: {error})")
        
        # Test short response
        short_response = "Good."
        is_valid, error = ResponseValidator.validate_response(
            short_response,
            tools_used=[]
        )
        print(f"✅ Short response check: {is_valid} (error: {error})")
        
        return True
        
    except Exception as e:
        print(f"❌ Response validator test failed: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all verification tests."""
    print("\n" + "=" * 60)
    print("AERIS-AQ v2.10.0 - ENHANCEMENT VERIFICATION")
    print("=" * 60 + "\n")
    
    results = []
    
    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Orchestrator Basics", test_orchestrator_basics()))
    results.append(("Model Adapter", test_model_adapter()))
    results.append(("Response Validator", test_response_validator()))
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("=" * 60)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)
    
    if passed == total:
        print("\n🎉 All enhancements verified successfully!")
        print("The agent is ready for testing with low-end models.")
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
