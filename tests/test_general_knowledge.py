"""
Test suite for general knowledge vs. current data handling.

Tests that the agent can:
1. Answer general health/science questions without tools
2. Use tools for current data questions
3. Maintain context across conversation
4. Handle follow-up questions appropriately
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings
from src.services.agent_service import AgentService

settings = get_settings()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class GeneralKnowledgeTests:
    """Test agent's ability to distinguish general vs data questions."""
    
    def __init__(self):
        self.agent = AgentService()
        self.results = []
    
    async def test_general_health_question(self):
        """Test: General health effects question should NOT use tools."""
        test_name = "General Health Effects"
        message = "What are the effects of high AQI values on a person's health in simple terms please"
        
        try:
            response = await self.agent.process_message(
                message=message,
                history=[]
            )
            
            # Should NOT use tools for general knowledge
            tools_used = response.get("tools_used", [])
            response_text = response.get("response", "")
            
            success = (
                len(tools_used) == 0 and  # No tools should be called
                len(response_text) > 100 and  # Should have substantial explanation
                any(keyword in response_text.lower() for keyword in [
                    "lung", "heart", "respiratory", "health", "breathe", "asthma"
                ])  # Should contain health-related terms
            )
            
            result = {
                "test": test_name,
                "message": message,
                "success": success,
                "tools_used": tools_used,
                "response_length": len(response_text),
                "response_preview": response_text[:200] + "..." if len(response_text) > 200 else response_text
            }
            
            self.results.append(result)
            status = "✅ PASS" if success else "❌ FAIL"
            logger.info(f"{status} - {test_name}")
            logger.info(f"   Tools used: {len(tools_used)}")
            logger.info(f"   Response length: {len(response_text)}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ FAIL - {test_name}: {e}")
            self.results.append({
                "test": test_name,
                "message": message,
                "success": False,
                "error": str(e)
            })
            return False
    
    async def test_specific_city_question(self):
        """Test: Specific city question SHOULD use tools."""
        test_name = "Specific City Data"
        message = "What is the air quality in London right now?"
        
        try:
            response = await self.agent.process_message(
                message=message,
                history=[]
            )
            
            tools_used = response.get("tools_used", [])
            response_text = response.get("response", "")
            
            # Should use tools for current data
            success = (
                len(tools_used) > 0 and
                len(response_text) > 50 and
                any(keyword in response_text.lower() for keyword in ["london", "aqi", "air quality"])
            )
            
            result = {
                "test": test_name,
                "message": message,
                "success": success,
                "tools_used": tools_used,
                "response_length": len(response_text),
                "response_preview": response_text[:200] + "..." if len(response_text) > 200 else response_text
            }
            
            self.results.append(result)
            status = "✅ PASS" if success else "❌ FAIL"
            logger.info(f"{status} - {test_name}")
            logger.info(f"   Tools used: {len(tools_used)}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ FAIL - {test_name}: {e}")
            self.results.append({
                "test": test_name,
                "message": message,
                "success": False,
                "error": str(e)
            })
            return False
    
    async def test_context_follow_up(self):
        """Test: Follow-up question should maintain context."""
        test_name = "Context Follow-Up"
        
        try:
            # First ask about a city
            response1 = await self.agent.process_message(
                message="What is the air quality in Paris?",
                history=[]
            )
            
            history = [
                {"role": "user", "content": "What is the air quality in Paris?"},
                {"role": "assistant", "content": response1["response"]}
            ]
            
            # Then ask general question - should understand it's general, not asking about Paris specifically
            response2 = await self.agent.process_message(
                message="What are the health effects of high pollution?",
                history=history
            )
            
            tools_used = response2.get("tools_used", [])
            response_text = response2.get("response", "")
            
            # Should NOT use tools for general question even after city query
            success = (
                len(tools_used) == 0 and
                len(response_text) > 100 and
                any(keyword in response_text.lower() for keyword in ["health", "lung", "respiratory"])
            )
            
            result = {
                "test": test_name,
                "message": "What are the health effects of high pollution? (after asking about Paris)",
                "success": success,
                "tools_used": tools_used,
                "response_length": len(response_text),
                "response_preview": response_text[:200] + "..." if len(response_text) > 200 else response_text
            }
            
            self.results.append(result)
            status = "✅ PASS" if success else "❌ FAIL"
            logger.info(f"{status} - {test_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ FAIL - {test_name}: {e}")
            self.results.append({
                "test": test_name,
                "success": False,
                "error": str(e)
            })
            return False
    
    async def test_explanation_question(self):
        """Test: Explanation question should NOT use tools."""
        test_name = "Explanation Question"
        message = "How does PM2.5 affect the human body?"
        
        try:
            response = await self.agent.process_message(
                message=message,
                history=[]
            )
            
            tools_used = response.get("tools_used", [])
            response_text = response.get("response", "")
            
            success = (
                len(tools_used) == 0 and
                len(response_text) > 100 and
                any(keyword in response_text.lower() for keyword in ["pm2.5", "particle", "lung", "blood"])
            )
            
            result = {
                "test": test_name,
                "message": message,
                "success": success,
                "tools_used": tools_used,
                "response_length": len(response_text),
                "response_preview": response_text[:200] + "..." if len(response_text) > 200 else response_text
            }
            
            self.results.append(result)
            status = "✅ PASS" if success else "❌ FAIL"
            logger.info(f"{status} - {test_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ FAIL - {test_name}: {e}")
            self.results.append({
                "test": test_name,
                "success": False,
                "error": str(e)
            })
            return False
    
    async def test_comparison_question(self):
        """Test: Comparison question SHOULD use tools for multiple cities."""
        test_name = "City Comparison"
        message = "Compare the air quality in New York and Tokyo"
        
        try:
            response = await self.agent.process_message(
                message=message,
                history=[]
            )
            
            tools_used = response.get("tools_used", [])
            response_text = response.get("response", "")
            
            # Should call tools for both cities
            success = (
                len(tools_used) >= 2 and  # At least 2 tool calls
                len(response_text) > 100 and
                "new york" in response_text.lower() and
                "tokyo" in response_text.lower()
            )
            
            result = {
                "test": test_name,
                "message": message,
                "success": success,
                "tools_used": tools_used,
                "response_length": len(response_text),
                "response_preview": response_text[:200] + "..." if len(response_text) > 200 else response_text
            }
            
            self.results.append(result)
            status = "✅ PASS" if success else "❌ FAIL"
            logger.info(f"{status} - {test_name}")
            logger.info(f"   Tools called: {len(tools_used)}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ FAIL - {test_name}: {e}")
            self.results.append({
                "test": test_name,
                "success": False,
                "error": str(e)
            })
            return False
    
    async def run_all_tests(self):
        """Run all tests and generate report."""
        logger.info("=" * 80)
        logger.info("STARTING GENERAL KNOWLEDGE TESTS")
        logger.info(f"Provider: {settings.AI_PROVIDER}")
        logger.info(f"Model: {settings.AI_MODEL}")
        logger.info("=" * 80)
        
        tests = [
            self.test_general_health_question,
            self.test_explanation_question,
            self.test_specific_city_question,
            self.test_comparison_question,
            self.test_context_follow_up,
        ]
        
        results = []
        for test in tests:
            try:
                result = await test()
                results.append(result)
                await asyncio.sleep(1)  # Brief pause between tests
            except Exception as e:
                logger.error(f"Test failed with exception: {e}")
                results.append(False)
        
        # Summary
        passed = sum(1 for r in results if r)
        total = len(results)
        pass_rate = (passed / total) * 100 if total > 0 else 0
        
        logger.info("=" * 80)
        logger.info("TEST SUMMARY")
        logger.info(f"Passed: {passed}/{total} ({pass_rate:.1f}%)")
        logger.info("=" * 80)
        
        # Save detailed results
        output_file = Path(__file__).parent / "general_knowledge_test_results.json"
        with open(output_file, "w") as f:
            json.dump({
                "timestamp": str(asyncio.get_event_loop().time()),
                "provider": settings.AI_PROVIDER,
                "model": settings.AI_MODEL,
                "total_tests": total,
                "passed": passed,
                "pass_rate": pass_rate,
                "results": self.results
            }, f, indent=2)
        
        logger.info(f"Detailed results saved to: {output_file}")
        
        return pass_rate >= 80  # 80% or better is success


async def main():
    """Run the test suite."""
    tests = GeneralKnowledgeTests()
    success = await tests.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
