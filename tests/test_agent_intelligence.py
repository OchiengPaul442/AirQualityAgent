"""
Comprehensive test suite for agent intelligence and tool calling.

Tests the agent's ability to:
1. Understand user prompts
2. Call appropriate tools
3. Process tool results
4. Generate complete responses
5. Handle multi-city comparisons
6. Respond to various query types
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.agent_service import AgentService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class AgentIntelligenceTest:
    """Test suite for agent intelligence and capabilities."""
    
    def __init__(self):
        self.agent = AgentService()
        self.session_id = "7aa5a602-9b44-4d11-bd16-fc5253dc67d5"  # Use provided session ID
        self.test_results = []
        self.history = []  # Track conversation history
        
    async def run_test(self, test_name: str, message: str, expected_tools: list[str] = None, 
                       expected_content: list[str] = None, check_length: bool = True):
        """
        Run a single test case.
        
        Args:
            test_name: Name of the test
            message: User message to send
            expected_tools: List of tool names that should be called
            expected_content: List of strings that should appear in response
            check_length: Whether to check response length (should be > 100 chars)
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"TEST: {test_name}")
        logger.info(f"MESSAGE: {message}")
        logger.info(f"{'='*80}")
        
        try:
            # Process message
            result = await self.agent.process_message(
                message=message,
                history=self.history.copy(),  # Use conversation history
                style="general"
            )
            
            # Add to history
            self.history.append({"role": "user", "content": message})
            self.history.append({"role": "assistant", "content": result.get("response", "")})
            
            # Extract info
            response = result.get("response", "")
            tools_used = result.get("tools_used", [])
            tokens_used = result.get("tokens_used", 0)
            
            logger.info(f"\n📊 RESULTS:")
            logger.info(f"Response length: {len(response)} characters")
            logger.info(f"Tools used: {tools_used}")
            logger.info(f"Tokens used: {tokens_used}")
            logger.info(f"\n📝 RESPONSE:\n{response[:500]}{'...' if len(response) > 500 else ''}\n")
            
            # Validate results
            test_passed = True
            issues = []
            
            # Check if tools were called when expected
            if expected_tools:
                if not tools_used:
                    issues.append(f"❌ NO TOOLS CALLED - Expected: {expected_tools}")
                    test_passed = False
                else:
                    for tool in expected_tools:
                        if tool not in tools_used:
                            issues.append(f"❌ Missing tool: {tool}")
                            test_passed = False
                        else:
                            logger.info(f"✅ Tool called correctly: {tool}")
            
            # Check response length
            if check_length and len(response) < 100:
                issues.append(f"❌ Response too short ({len(response)} chars)")
                test_passed = False
            elif check_length:
                logger.info(f"✅ Response has good length ({len(response)} chars)")
            
            # Check for expected content
            if expected_content:
                for content in expected_content:
                    if content.lower() not in response.lower():
                        issues.append(f"❌ Missing expected content: '{content}'")
                        test_passed = False
                    else:
                        logger.info(f"✅ Found expected content: '{content}'")
            
            # Check for empty or error response
            if not response or "error" in response.lower() and "encounter" in response.lower():
                issues.append("❌ Empty or error response")
                test_passed = False
            
            # Log results
            if test_passed:
                logger.info(f"\n✅ TEST PASSED: {test_name}")
            else:
                logger.error(f"\n❌ TEST FAILED: {test_name}")
                for issue in issues:
                    logger.error(f"  {issue}")
            
            # Store result
            self.test_results.append({
                "test_name": test_name,
                "passed": test_passed,
                "issues": issues,
                "response_length": len(response),
                "tools_used": tools_used,
                "response_preview": response[:200]
            })
            
            return test_passed
            
        except Exception as e:
            logger.error(f"\n❌ TEST EXCEPTION: {test_name}")
            logger.error(f"Error: {e}", exc_info=True)
            self.test_results.append({
                "test_name": test_name,
                "passed": False,
                "issues": [f"Exception: {str(e)}"],
                "response_length": 0,
                "tools_used": [],
                "response_preview": ""
            })
            return False
    
    async def run_all_tests(self):
        """Run comprehensive test suite."""
        logger.info("\n" + "="*80)
        logger.info("STARTING AGENT INTELLIGENCE TEST SUITE")
        logger.info("="*80 + "\n")
        
        # Test 1: Simple single city query
        await self.run_test(
            test_name="Single City Air Quality",
            message="What is the air quality in London?",
            expected_tools=["get_city_air_quality"],
            expected_content=["London", "AQI", "PM"]
        )
        
        await asyncio.sleep(2)  # Rate limiting
        
        # Test 2: Multi-city comparison
        await self.run_test(
            test_name="Multi-City Comparison",
            message="Compare air quality in London, Paris, and New York",
            expected_tools=["get_city_air_quality"],
            expected_content=["London", "Paris", "New York"]
        )
        
        await asyncio.sleep(2)
        
        # Test 3: African city (should use AirQo)
        await self.run_test(
            test_name="African City (AirQo)",
            message="What's the air quality in Kampala?",
            expected_tools=["get_african_city_air_quality"],
            expected_content=["Kampala"]
        )
        
        await asyncio.sleep(2)
        
        # Test 4: Multiple African cities
        await self.run_test(
            test_name="Multiple African Cities",
            message="Compare air quality between Kampala and Nairobi",
            expected_tools=["get_multiple_african_cities_air_quality"],
            expected_content=["Kampala", "Nairobi"]
        )
        
        await asyncio.sleep(2)
        
        # Test 5: Current/Real-time query
        await self.run_test(
            test_name="Current Air Quality Query",
            message="Tell me the current air quality in Tokyo",
            expected_tools=["get_city_air_quality"],
            expected_content=["Tokyo", "current"]
        )
        
        await asyncio.sleep(2)
        
        # Test 6: Conversational follow-up (should remember context)
        await self.run_test(
            test_name="Conversational Follow-up",
            message="How does that compare to yesterday?",
            expected_tools=[],  # May or may not call tools
            check_length=False  # Follow-up might be shorter
        )
        
        await asyncio.sleep(2)
        
        # Test 7: Health recommendation query
        await self.run_test(
            test_name="Health Recommendations",
            message="Is it safe to exercise outdoors in London today?",
            expected_tools=["get_city_air_quality"],
            expected_content=["London", "exercise", "safe"]
        )
        
        await asyncio.sleep(2)
        
        # Test 8: Implied location query
        await self.run_test(
            test_name="Implied Context Query",
            message="What about Paris?",
            expected_tools=["get_city_air_quality"],
            expected_content=["Paris"]
        )
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary."""
        logger.info("\n" + "="*80)
        logger.info("TEST SUMMARY")
        logger.info("="*80)
        
        passed = sum(1 for r in self.test_results if r["passed"])
        total = len(self.test_results)
        
        logger.info(f"\nTotal Tests: {total}")
        logger.info(f"Passed: {passed}")
        logger.info(f"Failed: {total - passed}")
        logger.info(f"Success Rate: {(passed/total)*100:.1f}%\n")
        
        # Detailed results
        logger.info("DETAILED RESULTS:")
        for result in self.test_results:
            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            logger.info(f"\n{status}: {result['test_name']}")
            logger.info(f"  Response: {result['response_length']} chars")
            logger.info(f"  Tools: {result['tools_used']}")
            if result["issues"]:
                logger.info(f"  Issues:")
                for issue in result["issues"]:
                    logger.info(f"    {issue}")
        
        # Save results to file
        results_file = Path(__file__).parent / "test_results.json"
        with open(results_file, "w") as f:
            json.dump({
                "total_tests": total,
                "passed": passed,
                "failed": total - passed,
                "success_rate": (passed/total)*100,
                "results": self.test_results
            }, f, indent=2)
        
        logger.info(f"\n📄 Results saved to: {results_file}")
        
        # Exit with error code if tests failed
        if passed < total:
            logger.error(f"\n❌ {total - passed} TESTS FAILED - REVIEW AGENT LOGIC")
            sys.exit(1)
        else:
            logger.info(f"\n✅ ALL TESTS PASSED - AGENT IS WORKING CORRECTLY")
            sys.exit(0)


async def main():
    """Main test execution."""
    tester = AgentIntelligenceTest()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
