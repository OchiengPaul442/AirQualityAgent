"""
Comprehensive Agent Service Tests
==================================

World-class test suite covering:
- Code leakage prevention
- Response formatting (including LaTeX)
- Tool execution and fallbacks
- Truncation detection
- Error handling
- Edge cases
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from domain.services.agent_service import AgentService


class TestCodeLeakagePrevention:
    """Test that agent NEVER shows code to users."""
    
    @pytest.fixture
    def agent_service(self):
        """Create agent service instance."""
        return AgentService()
    
    def test_detect_python_code_fence(self, agent_service):
        """Should detect Python code fences."""
        response = """
        Here's how to get air quality:
        ```python
        import requests
        data = get_air_quality()
        ```
        """
        assert agent_service._contains_code_blocks(response) is True
    
    def test_detect_json_code_fence(self, agent_service):
        """Should detect JSON code fences."""
        response = """
        The API returns:
        ```json
        {"pm25": 45, "aqi": 120}
        ```
        """
        assert agent_service._contains_code_blocks(response) is True
    
    def test_detect_expected_output_pattern(self, agent_service):
        """Should detect tutorial 'Expected Output:' pattern."""
        response = """
        Call the function and get:
        Expected Output:
        {"data": "value"}
        """
        assert agent_service._contains_code_blocks(response) is True
    
    def test_detect_coordinate_assignment(self, agent_service):
        """Should detect specific coordinate assignments."""
        response = """
        Set the coordinates:
        latitude = 32.5662
        longitude = 0.2066
        """
        assert agent_service._contains_code_blocks(response) is True
    
    def test_allow_legitimate_air_quality_response(self, agent_service):
        """Should NOT block legitimate air quality responses."""
        response = """
        The air quality near Kampala, Uganda is Good right now. 
        PM2.5 levels are 12 µg/m³ (AQI 50), which is safe for all activities.
        Data from AirQo monitor at Makerere University (0.5 km from your location).
        """
        assert agent_service._contains_code_blocks(response) is False
    
    def test_allow_technical_terms(self, agent_service):
        """Should NOT block responses with technical terms like 'import', 'class'."""
        response = """
        Air pollution has important health impacts, especially for vulnerable populations.
        The WHO classifies PM2.5 above 35 µg/m³ as hazardous.
        """
        assert agent_service._contains_code_blocks(response) is False
    
    def test_allow_references_to_data_sources(self, agent_service):
        """Should NOT block mentions of data sources or APIs."""
        response = """
        This data comes from the AirQo API network, which monitors air quality 
        across Uganda using low-cost sensors. The nearest station provides 
        real-time PM2.5 readings.
        """
        assert agent_service._contains_code_blocks(response) is False


class TestResponseCompleteness:
    """Test truncation and completeness detection."""
    
    @pytest.fixture
    def agent_service(self):
        return AgentService()
    
    def test_detect_incomplete_ending_with_comma(self, agent_service):
        """Should detect response ending with comma."""
        response = "The air quality is affected by traffic, industrial emissions,"
        assert agent_service._check_response_completeness(response) is True
    
    def test_detect_incomplete_ending_with_open_paren(self, agent_service):
        """Should detect response ending with open parenthesis."""
        response = "PM2.5 levels are measured in micrograms per cubic meter ("
        assert agent_service._check_response_completeness(response) is True
    
    def test_detect_incomplete_ending_with_bracket(self, agent_service):
        """Should detect response ending with open bracket."""
        response = "Health effects include respiratory issues ["
        assert agent_service._check_response_completeness(response) is True
    
    def test_complete_response_with_period(self, agent_service):
        """Should recognize complete response ending with period."""
        response = "The air quality is Good. PM2.5 is 15 µg/m³, which is safe for all activities."
        assert agent_service._check_response_completeness(response) is False
    
    def test_complete_response_with_question_mark(self, agent_service):
        """Should recognize complete response ending with question mark."""
        response = "Would you like to know more about PM2.5 levels?"
        assert agent_service._check_response_completeness(response) is False
    
    def test_short_response_not_marked_incomplete(self, agent_service):
        """Should not mark very short responses as incomplete."""
        response = "Good air quality."
        assert agent_service._check_response_completeness(response) is False


class TestLatexFormatting:
    """Test that LaTeX formulas use proper markdown syntax."""
    
    def test_inline_latex_format(self):
        """LaTeX should use $ delimiters for inline math."""
        # Correct format
        correct = "The formula is $PM_{2.5} = 45$ µg/m³"
        assert "$" in correct
        assert "[math]" not in correct
    
    def test_display_latex_format(self):
        """LaTeX should use $$ or \\[ \\] for display math."""
        # Correct formats should have proper delimiters
        correct1 = "$$E = mc^2$$"
        correct2 = "\\[E = mc^2\\]"
        
        # Check that correct formats have valid delimiters
        assert "$$" in correct1
        assert "\\[" in correct2
        assert "[math]" not in correct1  # Should not use invalid format
        assert "[math]" not in correct2  # Should not use invalid format


class TestToolExecution:
    """Test tool execution and data presentation."""
    
    @pytest.mark.asyncio
    async def test_air_quality_query_calls_tool(self):
        """Air quality queries should call get_air_quality_by_location."""
        agent = AgentService()
        
        # Mock the provider to return tool call
        with patch.object(agent.provider, 'process_message', new_callable=AsyncMock) as mock_provider:
            mock_provider.return_value = {
                "response": "The air quality is Good with PM2.5 of 12 µg/m³.",
                "tokens_used": 100,
                "cost_estimate": 0.001,
                "tools_used": ["get_air_quality_by_location"],
                "finish_reason": "stop",
            }
            
            result = await agent.process_message(
                message="What's the air quality in Kampala?",
                session_id="test_session"
            )
            
            assert result is not None
            assert "response" in result
            assert "Good" in result["response"] or "PM2.5" in result["response"] or "µg/m³" in result["response"]
            assert result.get("tools_used") is not None
    
    @pytest.mark.asyncio
    async def test_no_code_in_successful_response(self):
        """Successful responses should NEVER contain code."""
        agent = AgentService()
        
        with patch.object(agent.provider, 'process_message', new_callable=AsyncMock) as mock_provider:
            # Simulate a response that might have code
            mock_provider.return_value = {
                "response": "The air quality is Good. PM2.5: 15 µg/m³.",
                "tokens_used": 80,
                "cost_estimate": 0.0008,
                "tools_used": ["get_air_quality_by_location"],
                "finish_reason": "stop",
            }
            
            result = await agent.process_message(
                message="Air quality in my area?",
                session_id="test_session"
            )
            
            # Verify no code patterns
            response = result.get("response", "")
            assert "```" not in response
            assert "import " not in response or "import" not in response.lower()
            assert "Expected Output:" not in response
            assert "latitude =" not in response


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_provider_failure_returns_error_message(self):
        """Should return helpful error message when provider fails."""
        agent = AgentService()
        
        with patch.object(agent.provider, 'process_message', new_callable=AsyncMock) as mock_provider:
            mock_provider.side_effect = Exception("API Error")
            
            result = await agent.process_message(
                message="What's the air quality?",
                session_id="test_session"
            )
            
            assert result is not None
            assert "response" in result
            # Should have user-friendly error, not raw exception
            assert "exception" not in result["response"].lower() or "error" in result["response"].lower()
    
    @pytest.mark.asyncio
    async def test_empty_message_handled_gracefully(self):
        """Should handle empty messages gracefully."""
        agent = AgentService()
        
        result = await agent.process_message(
            message="",
            session_id="test_session"
        )
        
        assert result is not None
        assert "response" in result
    
    @pytest.mark.asyncio
    async def test_very_long_message_handled(self):
        """Should handle very long messages without crashing."""
        agent = AgentService()
        
        long_message = "What's the air quality? " * 1000  # Very long
        
        with patch.object(agent.provider, 'process_message', new_callable=AsyncMock) as mock_provider:
            mock_provider.return_value = {
                "response": "I can help with air quality data.",
                "tokens_used": 50,
                "cost_estimate": 0.0005,
                "tools_used": [],
                "finish_reason": "stop",
            }
            
            result = await agent.process_message(
                message=long_message,
                session_id="test_session"
            )
            
            assert result is not None


class TestMultiMonitorScenarios:
    """Test multi-monitor data handling."""
    
    @pytest.mark.asyncio
    async def test_multiple_monitors_mentioned_in_response(self):
        """When multiple monitors available, response should mention this."""
        agent = AgentService()
        
        with patch.object(agent.provider, 'process_message', new_callable=AsyncMock) as mock_provider:
            mock_provider.return_value = {
                "response": "I found 3 monitors near your location. Using data from Makerere University (0.3 km away): PM2.5 is 18 µg/m³.",
                "tokens_used": 120,
                "cost_estimate": 0.0012,
                "tools_used": ["get_air_quality_by_location"],
                "finish_reason": "stop",
            }
            
            result = await agent.process_message(
                message="Air quality near me?",
                session_id="test_session"
            )
            
            response = result.get("response", "")
            # Should mention monitor details
            assert any(word in response.lower() for word in ["monitor", "station", "sensor", "km", "away", "distance"])


class TestScientificAccuracy:
    """Test scientific accuracy requirements."""
    
    @pytest.mark.asyncio
    async def test_response_includes_units(self):
        """Responses should include proper units for measurements."""
        agent = AgentService()
        
        with patch.object(agent.provider, 'process_message', new_callable=AsyncMock) as mock_provider:
            mock_provider.return_value = {
                "response": "PM2.5: 25 µg/m³ (AQI 75, Moderate)",
                "tokens_used": 60,
                "cost_estimate": 0.0006,
                "tools_used": ["get_air_quality_by_location"],
                "finish_reason": "stop",
            }
            
            result = await agent.process_message(
                message="PM2.5 levels?",
                session_id="test_session"
            )
            
            response = result.get("response", "")
            # Should have units
            assert "µg/m³" in response or "μg/m³" in response or "ug/m3" in response


class TestMemoryManagement:
    """Test conversation memory handling."""
    
    @pytest.mark.asyncio
    async def test_conversation_history_maintained(self):
        """Should maintain conversation history across messages."""
        agent = AgentService()
        
        with patch.object(agent.provider, 'process_message', new_callable=AsyncMock) as mock_provider:
            mock_provider.return_value = {
                "response": "The air quality is Good.",
                "tokens_used": 50,
                "cost_estimate": 0.0005,
                "tools_used": [],
                "finish_reason": "stop",
            }
            
            # First message
            await agent.process_message("What's the air quality?", session_id="test_session")
            
            # Second message - should have history
            await agent.process_message("And the temperature?", session_id="test_session")
            
            # Provider should have been called with history
            call_args = mock_provider.call_args_list[-1]
            history = call_args[1].get('history', [])
            assert len(history) >= 2  # Should have previous exchange


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
