# Quick Testing Guide

## Running Tests

### Full Test Suite

```bash
python tests/test_agent_intelligence.py
```

### Expected Output

```
✅ ALL TESTS PASSED - AGENT IS WORKING CORRECTLY
Total Tests: 8
Passed: 8
Failed: 0
Success Rate: 100.0%
```

## Test Coverage

The test suite validates:

1. **Single City Queries** - "What is the air quality in London?"
2. **Multi-City Comparisons** - "Compare London, Paris, and New York"
3. **African Cities** - "What's the air quality in Kampala?"
4. **Multiple African Cities** - "Compare Kampala and Nairobi"
5. **Current Data Requests** - "Tell me the current air quality in Tokyo"
6. **Conversational Follow-ups** - "How does that compare to yesterday?"
7. **Health Questions** - "Is it safe to exercise outdoors in London?"
8. **Implied Context** - "What about Paris?"

## What's Tested

### ✅ Tool Calling

- Correct tool selection
- Appropriate tool for region (African vs global)
- Multi-tool coordination

### ✅ Response Quality

- Complete answers (100+ chars minimum)
- Proper formatting
- All expected content present

### ✅ Understanding

- Intent recognition
- Context maintenance
- Natural language processing

## Test Results Location

Results are saved to: `tests/test_results.json`

## Common Issues & Solutions

### Issue: Agent not calling tools

**Solution:** Check system instructions have proper tool usage guidance

### Issue: Responses truncated

**Solution:** Verify max_tokens is not multiplied (should be 2000 for general)

### Issue: Wrong tool selected

**Solution:** Review tool descriptions - ensure they're clear about when to use each

### Issue: Empty responses

**Solution:** Check provider error handling and fallback logic

## Manual Testing

You can also test manually using the session ID:

```python
from src.services.agent_service import AgentService
import asyncio

async def test_manual():
    agent = AgentService()
    result = await agent.process_message(
        message="What is the air quality in London?",
        history=[],
        style="general"
    )
    print(result["response"])

asyncio.run(test_manual())
```

## Debugging

Enable verbose logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Test Session ID

Use this session ID for testing: `7aa5a602-9b44-4d11-bd16-fc5253dc67d5`

## Success Criteria

✅ All tests pass (100% success rate)  
✅ Tools are called when expected  
✅ Responses are complete (>100 chars)  
✅ Expected content is present in responses  
✅ No exceptions or errors

## Next Steps

1. Run the test suite after any changes
2. Add new test cases for edge cases
3. Monitor real-world usage patterns
4. Iterate on tool descriptions based on performance

---

**Last Updated:** January 5, 2026  
**Test Pass Rate:** 100%
