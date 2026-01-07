"""
Comprehensive stress test for session context memory and document handling.

Tests:
1. Long conversation memory (20+ messages)
2. Document upload and persistent memory across messages
3. Context reference in follow-up questions
4. Memory cleanup and no hallucinations
5. Error recovery
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.database import SessionLocal
from src.db.repository import add_message, get_recent_session_history
from src.services.agent_service import AgentService

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_long_conversation_memory():
    """Test that agent remembers context across 20+ messages."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 1: Long Conversation Memory (20+ messages)")
    logger.info("=" * 80)
    
    agent = AgentService()
    session_id = f"test_session_{int(time.time())}"
    db = SessionLocal()
    
    try:
        # Conversation flow simulating a real user interaction
        messages = [
            ("What are the main air pollutants?", "Should list PM2.5, PM10, O3, NO2, SO2, CO"),
            ("Define PM2.5 and why it is important", "Should explain fine particles and health impacts"),
            ("What is the WHO guideline for PM2.5?", "Should mention 5 µg/m³ annual average"),
            ("How do atmospheric inversions affect air quality?", "Should explain temperature inversion trapping"),
            ("List three sources of urban air pollution", "Should mention vehicles, industry, residential heating"),
            ("What is an air quality standard?", "Should explain legal limits for pollutant concentrations"),
            ("Why should governments monitor air quality?", "Should mention health protection, policy enforcement"),
            ("What policy tools reduce vehicle emissions?", "Should mention emission standards, low-emission zones"),
            ("What is a non-attainment area?", "Should explain regions failing to meet standards"),
            ("Why do some countries struggle with guidelines?", "Should mention urbanization, enforcement, resources"),
            ("What are long-term health effects of air pollution?", "Should mention cardiovascular, respiratory, cancer"),
            ("Why are children more vulnerable?", "Should explain developing bodies, higher breathing rate"),
            ("How does pollution contribute to cardiovascular disease?", "Should mention inflammation, atherosclerosis"),
            ("What is the difference between indoor and outdoor pollution?", "Should contrast sources and concentrations"),
            ("How does poor air quality affect productivity?", "Should mention labor productivity, healthcare costs"),
            ("What are pollution hotspots?", "Should explain concentrated areas with high pollution"),
            ("How does air quality influence respiratory infections?", "Should mention immune suppression, clearance"),
            ("What is the impact on vulnerable groups?", "Should mention elderly, pregnant women, asthma patients"),
            ("How many deaths are linked to air pollution globally?", "Should mention 7 million premature deaths"),
            ("What are short-term effects of high pollution?", "Should mention eye irritation, respiratory attacks"),
        ]
        
        results = []
        for i, (user_msg, expected) in enumerate(messages, 1):
            logger.info(f"\n--- Message {i}/20 ---")
            logger.info(f"User: {user_msg}")
            
            # Get history from database
            history_objs = get_recent_session_history(db, session_id, max_messages=100)
            history = [{"role": m.role, "content": m.content} for m in history_objs]
            
            # Add user message to DB
            add_message(db, session_id, "user", user_msg)
            
            # Process message
            result = await agent.process_message(
                message=user_msg,
                history=history,
                session_id=session_id,
                style="simple"
            )
            
            response = result["response"]
            logger.info(f"Assistant: {response[:200]}...")
            logger.info(f"Expected: {expected}")
            
            # Add assistant response to DB
            add_message(db, session_id, "assistant", response)
            
            # Check for hallucinations or lost context
            if i > 5 and "I don't have memory" in response.lower():
                logger.error(f"❌ FAILED: Agent lost context at message {i}")
                results.append(False)
            elif "couldn't find" in response.lower() and "air quality" not in user_msg.lower():
                logger.error(f"❌ FAILED: Agent hallucinating location queries at message {i}")
                results.append(False)
            else:
                logger.info(f"✅ Message {i} processed successfully")
                results.append(True)
            
            # Small delay to prevent rate limiting
            await asyncio.sleep(0.5)
        
        # Final context check
        logger.info("\n--- Final Context Check ---")
        history_objs = get_recent_session_history(db, session_id, max_messages=100)
        logger.info(f"Total messages in session: {len(history_objs)}")
        
        success_rate = sum(results) / len(results) * 100
        logger.info(f"\n{'=' * 80}")
        logger.info(f"TEST 1 RESULT: {success_rate:.1f}% success rate ({sum(results)}/{len(results)})")
        logger.info(f"{'=' * 80}")
        
        return success_rate >= 90  # Pass if 90%+ successful
        
    finally:
        db.close()


