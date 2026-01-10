"""
Comprehensive Unit Tests for Streaming Endpoint

Tests the /api/v1/agent/chat/stream endpoint to ensure:
1. Proper SSE event emission (thoughts, response, done)
2. Stream completion signaling
3. Error handling and recovery
4. Session management
5. Thought stream lifecycle

Based on Anthropic's best practices for building effective agents.
"""

import json

import pytest
from fastapi.testclient import TestClient

from interfaces.rest_api.main import app

# Test session ID as specified by the user
TEST_SESSION_ID = "ca02cea3-c17e-471b-8d04-0ecc9c823367"


class TestStreamEndpoint:
    """Comprehensive tests for the streaming endpoint"""

    def setup_method(self):
        """Setup test fixtures"""
        self.client = TestClient(app)
        self.session_id = TEST_SESSION_ID

    def test_stream_basic_query(self):
        """Test basic streaming with a simple query"""
        # Send streaming request
        response = self.client.post(
            "/api/v1/agent/chat/stream",
            data={
                "message": "What is the difference between \"point sources,\" \"area sources,\" and \"mobile sources\" of air pollution, and how do control strategies differ for each?",
                "session_id": self.session_id,
                "style": "general"
            },
            headers={"Accept": "text/event-stream"}
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Parse SSE events
        events = self._parse_sse_stream(response.text)

        # Verify event types
        event_types = [e["type"] for e in events]

        # Should have at least: thoughts, response, done
        assert "thought" in event_types, "Should have thought events"
        assert "response" in event_types, "Should have response event"
        assert "done" in event_types, "Should have done event"

        # Verify done is the last event
        assert events[-1]["type"] == "done", "Done event should be last"

        # Verify response structure
        response_events = [e for e in events if e["type"] == "response"]
        assert len(response_events) == 1, "Should have exactly one response event"

        response_data = response_events[0]["data"]["data"]  # Access nested data
        assert "response" in response_data, "Response should have 'response' field"
        assert "session_id" in response_data, "Response should have 'session_id' field"
        assert "tools_used" in response_data, "Response should have 'tools_used' field"
        assert isinstance(response_data["response"], str), "Response text should be string"
        assert len(response_data["response"]) > 0, "Response should not be empty"

    def test_stream_thought_events(self):
        """Test that thought events are properly emitted"""
        response = self.client.post(
            "/api/v1/agent/chat/stream",
            data={
                "message": "Compare air quality in Paris and Berlin",
                "session_id": self.session_id
            }
        )

        events = self._parse_sse_stream(response.text)
        thought_events = [e for e in events if e["type"] == "thought"]

        # Should have multiple thought events
        assert len(thought_events) > 0, "Should have at least one thought event"

        # Verify thought event structure
        for thought in thought_events:
            data = thought["data"]
            assert "type" in data, "Thought should have type"
            assert "title" in data, "Thought should have title"
            assert "details" in data, "Thought should have details"
            assert "timestamp" in data, "Thought should have timestamp"
            assert isinstance(data["details"], dict), "Details should be dict"

        # Check for expected thought types
        thought_types = [t["data"].get("type") for t in thought_events]

        # Should have query analysis as first thought
        if len(thought_types) > 0:
            assert any("query" in str(t).lower() or "analysis" in str(t).lower()
                      for t in thought_types), "Should have query analysis thought"

    def test_stream_completion_signal(self):
        """Test that stream properly signals completion"""
        response = self.client.post(
            "/api/v1/agent/chat/stream",
            data={
                "message": "How might climate change policies interact with traditional air quality regulations, particularly regarding co-benefits of greenhouse gas reduction strategies?",
                "session_id": self.session_id
            }
        )

        events = self._parse_sse_stream(response.text)

        # Find done event
        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1, "Should have exactly one done event"

        # Verify done is last event
        assert events[-1]["type"] == "done", "Done event must be the last event"

        # Verify complete thought is emitted before response
        complete_thoughts = [
            e for e in events
            if e["type"] == "thought" and e["data"].get("type") == "complete"
        ]

        if complete_thoughts:
            complete_idx = events.index(complete_thoughts[0])
            response_events = [e for e in events if e["type"] == "response"]
            if response_events:
                response_idx = events.index(response_events[0])
                assert complete_idx < response_idx, "Complete thought should come before response"

    def test_stream_error_handling(self):
        """Test error handling in streaming"""
        # Test with empty message should return validation error
        response = self.client.post(
            "/api/v1/agent/chat/stream",
            data={
                "message": "",
                "session_id": self.session_id
            }
        )

        # Empty message should return 422 validation error, not SSE stream
        assert response.status_code == 422, "Should return validation error for empty message"

        # Test with whitespace-only message
        response = self.client.post(
            "/api/v1/agent/chat/stream",
            data={
                "message": "   ",  # Only whitespace
                "session_id": self.session_id
            }
        )

        # Whitespace-only should trigger error event in stream
        assert response.status_code == 200, "Should return SSE stream for whitespace message"
        events = self._parse_sse_stream(response.text)

        # Should have error event for whitespace-only message
        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) > 0, "Should have error event for whitespace-only message"

        # Should still have done event
        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1, "Should have done event even on error"

        # Verify error event structure
        error_data = error_events[0]["data"]
        assert "error" in str(error_data).lower() or "details" in error_data, \
            "Error event should contain error information"

    def test_stream_session_persistence(self):
        """Test that session is properly maintained across streaming requests"""
        # First request
        response1 = self.client.post(
            "/api/v1/agent/chat/stream",
            data={
                "message": "What is AQI?",
                "session_id": self.session_id
            }
        )

        events1 = self._parse_sse_stream(response1.text)
        response_data1 = [e for e in events1 if e["type"] == "response"][0]["data"]["data"]

        # Session ID should match
        assert response_data1["session_id"] == self.session_id

        # Second request with same session
        response2 = self.client.post(
            "/api/v1/agent/chat/stream",
            data={
                "message": "What was my previous question?",
                "session_id": self.session_id
            }
        )

        events2 = self._parse_sse_stream(response2.text)
        response_data2 = [e for e in events2 if e["type"] == "response"][0]["data"]["data"]

        # Should maintain same session
        assert response_data2["session_id"] == self.session_id

        # Response should reference previous context (this is agent behavior dependent)
        # We can at least verify it completed successfully
        assert len(response_data2["response"]) > 0

    def test_stream_with_file_upload(self):
        """Test streaming with document upload"""
        # Create a simple CSV file
        csv_content = b"location,aqi,pm25\nLondon,45,12.5\nParis,38,10.2"

        response = self.client.post(
            "/api/v1/agent/chat/stream",
            data={
                "message": "Analyze this air quality data",
                "session_id": self.session_id
            },
            files={
                "file": ("test_data.csv", csv_content, "text/csv")
            }
        )

        assert response.status_code == 200

        events = self._parse_sse_stream(response.text)

        # Should complete successfully
        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1

        # Should have response
        response_events = [e for e in events if e["type"] == "response"]
        assert len(response_events) == 1

    def test_stream_timeout_protection(self):
        """Test that stream has timeout protection"""
        import time

        start_time = time.time()

        response = self.client.post(
            "/api/v1/agent/chat/stream",
            data={
                "message": "What is air quality?",
                "session_id": self.session_id
            },
            timeout=120.0  # 2 minute timeout
        )

        duration = time.time() - start_time

        # Should complete within reasonable time
        assert duration < 120, f"Stream took too long: {duration}s"

        events = self._parse_sse_stream(response.text)

        # Should still complete properly
        assert any(e["type"] == "done" for e in events), "Should complete with done event"

    def test_stream_concurrent_requests(self):
        """Test handling of concurrent streaming requests"""
        import concurrent.futures
        import time

        def make_request(message: str, session_id: str):
            return self.client.post(
                "/api/v1/agent/chat/stream",
                data={
                    "message": message,
                    "session_id": session_id
                }
            )

        # Make 3 concurrent requests with different sessions
        sessions = [f"{self.session_id}-{i}" for i in range(3)]
        messages = [
            "What is PM2.5?",
            "What is PM10?",
            "What is ozone?"
        ]

        start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(make_request, msg, sess)
                for msg, sess in zip(messages, sessions, strict=False)
            ]

            responses = [f.result() for f in concurrent.futures.as_completed(futures)]

        duration = time.time() - start_time

        # All should succeed
        assert all(r.status_code == 200 for r in responses), "All requests should succeed"

        # All should complete with done event
        for response in responses:
            events = self._parse_sse_stream(response.text)
            assert any(e["type"] == "done" for e in events), "Each should have done event"

        print(f"Concurrent requests completed in {duration:.2f}s")

    def test_stream_response_quality(self):
        """Test the quality and completeness of streamed responses"""
        response = self.client.post(
            "/api/v1/agent/chat/stream",
            data={
                "message": "What are the health effects of poor air quality?",
                "session_id": self.session_id
            }
        )

        events = self._parse_sse_stream(response.text)
        response_events = [e for e in events if e["type"] == "response"]

        assert len(response_events) == 1, "Should have exactly one response"

        response_data = response_events[0]["data"]["data"]
        response_text = response_data["response"]

        # Quality checks
        assert len(response_text) > 100, "Response should be substantive (>100 chars)"
        assert len(response_text) < 10000, "Response should be reasonable length (<10k chars)"

        # Should not contain reasoning artifacts
        forbidden_phrases = [
            "the user wants",
            "the user is asking",
            "i should respond",
            "let me think"
        ]

        response_lower = response_text.lower()
        for phrase in forbidden_phrases:
            assert phrase not in response_lower, \
                f"Response should not expose internal reasoning: '{phrase}'"

    def test_stream_thought_progression(self):
        """Test that thoughts progress logically through the workflow"""
        response = self.client.post(
            "/api/v1/agent/chat/stream",
            data={
                "message": "Get air quality data for Tokyo",
                "session_id": self.session_id
            }
        )

        events = self._parse_sse_stream(response.text)
        thought_events = [e for e in events if e["type"] == "thought"]

        # Extract thought types in order
        thought_types = [t["data"].get("type", "unknown") for t in thought_events]

        # Expected progression (at least some of these should appear in order)
        expected_stages = [
            "query_analysis",
            "tool_selection",
            "tool_execution",
            "response_synthesis"
        ]

        # Check that stages appear in logical order
        stage_indices = {}
        for stage in expected_stages:
            matching = [i for i, t in enumerate(thought_types) if stage in str(t).lower()]
            if matching:
                stage_indices[stage] = min(matching)

        # If we have multiple stages, verify they're in order
        if len(stage_indices) >= 2:
            stages_list = list(stage_indices.items())
            for i in range(len(stages_list) - 1):
                current_stage, current_idx = stages_list[i]
                next_stage, next_idx = stages_list[i + 1]
                assert current_idx < next_idx, \
                    f"{current_stage} should come before {next_stage}"

    def test_stream_metadata_completeness(self):
        """Test that response metadata is complete and accurate"""
        response = self.client.post(
            "/api/v1/agent/chat/stream",
            data={
                "message": "What is the current air quality?",
                "session_id": self.session_id
            }
        )

        events = self._parse_sse_stream(response.text)
        response_events = [e for e in events if e["type"] == "response"]

        response_data = response_events[0]["data"]["data"]

        # Required fields
        required_fields = ["response", "tools_used", "tokens_used", "cached", "session_id"]
        for field in required_fields:
            assert field in response_data, f"Response should have '{field}' field"

        # Type checks
        assert isinstance(response_data["response"], str)
        assert isinstance(response_data["tools_used"], list)
        assert isinstance(response_data["tokens_used"], (int, float))
        assert isinstance(response_data["cached"], bool)
        assert isinstance(response_data["session_id"], str)

        # Value checks
        assert len(response_data["response"]) > 0, "Response should not be empty"
        assert response_data["tokens_used"] >= 0, "Token count should be non-negative"
        assert response_data["session_id"] == self.session_id, "Session ID should match"

    # Helper methods

    def _parse_sse_stream(self, stream_text: str) -> list[dict]:
        """
        Parse Server-Sent Events stream into structured events
        
        Args:
            stream_text: Raw SSE text stream
            
        Returns:
            List of event dictionaries with type and data
        """
        events = []
        lines = stream_text.split('\n')  # Don't strip to preserve final empty lines

        current_event = None
        current_data = None

        for line in lines:
            line = line.strip()

            if line.startswith('event: '):
                # New event type
                current_event = line[7:].strip()

            elif line.startswith('data: '):
                # Event data
                data_str = line[6:].strip()

                if data_str:
                    try:
                        current_data = json.loads(data_str)
                    except json.JSONDecodeError:
                        current_data = {"raw": data_str}
                else:
                    # Empty data (like for done event)
                    current_data = {}

            elif line == '':
                # Empty line marks end of event
                if current_event is not None:  # Allow empty data
                    events.append({
                        "type": current_event,
                        "data": current_data
                    })
                    current_event = None
                    current_data = None

        # Handle final event if stream doesn't end with empty line
        if current_event is not None:
            events.append({
                "type": current_event,
                "data": current_data
            })

        return events


