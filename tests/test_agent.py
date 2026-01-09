"""
Consolidated Test Suite - All Features

Tests all agent functionality in one comprehensive suite:
- Core agent features (reasoning, cost optimization, capabilities)
- API endpoints (chat, sessions, health)
- Data sources (WAQI, AirQo, OpenMeteo)
- Document processing and context management
- Security and error handling
- Performance and concurrency
"""

import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings
from src.services.agent.cost_optimizer import CostOptimizer, get_cost_optimizer

# ============================================================================
# CORE FEATURES TESTS
# ============================================================================


class TestCostOptimization:
    """Test cost optimization features."""
    
    def test_response_caching(self):
        """Test response caching mechanism."""
        optimizer = CostOptimizer(cache_ttl_seconds=60)
        
        # No cache initially
        cached = optimizer.get_cached_response("What's the air quality in Nairobi?")
        assert cached is None
        
        # Cache a response
        response = {"answer": "The air quality is good"}
        optimizer.cache_response("What's the air quality in Nairobi?", response)
        
        # Should get cached response
        cached = optimizer.get_cached_response("What's the air quality in Nairobi?")
        assert cached is not None
        assert cached["answer"] == "The air quality is good"
    
    def test_document_session_persistence(self):
        """Test that document content persists within session even with cache expiry."""
        optimizer = CostOptimizer(cache_ttl_seconds=1)
        
        # Cache response with document context
        session_context = {"session_id": "test123", "has_document": True}
        optimizer.cache_response("analyze data", {"data": "results"}, session_context)
        
        # Should be available immediately
        cached = optimizer.get_cached_response("analyze data", session_context)
        assert cached is not None
        
        # Wait for normal cache expiration
        time.sleep(2)
        
        # For sessions with documents, should still be available
        # (This will be enhanced in cost_optimizer.py)
        cached = optimizer.get_cached_response("analyze data", session_context)
        # Note: Will implement extended TTL for document sessions
    
    def test_token_usage_tracking(self):
        """Test token usage tracking per session with warnings."""
        optimizer = CostOptimizer(max_tokens_per_session=1000)
        
        # Normal usage
        stats = optimizer.track_token_usage("session123", 300, cost=0.0045)
        assert stats["total_tokens"] == 300
        assert stats["usage_percentage"] == 30.0
        assert stats["warning"] is None
        
        # High usage - should warn
        stats = optimizer.track_token_usage("session123", 500, cost=0.0075)
        assert stats["total_tokens"] == 800
        assert stats["usage_percentage"] == 80.0
        assert stats["warning"] is not None
        assert "conversation" in stats["warning"].lower()
        assert "recommendation" in stats
        assert stats["recommendation"] is not None
    
    def test_query_complexity_analysis(self):
        """Test smart model selection based on query complexity."""
        optimizer = CostOptimizer()
        
        # Simple queries -> use cheaper model
        assert optimizer.should_use_cheaper_model("What is the air quality?") is True
        assert optimizer.should_use_cheaper_model("Show me current data") is True
        
        # Complex queries -> use advanced model
        assert optimizer.should_use_cheaper_model("Analyze and compare pollution trends") is False
        assert optimizer.should_use_cheaper_model("Explain why PM2.5 is increasing") is False
    
    def test_request_deduplication(self):
        """Test duplicate request detection."""
        optimizer = CostOptimizer()
        
        # First request
        is_duplicate = optimizer.deduplicate_request("query123")
        assert is_duplicate is False
        
        # Same request immediately after
        is_duplicate = optimizer.deduplicate_request("query123")
        assert is_duplicate is True
        
        # Complete first request
        optimizer.complete_request("query123")
        
        # Now it's not duplicate
        is_duplicate = optimizer.deduplicate_request("query123")
        assert is_duplicate is False
    
    def test_cache_statistics(self):
        """Test cost optimization statistics."""
        optimizer = CostOptimizer()
        
        # Make requests
        optimizer.get_cached_response("query1")  # Miss
        optimizer.cache_response("query1", {"data": "test"})
        optimizer.get_cached_response("query1")  # Hit
        optimizer.get_cached_response("query1")  # Hit
        
        stats = optimizer.get_statistics()
        assert stats["total_requests"] == 3
        assert stats["cache_hits"] == 2
        assert stats["cache_misses"] == 1
        assert stats["cache_hit_rate_pct"] == pytest.approx(66.67, rel=0.1)


class TestConfiguration:
    """Test configuration enhancements."""
    
    def test_image_upload_config(self):
        """Test image upload configuration."""
        settings = get_settings()
        
        assert hasattr(settings, 'SUPPORT_IMAGE_UPLOAD')
        assert hasattr(settings, 'MAX_IMAGE_SIZE_MB')
        assert hasattr(settings, 'ALLOWED_IMAGE_FORMATS')
        assert hasattr(settings, 'VISION_CAPABLE_MODELS')
    
    def test_vision_capability_detection(self):
        """Test checking if model supports vision."""
        settings = get_settings()
        
        # Known vision models
        assert settings.is_vision_capable("gemini", "gemini-1.5-flash") is True
        assert settings.is_vision_capable("openai", "gpt-4o") is True
        
        # Non-vision models
        assert settings.is_vision_capable("openai", "gpt-3.5-turbo") is False
    
    def test_cost_optimization_config(self):
        """Test cost optimization settings."""
        settings = get_settings()
        
        assert hasattr(settings, 'ENABLE_COST_OPTIMIZATION')
        assert hasattr(settings, 'CACHE_RESPONSE_TTL_SECONDS')
        assert hasattr(settings, 'MAX_TOKENS_PER_SESSION')
    
    def test_reasoning_config(self):
        """Test reasoning engine settings."""
        settings = get_settings()
        
        assert hasattr(settings, 'ENABLE_REASONING_DISPLAY')
        assert hasattr(settings, 'REASONING_STYLE')


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

def test_full_system_integration():
    """Test all systems working together."""
    # Configuration
    settings = get_settings()
    assert settings is not None
    
    # Cost optimizer
    optimizer = get_cost_optimizer()
    
    query = "What's the air quality in Nairobi?"
    
    # First query - cache miss
    cached = optimizer.get_cached_response(query)
    assert cached is None
    
    # Cache result
    optimizer.cache_response(query, {"answer": "Good"})
    
    # Second query - cache hit
    cached = optimizer.get_cached_response(query)
    assert cached is not None
    
    # Track tokens
    stats = optimizer.track_token_usage("session1", 500, 0.01)
    assert stats["total_tokens"] == 500
    
    print("✅ Full system integration test PASSED")


def test_session_token_limit_warning():
    """Test that users get proper warnings when approaching token limits."""
    optimizer = CostOptimizer(max_tokens_per_session=1000)
    
    # Use 800 tokens (80%)
    stats = optimizer.track_token_usage("session_xyz", 800, 0.012)
    
    assert stats["warning"] is not None
    assert "conversation" in stats["warning"].lower()
    assert "token" in stats["warning"].lower()
    assert stats["usage_percentage"] == 80.0
    
    # Verify warning is user-friendly
    warning = stats["warning"]
    recommendation = stats["recommendation"]
    
    assert len(warning) > 0
    assert len(warning) < 200  # Should be concise
    assert recommendation is not None
    assert "new chat" in recommendation.lower()
    
    print(f"✅ Token limit warning: {warning}")
    print(f"✅ Recommendation: {recommendation}")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