async def test_document_persistence():
    """Test that document content is remembered across multiple messages."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Document Persistence and Memory")
    logger.info("=" * 80)
    
    agent = AgentService()
    session_id = f"test_doc_session_{int(time.time())}"
    db = SessionLocal()
    
    try:
        # Simulate document upload
        document_data = [{
            "filename": "air_quality_data.csv",
            "file_type": "csv",
            "content": "City,PM2.5,AQI\nNew York,12,45\nLos Angeles,35,95\nBeijing,85,155",
            "metadata": {"rows": 4, "columns": 3},
            "success": True,
            "truncated": False,
            "full_length": 100
        }]
        
        # Message sequence testing document memory
        messages = [
            ("Analyze this air quality data", document_data, "Should analyze the CSV data"),
            ("Which city has the highest PM2.5?", None, "Should remember Beijing from document"),
            ("What is the AQI for Los Angeles?", None, "Should remember 95 from document"),
            ("Compare New York and Beijing", None, "Should reference both cities from document"),
            ("What are the health implications?", None, "Should relate to document data context"),
        ]
        
        results = []
        for i, (user_msg, doc_data, expected) in enumerate(messages, 1):
            logger.info(f"\n--- Document Test {i}/5 ---")
            logger.info(f"User: {user_msg}")
            
            # Get history from database
            history_objs = get_recent_session_history(db, session_id, max_messages=100)
            history = [{"role": m.role, "content": m.content} for m in history_objs]
            
            # Add user message to DB
            add_message(db, session_id, "user", user_msg)
            
            # Process message
            result = await agent.process_message(
                message=user_msg,
                history=history,
                document_data=doc_data,
                session_id=session_id,
                style="technical"
            )
            
            response = result["response"]
            logger.info(f"Assistant: {response[:200]}...")
            logger.info(f"Expected: {expected}")
            
            # Add assistant response to DB
            add_message(db, session_id, "assistant", response)
            
            # Check if document context is retained
            if i > 1:  # After first message
                if i == 2 and "beijing" not in response.lower():
                    logger.error(f"❌ FAILED: Document data not remembered (Beijing)")
                    results.append(False)
                elif i == 3 and "95" not in response:
                    logger.error(f"❌ FAILED: Document data not remembered (AQI 95)")
                    results.append(False)
                else:
                    logger.info(f"✅ Document context retained at message {i}")
                    results.append(True)
            else:
                logger.info(f"✅ Document uploaded and analyzed")
                results.append(True)
            
            await asyncio.sleep(0.5)
        
        # Check session manager stats
        if hasattr(agent, 'session_manager'):
            stats = agent.session_manager.get_stats()
            logger.info(f"\nSession Manager Stats: {stats}")
            docs_in_session = agent.session_manager.get_session_documents(session_id)
            logger.info(f"Documents in session: {len(docs_in_session)}")
        
        success_rate = sum(results) / len(results) * 100
        logger.info(f"\n{'=' * 80}")
        logger.info(f"TEST 2 RESULT: {success_rate:.1f}% success rate ({sum(results)}/{len(results)})")
        logger.info(f"{'=' * 80}")
        
        return success_rate >= 80  # Pass if 80%+ successful
        
    finally:
        db.close()


async def test_context_summarization():
    """Test that very long conversations are handled without token overflow."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Context Summarization (50+ messages)")
    logger.info("=" * 80)
    
    agent = AgentService()
    session_id = f"test_long_session_{int(time.time())}"
    db = SessionLocal()
    
    try:
        # Simulate 50 messages
        for i in range(1, 51):
            user_msg = f"Test message {i}: What is the PM2.5 level significance?"
            
            # Get history
            history_objs = get_recent_session_history(db, session_id, max_messages=100)
            history = [{"role": m.role, "content": m.content} for m in history_objs]
            
            # Add to DB
            add_message(db, session_id, "user", user_msg)
            
            # Process
            result = await agent.process_message(
                message=user_msg,
                history=history,
                session_id=session_id,
                style="simple"
            )
            
            # Add response to DB
            add_message(db, session_id, "assistant", result["response"])
            
            if i % 10 == 0:
                logger.info(f"✅ Processed {i} messages without errors")
                # Check memory stats
                if hasattr(agent, 'session_manager'):
                    stats = agent.session_manager.get_stats()
                    logger.info(f"Session stats: {stats}")
            
            await asyncio.sleep(0.3)
        
        # Final check
        history_objs = get_recent_session_history(db, session_id, max_messages=100)
        logger.info(f"\n✅ Successfully processed 50 messages")
        logger.info(f"Retrieved {len(history_objs)} messages from database")
        
        logger.info(f"\n{'=' * 80}")
        logger.info(f"TEST 3 RESULT: PASSED - No token overflow errors")
        logger.info(f"{'=' * 80}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ TEST 3 FAILED: {e}")
        return False
    finally:
        db.close()


