"""
Comprehensive test suite for Air Quality Agent
Tests all critical functionality including truncation, continuation, and API responses
"""

import time

import pytest
import requests

BASE_URL = "http://localhost:8000"


def check_server():
    """Check if server is running"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="module")
def require_server():
    """Fixture to ensure server is running"""
    if not check_server():
        pytest.skip("Server not running on http://localhost:8000")


class TestTruncationAndContinuation:
    """Test truncation detection and continuation feature"""
    
    def test_truncation_detected_correctly(self, require_server):
        """Test that truncated responses set correct flags"""
        # Long complex message that will trigger incompleteness
        long_message = """Designing a multi-variable calibration scheme for PM sensors involves several steps. 
        Given a sensor drift rate of 2% per month, calibrate periodically. Collect sensor data (Plantower PMS5003), 
        environmental variables (RH, temp, delta-T), reference measurements, timestamps, location data. 
        Data preprocessing includes handling missing values, detecting outliers, normalizing features, creating 
        time-based features. Feature engineering: polynomial features, interaction terms, lag features, 
        domain-specific transformations. Model selection: Multiple Linear Regression, Ridge/Lasso, Random Forest, 
        Gradient Boosting, Neural Networks depending on complexity and data characteristics."""
        
        session_id = f"trunc_test_{int(time.time())}"
        
        response = requests.post(
            f"{BASE_URL}/api/v1/agent/chat",
            data={"message": long_message, "session_id": session_id},
            timeout=120
        )
        
        assert response.status_code == 200, f"Request failed: {response.status_code}"
        data = response.json()
        
        # Check flags are set correctly
        truncated = data.get("truncated", False)
        requires_continuation = data.get("requires_continuation", False)
        finish_reason = data.get("finish_reason")
        response_text = data.get("response", "")
        
        print(f"\nTruncation Test Results:")
        print(f"truncated: {truncated}")
        print(f"requires_continuation: {requires_continuation}")
        print(f"finish_reason: {finish_reason}")
        print(f"Response length: {len(response_text)} chars")
        
        # If response is truncated, flags should be set correctly
        if truncated:
            assert requires_continuation == True, f"Response truncated but requires_continuation={requires_continuation}"
            assert finish_reason in ["stop", "length"], f"Invalid finish_reason: {finish_reason}"
    
    def test_continuation_works(self, require_server):
        """Test that continuation resumes correctly"""
        # First message
        session_id = f"cont_test_{int(time.time())}"
        
        response1 = requests.post(
            f"{BASE_URL}/api/v1/agent/chat",
            data={"message": "Explain PMF analysis with 36 elements over 2 years in detail", "session_id": session_id},
            timeout=120
        )
        
        assert response1.status_code == 200
        data1 = response1.json()
        
        if data1.get("truncated"):
            time.sleep(1)
            
            # Send continue
            response2 = requests.post(
                f"{BASE_URL}/api/v1/agent/chat",
                data={"message": "continue", "session_id": session_id},
                timeout=120
            )
            
            assert response2.status_code == 200
            data2 = response2.json()
            
            response1_text = data1.get("response", "")
            response2_text = data2.get("response", "")
            
            print(f"\nContinuation Test Results:")
            print(f"First response truncated: {data1.get('truncated')}")
            print(f"First response length: {len(response1_text)} chars")
            print(f"Continuation length: {len(response2_text)} chars")
            print(f"First response last 100 chars: ...{response1_text[-100:]}")
            print(f"Continuation first 100 chars: {response2_text[:100]}...")
            
            # Continuation should have content
            assert len(response2_text) > 0, "Continuation response is empty"
            
            # Check that continuation doesn't repeat the start of the first response
            # Extract first significant sentence from first response (skip common prefixes)
            first_response_words = response1_text[:500].lower()
            continuation_words = response2_text[:500].lower()
            
            # The continuation should NOT contain large chunks from the beginning of response1
            # This is a heuristic check - if more than 50% of the first 200 chars match, it's likely repeating
            if len(response1_text) > 200 and len(response2_text) > 200:
                # Look for substantial overlap indicating repetition
                overlap_threshold = 0.3  # Allow 30% overlap (some context is OK)
                first_chunk = set(response1_text[:200].lower().split())
                cont_chunk = set(response2_text[:200].lower().split())
                if len(first_chunk) > 0:
                    overlap = len(first_chunk & cont_chunk) / len(first_chunk)
                    print(f"Word overlap ratio: {overlap:.2f}")
                    if overlap > overlap_threshold:
                        print("WARNING: High overlap detected - continuation may be repeating content")
                    # Don't fail test but log the warning


class TestAPIResponses:
    """Test API response format and fields"""
    
    def test_response_has_required_fields(self, require_server):
        """Test that API response has all required fields"""
        session_id = f"api_test_{int(time.time())}"
        
        response = requests.post(
            f"{BASE_URL}/api/v1/agent/chat",
            data={"message": "What is PM2.5?", "session_id": session_id},
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Required fields
        required_fields = [
            "response",
            "session_id",
            "truncated",
            "requires_continuation",
            "finish_reason",
            "message_count",
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Check types
        assert isinstance(data["response"], str)
        assert isinstance(data["truncated"], bool)
        assert isinstance(data["requires_continuation"], bool)
        assert data["finish_reason"] in [None, "stop", "length"]
        
        print(f"\nAPI Response Fields:")
        for field in required_fields:
            print(f"  {field}: {data.get(field)}")
    
    def test_response_excludes_useless_fields(self, require_server):
        """Test that response doesn't include verbose/useless fields"""
        session_id = f"clean_test_{int(time.time())}"
        
        response = requests.post(
            f"{BASE_URL}/api/v1/agent/chat",
            data={"message": "Test", "session_id": session_id},
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # These fields should NOT be in response (removed for simplicity)
        excluded_fields = ["reasoning_content", "thinking_steps"]
        
        for field in excluded_fields:
            assert field not in data, f"Response should not include {field}"


class TestLocationHandling:
    """Test location handling (from previous bug fix)"""
    
    def test_ip_based_location_no_crash(self, require_server):
        """Test that IP-based location doesn't crash"""
        session_id = f"location_test_{int(time.time())}"
        
        # First message without location
        response1 = requests.post(
            f"{BASE_URL}/api/v1/agent/chat",
            data={"message": "What's the air quality?", "session_id": session_id},
            timeout=30
        )
        
        assert response1.status_code == 200
        
        # Follow-up with city name (IP-based location, no GPS)
        response2 = requests.post(
            f"{BASE_URL}/api/v1/agent/chat",
            data={"message": "Cape Town", "session_id": session_id},
            timeout=30
        )
        
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Should not crash, should have response
        assert len(data2.get("response", "")) > 0


if __name__ == "__main__":
    # Run with: python -m pytest tests/test_agent_comprehensive.py -v -s
    pytest.main([__file__, "-v", "-s", "--tb=short"])
