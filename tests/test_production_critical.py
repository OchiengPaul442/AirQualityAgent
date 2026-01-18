"""
Production Critical Test - Real User Scenarios
Tests the exact failure cases reported by users
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from domain.services.agent_service import AgentService


class TestProductionScenarios:
    """Test real production scenarios that failed"""
    
    @pytest.mark.asyncio
    async def test_user_asks_whats_air_quality_no_location(self):
        """
        User: "What's the air quality like in my city right now?"
        Agent should ask for city name
        """
        agent = AgentService()
        
        message = "What's the air quality like in my city right now?"
        history = []
        
        # Mock provider response
        with patch.object(agent.provider, 'process_message', new_callable=AsyncMock) as mock_process:
            mock_process.return_value = {
                "response": "Could you please provide me with the name of your city or its coordinates?",
                "tokens_used": 50,
                "cost_estimate": 0.001,
                "cached": False,
                "finish_reason": "stop"
            }
            
            result = await agent.process_message(
                message=message,
                history=history,
                location_data=None,  # No location provided
                session_id="test-session"
            )
            
            assert "response" in result
            assert result["response"] is not None
            assert len(result["response"]) > 0
            print(f"✓ Agent response: {result['response'][:100]}")
    
    @pytest.mark.asyncio
    async def test_user_provides_cape_town(self):
        """
        CRITICAL TEST: This was causing crashes!
        User: "Cape town"
        Agent should process this without crashing
        """
        agent = AgentService()
        
        message = "Cape town"
        history = [
            {"role": "user", "content": "What's the air quality like in my city right now?"},
            {"role": "assistant", "content": "Could you please provide me with the name of your city?"}
        ]
        
        # This should NOT crash with KeyError
        try:
            with patch.object(agent.provider, 'process_message', new_callable=AsyncMock) as mock_process:
                mock_process.return_value = {
                    "response": "Cape Town's current air quality shows PM2.5 at 15 µg/m³ (AQI 57, Moderate).",
                    "tokens_used": 100,
                    "cost_estimate": 0.002,
                    "cached": False,
                    "finish_reason": "stop",
                    "tools_used": ["get_air_quality_for_city"]
                }
                
                result = await agent.process_message(
                    message=message,
                    history=history,
                    location_data={"source": "ip", "ip_address": "197.221.168.51"},  # IP-based, not GPS
                    session_id="test-session"
                )
                
                assert "response" in result
                assert "error" not in result or result.get("error") is None
                assert result["response"] is not None
                print(f"✓ Successfully processed Cape Town query: {result['response'][:100]}")
                
        except KeyError as e:
            pytest.fail(f"CRITICAL: KeyError crash when processing city name! {e}")
        except Exception as e:
            pytest.fail(f"CRITICAL: Unexpected error: {e}")
    
    @pytest.mark.asyncio
    async def test_complex_chemistry_question(self):
        """
        Test complex photochemical question
        """
        agent = AgentService()
        
        message = """A city is experiencing a high ozone episode (peak 180 µg/m³) during a heatwave 
        while simultaneously measuring elevated NO₂ (85 µg/m³) and VOCs from traffic. Explain the 
        complete photochemical reaction chain."""
        
        history = []
        
        with patch.object(agent.provider, 'process_message', new_callable=AsyncMock) as mock_process:
            mock_process.return_value = {
                "response": "The city is experiencing a challenging air quality situation with elevated ozone...",
                "tokens_used": 500,
                "cost_estimate": 0.01,
                "cached": False,
                "finish_reason": "stop",
                "tools_used": ["web_search"]
            }
            
            result = await agent.process_message(
                message=message,
                history=history,
                location_data=None,
                session_id="test-session"
            )
            
            assert "response" in result
            assert result["response"] is not None
            print(f"✓ Complex chemistry question handled")
    
    @pytest.mark.asyncio
    async def test_location_data_with_ip_only(self):
        """
        Test that IP-based location doesn't crash when accessing GPS fields
        """
        agent = AgentService()
        
        message = "What's the air quality?"
        history = []
        
        # IP-based location (NO latitude/longitude)
        location_data = {"source": "ip", "ip_address": "41.191.232.237"}
        
        try:
            with patch.object(agent.provider, 'process_message', new_callable=AsyncMock) as mock_process:
                mock_process.return_value = {
                    "response": "Current air quality data shows moderate levels.",
                    "tokens_used": 50,
                    "cost_estimate": 0.001,
                    "cached": False,
                    "finish_reason": "stop"
                }
                
                result = await agent.process_message(
                    message=message,
                    history=history,
                    location_data=location_data,
                    session_id="test-session"
                )
                
                assert "response" in result
                assert "error" not in result or result.get("error") is None
                print(f"✓ IP-based location handled correctly")
                
        except KeyError as e:
            pytest.fail(f"CRITICAL: KeyError when processing IP-based location! {e}")
    
    @pytest.mark.asyncio
    async def test_location_data_with_gps(self):
        """
        Test GPS-based location works correctly
        """
        agent = AgentService()
        
        message = "Air quality here?"
        history = []
        
        # GPS-based location (WITH latitude/longitude)
        location_data = {
            "source": "gps",
            "latitude": -33.9249,
            "longitude": 18.4241
        }
        
        with patch.object(agent.provider, 'process_message', new_callable=AsyncMock) as mock_process:
            mock_process.return_value = {
                "response": "At your location (Cape Town), PM2.5 is 15 µg/m³.",
                "tokens_used": 80,
                "cost_estimate": 0.002,
                "cached": False,
                "finish_reason": "stop",
                "tools_used": ["get_air_quality_by_location"]
            }
            
            result = await agent.process_message(
                message=message,
                history=history,
                location_data=location_data,
                session_id="test-session"
            )
            
            assert "response" in result
            assert result["response"] is not None
            print(f"✓ GPS-based location handled correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