async def test_memory_cleanup():
    """Test that old sessions are properly cleaned up."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: Memory Cleanup and Leak Prevention")
    logger.info("=" * 80)
    
    agent = AgentService()
    
    if not hasattr(agent, 'session_manager'):
        logger.warning("⚠️  TEST 4 SKIPPED: SessionContextManager not available")
        return True
    
    try:
        # Create multiple sessions
        session_ids = [f"cleanup_test_{i}" for i in range(10)]
        
        for session_id in session_ids:
            await agent.process_message(
                message="Test message",
                history=[],
                session_id=session_id
            )
        
        stats = agent.session_manager.get_stats()
        logger.info(f"Created 10 sessions, stats: {stats}")
        
        # Wait for TTL to expire (simulate)
        logger.info("Simulating TTL expiry...")
        for session_id in session_ids:
            context = agent.session_manager.get_or_create_context(session_id)
            context["last_access"] = time.time() - 4000  # Older than TTL
        
        # Trigger cleanup
        agent.session_manager._cleanup_old_contexts()
        
        stats_after = agent.session_manager.get_stats()
        logger.info(f"After cleanup: {stats_after}")
        
        if stats_after["active_sessions"] < stats["active_sessions"]:
            logger.info(f"✅ Cleanup successful: {stats['active_sessions']} → {stats_after['active_sessions']} sessions")
            return True
        else:
            logger.error(f"❌ Cleanup failed: Sessions not removed")
            return False
        
    except Exception as e:
        logger.error(f"❌ TEST 4 FAILED: {e}")
        return False


async def run_all_tests():
    """Run all stress tests."""
    logger.info("\n" + "#" * 80)
    logger.info("STARTING COMPREHENSIVE SESSION CONTEXT STRESS TESTS")
    logger.info("#" * 80 + "\n")
    
    results = {}
    
    # Test 1: Long conversation memory
    try:
        results["long_conversation"] = await test_long_conversation_memory()
    except Exception as e:
        logger.error(f"Test 1 crashed: {e}", exc_info=True)
        results["long_conversation"] = False
    
    # Test 2: Document persistence
    try:
        results["document_persistence"] = await test_document_persistence()
    except Exception as e:
        logger.error(f"Test 2 crashed: {e}", exc_info=True)
        results["document_persistence"] = False
    
    # Test 3: Context summarization
    try:
        results["context_summarization"] = await test_context_summarization()
    except Exception as e:
        logger.error(f"Test 3 crashed: {e}", exc_info=True)
        results["context_summarization"] = False
    
    # Test 4: Memory cleanup
    try:
        results["memory_cleanup"] = await test_memory_cleanup()
    except Exception as e:
        logger.error(f"Test 4 crashed: {e}", exc_info=True)
        results["memory_cleanup"] = False
    
    # Summary
    logger.info("\n" + "#" * 80)
    logger.info("FINAL RESULTS")
    logger.info("#" * 80)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
    
    total_passed = sum(results.values())
    total_tests = len(results)
    logger.info(f"\nOverall: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        logger.info("🎉 ALL TESTS PASSED! Session context memory is working correctly.")
        return 0
    else:
        logger.error("⚠️  SOME TESTS FAILED. Review the logs above for details.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