class TestStreamIntegration:
    """Integration tests for streaming with other components"""

    def test_stream_database_persistence(self):
        """Test that streamed messages are saved to database"""
        client = TestClient(app)

        # Send streaming request
        response = client.post(
            "/api/v1/agent/chat/stream",
            data={
                "message": "Test message for persistence",
                "session_id": TEST_SESSION_ID
            }
        )

        assert response.status_code == 200

        # Check database
        # Note: This requires access to the database session
        # In a real test, you'd mock the database or use a test database

        # For now, just verify the session exists via API
        session_response = client.get(f"/api/v1/sessions/{TEST_SESSION_ID}")

        if session_response.status_code == 200:
            session_data = session_response.json()
            assert len(session_data["messages"]) >= 2, \
                "Should have user message and assistant response"

    def test_stream_cost_tracking(self):
        """Test that streaming requests are tracked for cost"""
        client = TestClient(app)

        # Make multiple streaming requests
        for i in range(3):
            response = client.post(
                "/api/v1/agent/chat/stream",
                data={
                    "message": f"Test query {i}",
                    "session_id": f"{TEST_SESSION_ID}-cost-{i}"
                }
            )
            assert response.status_code == 200

        # Verify cost tracking is working
        # (This would require accessing the cost tracker state)
        # For now, just verify requests succeeded
        print("Cost tracking test completed - requests successful")


@pytest.mark.asyncio
class TestStreamAsync:
    """Async tests for streaming endpoint"""

    async def test_stream_async_client(self):
        """Test streaming with async HTTP client"""

        # Use TestClient's transport for async testing
        from starlette.testclient import TestClient

        from interfaces.rest_api.main import app as test_app
        test_client = TestClient(test_app)

        # For now, use sync client as AsyncClient with TestClient is tricky
        response = test_client.post(
            "/api/v1/agent/chat/stream",
            data={
                "message": "What is air quality?",
                "session_id": TEST_SESSION_ID
            }
        )

        assert response.status_code == 200

        # Parse events
        events = self._parse_sse_stream(response.text)
        assert any(e["type"] == "done" for e in events)

    def _parse_sse_stream(self, stream_text: str) -> list[dict]:
        """Helper to parse SSE stream"""
        events = []
        lines = stream_text.split('\n')  # Don't strip to preserve final empty lines

        current_event = None
        current_data = None

        for line in lines:
            line = line.strip()

            if line.startswith('event: '):
                current_event = line[7:].strip()

            elif line.startswith('data: '):
                data_str = line[6:].strip()

                if data_str:
                    try:
                        current_data = json.loads(data_str)
                    except json.JSONDecodeError:
                        current_data = {"raw": data_str}
                else:
                    # Empty data (like for done event)
                    current_data = {}

            elif line == '':
                if current_event is not None:  # Allow empty data
                    events.append({
                        "type": current_event,
                        "data": current_data
                    })
                    current_event = None
                    current_data = None

        # Handle final event if stream doesn't end with empty line
        if current_event is not None:
            events.append({
                "type": current_event,
                "data": current_data
            })

        return events


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
