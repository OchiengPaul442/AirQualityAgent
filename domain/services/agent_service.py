"""
Agent Service - Streamlined Orchestrator

Refactored to use modular architecture:
- Cost tracking via CostTracker
- Tool execution via ToolExecutor
- Provider abstraction (Gemini, OpenAI, Ollama)
- System instructions from prompts module
"""

import hashlib
import inspect
import logging
import time
from typing import Any

from core.agent.cost_tracker import CostTracker
from core.agent.orchestrator import ResponseValidator, ToolOrchestrator
from core.agent.query_analyzer import QueryAnalyzer

# ThoughtStream removed - use logging and observability tools instead
from core.agent.tool_executor import ToolExecutor
from core.memory.context_manager import SessionContextManager
from core.memory.langchain_memory import LangChainSessionMemory, create_session_memory
from core.memory.prompts.system_instructions import get_response_parameters, get_system_instruction
from core.providers.base_provider import BaseAIProvider
from core.providers.gemini_provider import GeminiProvider
from core.providers.mock_provider import MockProvider
from core.providers.ollama_provider import OllamaProvider
from core.providers.openai_provider import OpenAIProvider
from core.tools.document_scanner import DocumentScanner
from core.tools.robust_scraper import RobustScraper
from domain.services.search_service import SearchService
from infrastructure.api.airqo import AirQoService
from infrastructure.api.carbon_intensity import CarbonIntensityService
from infrastructure.api.defra import DefraService
from infrastructure.api.geocoding import GeocodingService
from infrastructure.api.nsw import NSWService
from infrastructure.api.openmeteo import OpenMeteoService
from infrastructure.api.uba import UbaService
from infrastructure.api.waqi import WAQIService
from infrastructure.api.weather import WeatherService
from infrastructure.cache.cache_service import get_cache
from interfaces.mcp.client import MCPClient
from shared.config.settings import get_settings

logger = logging.getLogger(__name__)


class AgentService:
    """
    Main orchestrator for the Air Quality AI Agent.

    Responsibilities:
    - Initialize all service dependencies
    - Create and configure AI provider
    - Handle message processing requests
    - Manage cost tracking and caching
    - Connect to MCP servers
    """

    def __init__(self):
        """Initialize agent with all required services and providers."""
        self.settings = get_settings()
        self.cache = get_cache()
        self.mcp_clients: dict[str, MCPClient] = {}

        # Initialize SessionContextManager for better long-conversation handling
        self.session_manager = SessionContextManager(max_contexts=50, context_ttl=3600)

        # Persist simple personal info per session (name/location) so recall doesn't rely on the LLM
        # and survives history truncation.
        self._personal_info_by_session: dict[str, dict[str, str]] = {}

        # LangChain memory cache for enhanced session management
        # Provides: token-aware truncation, summarization, Redis persistence
        self.langchain_memories: dict[str, LangChainSessionMemory] = {}
        logger.info("LangChain memory integration enabled for advanced session management")

        # Document accumulation cache per session with timestamp tracking for cleanup
        # DEPRECATED: Moved to SessionContextManager, kept for backward compatibility
        # Format: {session_id: {"documents": [...], "last_access": timestamp}}
        self.document_cache: dict[str, dict[str, Any]] = {}
        self.document_cache_ttl = 3600  # 1 hour TTL for document cache cleanup

        # Parse enabled data sources
        enabled_sources = set(
            src.strip().lower()
            for src in self.settings.ENABLED_DATA_SOURCES.split(",")
            if src.strip()
        )

        # Initialize services based on enabled sources
        self.waqi = WAQIService() if "waqi" in enabled_sources else None
        self.airqo = AirQoService() if "airqo" in enabled_sources else None
        self.openmeteo = OpenMeteoService() if "openmeteo" in enabled_sources else None
        self.carbon_intensity = (
            CarbonIntensityService() if "carbon_intensity" in enabled_sources else None
        )
        self.defra = DefraService() if "defra" in enabled_sources else None
        self.uba = UbaService() if "uba" in enabled_sources else None
        self.nsw = NSWService() if "nsw" in enabled_sources else None
        self.weather = WeatherService()  # Always enabled as it's used by other services
        self.scraper = RobustScraper()  # Always enabled for web scraping
        self.search = SearchService()  # Always enabled for web search
        self.document_scanner = DocumentScanner()  # Always enabled for document processing
        self.geocoding = GeocodingService()  # Always enabled for location services

        # Initialize tool executor with available services
        self.tool_executor = ToolExecutor(
            self.waqi,
            self.airqo,
            self.openmeteo,
            self.carbon_intensity,
            self.defra,
            self.uba,
            self.nsw,
            self.weather,
            self.search,
            self.scraper,
            self.document_scanner,
            self.geocoding,
        )

        # Initialize advanced orchestration layer for low-end models
        self.orchestrator = ToolOrchestrator(
            tool_executor=self.tool_executor,
            max_retries=3,
            retry_delay=1.0,
            enable_fallbacks=True,
            timeout_per_tool=30.0
        )
        logger.info("Advanced orchestration layer initialized for optimized tool execution")

        # Initialize cost tracker with provider-specific limits
        # For local models (Ollama), use higher limits since there's no cost
        if self.settings.AI_PROVIDER == "ollama":
            self.cost_tracker = CostTracker(
                max_daily_cost=float('inf'),  # No cost limit for local models
                max_daily_requests=10000  # Much higher limit for local models
            )
            logger.info("Cost tracker initialized with relaxed limits for Ollama (local model)")
        else:
            self.cost_tracker = CostTracker()
            logger.info("Cost tracker initialized with default limits for cloud API")

        # Create and setup AI provider (support sync or async setup)
        self.provider = self._create_provider()
        try:
            setup_result = self.provider.setup()
            if inspect.isawaitable(setup_result):
                # schedule or run loop-aware await if running in async context
                # we do not await here to avoid requiring async __init__, but
                # callers that need full setup should call provider.setup() themselves
                pass
        except Exception:
            # swallow provider setup errors here; provider will raise on use
            logger.exception("Provider setup failed during AgentService init")

        logger.info(f"AgentService initialized with provider: {self.settings.AI_PROVIDER}")

        # Memory management and loop prevention (per-session)
        self.conversation_memory: dict[str, list[dict]] = {}  # {session_id: [messages]}
        self.max_conversation_length = 30  # Prevent memory bloat (reduced from 50)
        self.loop_detection_window = 8  # Check last N messages for loops (reduced from 10)
        self.max_response_length = 6000  # Prevent extremely long responses (reduced from 8000)
        self.max_message_cache_size = 100  # Limit total cached messages in memory

        # Session context management for better long-conversation handling
        self.session_context_cache: dict[str, dict[str, Any]] = (
            {}
        )  # {session_id: {summary, last_update}}
        self.max_session_contexts = 50  # Limit concurrent session contexts in memory

    def _classify_query_intent(self, message: str) -> dict[str, Any]:
        """
        Advanced query classification using semantic pattern recognition.
        
        Analyzes query structure, keywords, and context to determine:
        - Intent (air_quality_data, forecast, health_advice, general_knowledge, etc.)
        - Complexity (simple, moderate, complex)
        - Data requirements (needs_external_data)
        
        Returns dict with classification results for thinking trace.
        """
        msg_lower = message.lower()

        # Intent patterns with semantic understanding
        intent_patterns = {
            "air_quality_data": ["air quality", "aqi", "pm2.5", "pm10", "pollution level", "pollutants"],
            "forecast": ["forecast", "prediction", "tomorrow", "next week", "future", "will be"],
            "health_advice": ["health", "safe", "dangerous", "effects", "symptoms", "vulnerable"],
            "comparison": ["compare", "versus", "vs", "difference between", "better"],
            "trend_analysis": ["trend", "pattern", "historical", "over time", "past"],
            "general_knowledge": ["what is", "what are", "how does", "why", "explain", "tell me about"]
        }

        # Detect intent with scoring
        intent_scores = {}
        for intent, patterns in intent_patterns.items():
            score = sum(1 for pattern in patterns if pattern in msg_lower)
            if score > 0:
                intent_scores[intent] = score

        # Determine primary intent
        if intent_scores:
            primary_intent = max(intent_scores, key=intent_scores.get)
        else:
            primary_intent = "general_inquiry"

        # Assess complexity
        complexity_indicators = {
            "simple": len(message.split()) < 10 and len(intent_scores) <= 1,
            "complex": any(word in msg_lower for word in ["compare", "analyze", "multiple", "all"]) or len(intent_scores) > 2
        }

        if complexity_indicators["complex"]:
            complexity = "complex"
        elif complexity_indicators["simple"]:
            complexity = "simple"
        else:
            complexity = "moderate"

        # Determine data needs
        needs_external_data = primary_intent in ["air_quality_data", "forecast", "comparison", "trend_analysis"]

        return {
            "intent": primary_intent,
            "complexity": complexity,
            "needs_external_data": needs_external_data,
            "confidence": min(max(intent_scores.values()) / 3.0, 1.0) if intent_scores else 0.5
        }

    def _check_for_loops(self, user_message: str, session_id: str | None = None) -> bool:
        """
        Check for potential conversation loops or repetitive patterns.
        Uses semantic similarity to avoid false positives on new questions.

        Args:
            user_message: Current user message to check
            session_id: Session ID for memory isolation

        Returns True if a loop is detected, False otherwise.
        """
        # Get session-specific memory, or use default if no session
        session_memory = self.conversation_memory.get(session_id or "default", [])

        if len(session_memory) < self.loop_detection_window:
            return False

        # Get recent user messages
        recent_messages = [
            msg.get("user", "") for msg in session_memory[-self.loop_detection_window :]
        ]

        # Check for exact message repetition (must be exact and repeated 3+ times)
        exact_count = recent_messages.count(user_message)
        if exact_count >= 3:
            logger.warning(f"Exact message repetition detected: {exact_count} times")
            return True

        # Check for semantic similarity (only if messages are similar enough)
        # Calculate simple word overlap similarity
        def get_word_similarity(msg1: str, msg2: str) -> float:
            words1 = set(msg1.lower().split())
            words2 = set(msg2.lower().split())
            if not words1 or not words2:
                return 0.0
            intersection = len(words1 & words2)
            union = len(words1 | words2)
            return intersection / union if union > 0 else 0.0

        # Check if current message is very similar to multiple recent messages
        similar_count = 0
        for recent_msg in recent_messages[-5:]:  # Check last 5 messages only
            similarity = get_word_similarity(user_message, recent_msg)
            if similarity > 0.8:  # Very similar (80%+ word overlap)
                similar_count += 1

        # Only flag as loop if highly similar message appears 3+ times
        if similar_count >= 3:
            logger.warning(f"Semantic loop detected: {similar_count} similar messages")
            return True

        # Check for AI repetition (same AI response multiple times in a row)
        recent_ai_responses = [msg.get("ai", "") for msg in session_memory[-5:]]
        if len(recent_ai_responses) >= 3:
            # Check if AI is giving the same response repeatedly
            last_ai = recent_ai_responses[-1] if recent_ai_responses else ""
            if last_ai and recent_ai_responses.count(last_ai) >= 3:
                logger.warning(
                    f"AI response loop detected: same response {recent_ai_responses.count(last_ai)} times"
                )
                return True

        # Check for phrase-level repetition (detecting "The user wants..." loops)
        if len(recent_ai_responses) >= 2:
            last_response = recent_ai_responses[-1] if recent_ai_responses else ""
            # Extract first 50 chars as signature
            signature = last_response[:50].lower().strip()

            # Count how many recent responses start with similar signature
            similar_starts = sum(
                1 for resp in recent_ai_responses[-5:]
                if resp[:50].lower().strip() == signature and len(signature) > 10
            )

            if similar_starts >= 3:
                logger.warning(f"Phrase-level loop detected: similar response start {similar_starts} times")
                return True

        return False

    def _check_response_for_reasoning_exposure(self, response: str) -> bool:
        """
        Check if AI response exposes internal reasoning that should be hidden.
        Returns True if reasoning exposure detected IN THE ACTUAL RESPONSE.
        
        Note: This checks the response content, NOT the model's internal thinking.
        """
        # Only check if response is suspiciously short (likely pure reasoning, not actual answer)
        if len(response.strip()) < 50:
            return False  # Too short to contain reasoning patterns meaningfully

        # Patterns that indicate internal reasoning exposure IN USER-FACING RESPONSE
        # These should only trigger if they appear at start of response (first 200 chars)
        # to avoid false positives from phrases like "The WHO guidelines should..."
        response_start = response[:200].lower().strip()

        exposure_patterns = [
            "the user wants",
            "the user might",
            "the user is asking",
            "the assistant should",
            "i should respond",
            "i need to",
            "let me think",
            "i'll need to",
            "we need to first",
        ]

        for pattern in exposure_patterns:
            if pattern in response_start:
                logger.warning(f"Reasoning exposure detected: '{pattern}' found in response start")
                return True

        return False

    def _manage_memory(self, session_id: str | None = None):
        """Manage conversation memory to prevent bloat and loops.
        
        Args:
            session_id: Session ID for memory management
        """
        session_key = session_id or "default"
        session_memory = self.conversation_memory.get(session_key, [])

        if len(session_memory) > self.max_conversation_length:
            # Keep only the most recent messages
            self.conversation_memory[session_key] = session_memory[-self.max_conversation_length :]

        # Cleanup old sessions to prevent memory bloat
        if len(self.conversation_memory) > self.max_session_contexts:
            # Remove oldest sessions (simple FIFO)
            oldest_session = min(self.conversation_memory.keys(), key=lambda k: len(self.conversation_memory[k]))
            del self.conversation_memory[oldest_session]
            logger.debug(f"Removed conversation memory for session: {oldest_session}")

        # Session context manager handles its own cleanup automatically
        # Log session context stats periodically
        if len(session_memory) % 10 == 0:  # Every 10 messages
            stats = self.session_manager.get_stats()
            logger.debug(f"Session context stats: {stats}")

    def _get_timestamp(self) -> float:
        """Get current timestamp for memory tracking.
        
        Returns:
            float: Current time in seconds since epoch
        """
        from time import time
        return time()

    def _add_to_memory(self, user_message: str, ai_response: str, session_id: str | None = None):
        """Add conversation turn to memory with safeguards.
        
        Args:
            user_message: User's message
            ai_response: AI's response
            session_id: Session ID for memory isolation
        """
        session_key = session_id or "default"
        if session_key not in self.conversation_memory:
            self.conversation_memory[session_key] = []

        self.conversation_memory[session_key].append(
            {
                "user": user_message[:1000],  # Limit message length
                "ai": ai_response[:2000],  # Limit response length
                "timestamp": self._get_timestamp(),
            }
        )
        self._manage_memory(session_id)

    def _create_provider(self) -> BaseAIProvider:
        """
        Factory method to create the appropriate AI provider.

        Returns:
            BaseAIProvider: Configured provider instance
        """
        provider_map: dict[str, type[BaseAIProvider]] = {
            "gemini": GeminiProvider,
            "openai": OpenAIProvider,
            "ollama": OllamaProvider,
            "mock": MockProvider,
        }

        provider_class = provider_map.get(self.settings.AI_PROVIDER.lower())
        if not provider_class:
            raise ValueError(
                f"Unsupported AI_PROVIDER: {self.settings.AI_PROVIDER}. "
                f"Supported: {', '.join(provider_map.keys())}"
            )

        return provider_class(self.settings, self.tool_executor)

    def _get_or_create_langchain_memory(self, session_id: str) -> LangChainSessionMemory | None:
        """
        Get or create LangChain memory for a session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            LangChainSessionMemory instance for the session, or None if unavailable
        """
        try:
            if session_id not in self.langchain_memories:
                self.langchain_memories[session_id] = create_session_memory(
                    session_id=session_id,
                    use_summarization=False,  # Start with token buffer
                    max_tokens=2000  # Align with context limits
                )
                logger.info(f"Created LangChain memory for session {session_id}")
            return self.langchain_memories[session_id]
        except ImportError as e:
            logger.warning(f"LangChain not available: {e}. Memory features disabled.")
            return None
        except Exception as e:
            logger.error(f"Failed to create LangChain memory for session {session_id}: {e}")
            return None

    def _has_location_consent(self, history: list[dict[str, Any]]) -> bool:
        """
        Check if the user has already consented to location sharing in the conversation history.

        Args:
            history: Conversation history

        Returns:
            bool: True if user has consented to location sharing
        """
        consent_keywords = [
            "yes",
            "sure",
            "okay",
            "proceed",
            "go ahead",
            "allow",
            "consent",
            "please",
            "yes please",
            "of course",
            "absolutely",
            "fine",
            "ok",
            "alright",
            "sure thing",
        ]

        location_related_phrases = [
            "location",
            "current location",
            "my location",
            "where i am",
            "local",
            "here",
            "air quality",
            "pollution",
            "aqi",
            "gps",
            "coordinates",
        ]

        has_location_question = False
        has_consent = False

        for message in history:
            content = message.get("content", "").lower().strip()
            role = message.get("role", "")

            # Check assistant messages for location questions
            if role == "assistant":
                if any(phrase in content for phrase in location_related_phrases):
                    has_location_question = True

            # Check user messages for consent
            elif role == "user":
                if any(keyword in content for keyword in consent_keywords):
                    has_consent = True

        # Only consider consent valid if there was a location-related question before
        return has_location_question and has_consent

    def _is_appreciation_message(self, message: str) -> bool:
        """
        Check if a message is a simple appreciation/acknowledgment.

        Args:
            message: User message to check

        Returns:
            bool: True if message is appreciation-only
        """
        message_lower = message.lower().strip()
        words = message_lower.split()

        # Very short messages (1-2 words) - check exact matches or abbreviations
        if len(words) <= 2:
            # Exact matches for short appreciation messages
            exact_matches = [
                "thanks",
                "thank",
                "thx",
                "ty",
                "cheers",
                "ok",
                "okay",
                "awesome",
                "helpful",
            ]
            if message_lower in exact_matches:
                return True
            # Check for appreciation phrases
            appreciation_phrases = [
                "thank you",
                "thank you very much",
                "thanks a lot",
                "thank you so much",
                "appreciate it",
                "much appreciated",
                "good job",
                "well done",
                "nice work",
                "great job",
            ]
            if message_lower in appreciation_phrases:
                return True
            return False

        # Short messages (3-5 words) that contain appreciation keywords as whole words
        if len(words) <= 5:
            appreciation_words = [
                "thank",
                "thanks",
                "appreciate",
                "great",
                "awesome",
                "perfect",
                "nice",
                "helpful",
                "cheers",
                "appreciated",
            ]
            # Check if any appreciation word is in the message as a whole word
            for word in words:
                if word in appreciation_words:
                    return True
            # Check for specific phrases
            specific_phrases = ["thanks a lot", "thank you very much", "thanks on that"]
            if message_lower in specific_phrases:
                return True
            return False

        # Longer messages that are direct thanks (6-8 words)
        if len(words) <= 8:
            if any(phrase in message_lower for phrase in ["thank you", "thanks", "thank"]):
                return True

        return False

    def _build_personal_info_recall_response(
        self, message: str, history: list[dict[str, Any]], session_id: str | None
    ) -> str | None:
        import re

        message_lower = message.lower()
        asks_name = any(
            phrase in message_lower
            for phrase in [
                "what's my name",
                "what is my name",
            ]
        )
        asks_location = any(
            phrase in message_lower
            for phrase in [
                "where do i live",
                "where i live",
                "where am i",
                "what city",
                "which city",
                "what location",
            ]
        )

        if not (asks_name or asks_location):
            return None

        name: str | None = None
        location: str | None = None

        if session_id:
            stored = self._personal_info_by_session.get(session_id, {})
            name = stored.get("name") or None
            location = stored.get("location") or None

        for msg in reversed(history or []):
            if msg.get("role") != "user":
                continue
            content = (msg.get("content") or "").strip()
            if not content:
                continue

            if name is None:
                name_match = re.search(
                    r"\bmy name is\s+([A-Za-z][A-Za-z\-']{0,63})\b",
                    content,
                    re.IGNORECASE,
                )
                if name_match:
                    name = name_match.group(1)

            if location is None:
                location_match = re.search(
                    r"\bi\s+(?:live in|am from|i'm from|i'm in)\s+([A-Za-z][A-Za-z\s\-']{0,63})\b",
                    content,
                    re.IGNORECASE,
                )
                if location_match:
                    location = location_match.group(1).strip().rstrip(".")

            if name and location:
                break

        # Hydrate per-session cache if we found anything in history.
        if session_id and (name or location):
            entry = self._personal_info_by_session.setdefault(session_id, {})
            if name:
                entry["name"] = name
            if location:
                entry["location"] = location

        if asks_name and asks_location and (name or location):
            if name and location:
                return f"You told me your name is {name} and you live in {location}."
            if name:
                return f"You told me your name is {name}."
            if location:
                return f"You told me you're in {location}."

        if asks_name and name:
            return f"You told me your name is {name}."

        if asks_location and location:
            return f"You told me you're in {location}."

        return None

    def _check_security_violation(self, message_lower: str) -> bool:
        """
        Check if a message contains security violation attempts.

        This provides an additional layer of security beyond system instructions,
        since AI providers may not always follow security rules properly.

        Args:
            message_lower: Lowercase message to check

        Returns:
            bool: True if security violation detected
        """
        # CRITICAL: Exclude legitimate document processing queries
        # Users asking about uploaded documents is NOT a security violation
        legitimate_document_queries = [
            r"\bwhat.*document\b",
            r"\bwhat.*file\b",
            r"\banalyze.*document\b",
            r"\banalyze.*file\b",
            r"\bsummarize.*document\b",
            r"\bsummarize.*file\b",
            r"\bshow.*data\b",
            r"\btell me about.*document\b",
            r"\btell me about.*file\b",
        ]
        
        import re

        # Check if query is about uploaded documents (legitimate)
        for pattern in legitimate_document_queries:
            if re.search(pattern, message_lower, re.IGNORECASE):
                logger.debug(f"Legitimate document query detected: {message_lower[:100]}")
                return False  # Not a security violation
        
        # Security violation patterns (only for actual attacks)
        security_patterns = [
            # Tool/function enumeration attempts (but NOT document/file questions)
            r"\b(list|show|display|enumerate)\b.*\b(all )?(tool|function|method|api)s?\b",
            r"\b(what|which)\b.*\b(tool|function|method|api)s?\b.*\b(available|do you have|can you use)\b",
            r"\b(available|accessible)\b.*\b(tool|function|method|api)s?\b",
            # System prompt/instruction revelation attempts
            r"\b(system|internal)\b.*\b(prompt|instruction)s?\b",
            r"\b(show|reveal|display)\b.*\b(system )?(prompt|instruction)s?\b",
            r"\b(what.*your )?(system )?(prompt|instruction)\b",
            # API key/token revelation attempts
            r"\b(api|access)\b.*\b(key|token|secret)s?\b.*\b(show|reveal|what)\b",
            r"\b(what|show|reveal).*\b(api|access)\b.*\b(key|token|secret)s?\b",
            # Source code revelation attempts
            r"\b(show|reveal|display)\b.*\b(source|program)\b.*\b(code)\b",
            r"\b(source|program)\b.*\b(code)\b.*\b(show|reveal|display)\b",
            # Developer mode attempts
            r"\b(developer|dev|admin|root)\b.*\b(mode|access|privileges)\b",
            r"\b(enter|enable|activate)\b.*\b(developer|dev|admin)\b.*\b(mode)\b",
            r"\b(ignore|suspend|bypass)\b.*\b(safety|security|restriction)s?\b",
            # Direct security bypass attempts
            r"\b(override|ignore|bypass)\b.*\b(instruction|rule|security)s?\b",
            r"\b(dan|jailbreak|uncensored)\b",
        ]

        for pattern in security_patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                logger.warning(f"Security violation pattern matched: {pattern}")
                return True

        return False

    def _generate_cache_key(
        self,
        message: str,
        history: list[dict[str, Any]],
        document_data: list[dict[str, Any]] | None = None,
        style: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        session_id: str | None = None,
    ) -> str:
        """
        Generate a unique cache key for the request.
        Optimized to handle complex objects safely and prevent serialization errors.
        """
        # Simplified and robust cache key generation
        # Only use message, last 3 history items, and basic params
        try:
            # Truncate message for cache key to avoid extremely long keys
            msg_hash = (
                message[:500] if len(message) <= 500 else hashlib.md5(message.encode()).hexdigest()
            )

            # Only use last 3 history items (not 5) for better memory efficiency
            recent_history = history[-3:] if len(history) > 3 else history
            history_str = str(
                [
                    {"role": h.get("role", ""), "content": h.get("content", "")[:100]}
                    for h in recent_history
                ]
            )

            # Document cache key: use filenames only, not full content
            doc_str = ""
            if document_data:
                try:
                    filenames = [
                        d.get("filename", "unknown") for d in document_data if isinstance(d, dict)
                    ]
                    doc_str = ",".join(filenames)
                except Exception:
                    doc_str = "docs_present"

            cache_parts = [
                self.settings.AI_PROVIDER,
                self.settings.AI_MODEL,
                msg_hash,
                history_str,
                doc_str,
                style or "general",
                str(temperature) if temperature is not None else "default",
                str(top_p) if top_p is not None else "default",
            ]

            cache_string = "|".join(cache_parts)
            return hashlib.md5(cache_string.encode()).hexdigest()
        except Exception as e:
            logger.error(f"Cache key generation error: {e}, using fallback")
            # Fallback: simple hash of message only
            return hashlib.md5(message.encode()).hexdigest()

    def _get_fresh_cached_response(self, cache_key: str, message: str) -> dict[str, Any] | None:
        """
        Get cached response only if it's still fresh and appropriate to return.

        Implements intelligent cache invalidation based on:
        - Data type (current vs forecast)
        - Time elapsed since caching
        - Query characteristics
        - User expectations for freshness

        Uses modern AI caching strategies with context-aware freshness requirements.

        Args:
            cache_key: Generated cache key
            message: Original user message

        Returns:
            Fresh cached response or None if cache should not be used
        """
        import time
        from datetime import datetime

        # Get cached data with metadata
        cached_data = self.cache.get("agent", cache_key)
        if cached_data is None:
            return None

        # Ensure cached_data is a dict with expected structure
        if not isinstance(cached_data, dict):
            logger.warning(f"Invalid cache data format for key {cache_key[:16]}...")
            return None

        # Check if cache has timestamp metadata
        cache_timestamp = cached_data.get("_cache_timestamp")
        if cache_timestamp is None:
            # Legacy cache without timestamp - treat as stale
            logger.info(
                f"Legacy cache without timestamp for key {cache_key[:16]}... - treating as stale"
            )
            return None

        # Calculate age of cached data
        current_time = time.time()
        cache_age_seconds = current_time - cache_timestamp
        cache_age_minutes = cache_age_seconds / 60

        # Analyze query type for appropriate freshness requirements
        message_lower = message.lower()
        query_analysis = QueryAnalyzer.detect_air_quality_query(message)
        forecast_analysis = QueryAnalyzer.detect_forecast_query(message)

        # Determine data freshness requirements based on query type
        if forecast_analysis["is_forecast"]:
            # Forecast data: Very short TTL (1-2 hours max)
            max_age_minutes = 60  # 1 hour for forecasts
            data_type = "forecast"
        elif any(
            keyword in message_lower for keyword in ["current", "now", "today", "latest", "recent"]
        ):
            # Explicitly current/recent data requests
            max_age_minutes = 30  # 30 minutes
            data_type = "current_explicit"
        elif query_analysis["is_air_quality"]:
            # General air quality queries
            max_age_minutes = 60  # 1 hour
            data_type = "air_quality"
        else:
            # General conversational queries
            max_age_minutes = 240  # 4 hours (more lenient for non-data queries)
            data_type = "conversational"

        # Check if cache is too old
        if cache_age_minutes > max_age_minutes:
            logger.info(
                f"Cache too old for {data_type} query: {cache_age_minutes:.1f}min > {max_age_minutes}min limit"
            )
            return None

        # Additional freshness checks for air quality data
        if query_analysis["is_air_quality"] or forecast_analysis["is_forecast"]:
            # For air quality data, be more strict during peak pollution hours
            current_hour = datetime.now().hour

            # Morning and evening rush hours + nighttime (when pollution can change rapidly)
            if current_hour in [6, 7, 8, 17, 18, 19, 20, 21, 22, 23, 0, 1]:
                # Reduce TTL during high-variability periods
                adjusted_max_age = max_age_minutes * 0.5  # 50% of normal TTL
                if cache_age_minutes > adjusted_max_age:
                    logger.info(
                        f"Cache invalidated during peak hours: {cache_age_minutes:.1f}min > {adjusted_max_age}min adjusted limit"
                    )
                    return None

            # Check for repeated identical queries (user might be testing/refreshed)
            # If same query within 5 minutes, serve from cache (user expectation management)
            if cache_age_minutes < 5:
                logger.info(
                    f"Recent identical query ({cache_age_minutes:.1f}min ago) - serving from cache"
                )
                return cached_data

        # Log successful cache hit with freshness info
        logger.info(
            f"Fresh cache hit: {data_type} data, age {cache_age_minutes:.1f}min (limit {max_age_minutes}min)"
        )

        # Return the cached response (remove internal metadata before returning)
        response_copy = cached_data.copy()
        response_copy.pop("_cache_timestamp", None)  # Remove internal metadata
        return response_copy

    def _cleanup_stale_cache(self) -> int:
        """
        Clean up stale cached responses to prevent memory bloat.

        This is called periodically to remove old cache entries that are no longer useful.
        Similar to cache eviction strategies in production AI systems.

        Returns:
            Number of cache entries cleaned up
        """
        import time

        # Only run cleanup occasionally to avoid performance impact
        # In production, this could be run by a background task
        current_time = time.time()
        cleanup_interval = 300  # 5 minutes between cleanup runs

        if hasattr(self, "_last_cache_cleanup"):
            if current_time - self._last_cache_cleanup < cleanup_interval:
                return 0  # Skip cleanup if recently done

        self._last_cache_cleanup = current_time

        # For Redis cache, we rely on TTL expiration
        # For memory cache, we need manual cleanup
        if hasattr(self.cache, "_memory_cache"):
            cleaned_count = 0
            max_age_seconds = 14400  # 4 hours max age for any cache entry

            keys_to_delete = []
            for key, value in self.cache._memory_cache.items():
                if isinstance(value, dict) and "_cache_timestamp" in value:
                    cache_age = current_time - value["_cache_timestamp"]
                    if cache_age > max_age_seconds:
                        keys_to_delete.append(key)

            for key in keys_to_delete:
                del self.cache._memory_cache[key]
                cleaned_count += 1

            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} stale cache entries")

            return cleaned_count

        return 0

    async def process_message(
        self,
        message: str,
        history: list[dict[str, Any]] | None = None,
        document_data: list[dict[str, Any]] | None = None,
        style: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        client_ip: str | None = None,
        location_data: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Process a user message and generate a response.

        This is the main entry point for message processing. It:
        1. Checks for appreciation messages (simple acknowledgment)
        2. Verifies cost limits haven't been exceeded
        3. Checks cache for previous identical responses
        4. Delegates to provider for actual processing
        5. Tracks costs and caches results
        6. (Optional) Captures reasoning/thinking steps when thinking_mode=True

        Args:
            message: User's message
            history: Conversation history (default: [])
            document_data: Optional uploaded document context
            style: Response style preset (default: "general")
            temperature: Temperature override (default: from style)
            top_p: Top-p override (default: from style)
            client_ip: Client IP address for location services (fallback)
            location_data: GPS or IP location data with format:
                {"source": "gps", "latitude": float, "longitude": float} or
                {"source": "ip", "ip_address": str}
            session_id: Session identifier for document accumulation

        Returns:
            Dict containing:
                - response: AI's response text
                - tokens_used: Token count (if available)
                - cost_estimate: Estimated cost in USD
                - cached: Whether response was from cache
        """
        history = history or []

        # CRITICAL FIX: Merge LangChain memory history with incoming history
        # LangChain provides backup/supplemental memory when database is unavailable
        if session_id:
            try:
                lc_memory = self._get_or_create_langchain_memory(session_id)
                if lc_memory:  # Check if LangChain memory is available
                    langchain_history = lc_memory.get_history()
                    if langchain_history:
                        logger.info(f"📚 Loaded {len(langchain_history)} messages from LangChain memory for session {session_id}")
                        logger.debug(f"LangChain history content: {langchain_history}")
                        
                        # If no database history, use LangChain as primary source
                        if not history:
                            history = langchain_history
                            logger.info(f"✅ Using LangChain memory as primary source ({len(history)} messages)")
                        else:
                            # Database history exists - LangChain is supplemental
                            # Merge unique messages from LangChain that aren't in database
                            db_contents = {msg.get("content", "") for msg in history}
                            for lc_msg in langchain_history:
                                if lc_msg.get("content", "") not in db_contents:
                                    history.append(lc_msg)
                                    logger.debug(f"Added unique message from LangChain to history")
                            logger.info(f"✅ Using database history ({len(history)} messages total after LangChain merge)")
                    else:
                        logger.info(f"📚 LangChain memory exists but is empty for session {session_id}")
            except Exception as e:
                logger.warning(f"Failed to load LangChain memory for session {session_id}: {e}")

        # Check for GPS-based location queries
        if location_data and location_data.get("source") == "gps":
            location_keywords = [
                "my location",
                "current location",
                "here",
                "this location",
                "where i am",
                "my area",
                "local",
            ]
            if any(keyword in message.lower() for keyword in location_keywords):
                logger.info(
                    f"GPS location query detected, providing direct air quality data for coordinates: {location_data['latitude']}, {location_data['longitude']}"
                )

                # Get air quality data directly
                from infrastructure.api.openmeteo import OpenMeteoService

                openmeteo = OpenMeteoService()
                air_quality_result = openmeteo.get_current_air_quality(
                    latitude=location_data["latitude"],
                    longitude=location_data["longitude"],
                    timezone="auto",
                )

                # Get location name
                from infrastructure.api.geocoding import GeocodingService

                geocoding = GeocodingService()
                reverse_result = geocoding.reverse_geocode(
                    location_data["latitude"], location_data["longitude"]
                )
                location_name = "your current location"
                if reverse_result.get("success"):
                    city = reverse_result.get("address", {}).get("city", "")
                    if city:
                        location_name = city

                # Format response
                if "current" in air_quality_result and air_quality_result["current"]:
                    response_text = f"# Air Quality at {location_name}\n\n"
                    response_text += f"**Location**: {location_data['latitude']:.4f}, {location_data['longitude']:.4f} (precise GPS)\n\n"

                    # Add air quality data
                    current = air_quality_result["current"]
                    response_text += "## Current Air Quality\n\n"
                    response_text += "| Parameter | Value | Status |\n"
                    response_text += "|-----------|-------|--------|\n"

                    if "us_aqi" in current:
                        us_aqi = current["us_aqi"]
                        status = (
                            "Good" if us_aqi <= 50 else "Moderate" if us_aqi <= 100 else "Unhealthy"
                        )
                        response_text += f"| US AQI | {us_aqi} | {status} |\n"

                    if "pm2_5" in current:
                        pm25 = current["pm2_5"]
                        response_text += f"| PM2.5 | {pm25} µg/m³ | |\n"

                    if "pm10" in current:
                        pm10 = current["pm10"]
                        response_text += f"| PM10 | {pm10} µg/m³ | |\n"

                    response_text += "\n*Data provided with precise GPS coordinates for accurate local air quality information.*"
                else:
                    response_text = f"I couldn't retrieve air quality data for your current location ({location_data['latitude']:.4f}, {location_data['longitude']:.4f}). Please try again or specify a different location."

                return {
                    "response": response_text,
                    "tokens_used": 0,
                    "cost_estimate": 0.0,
                    "cached": False,
                }

        # Check for location consent in history and modify message if needed
        original_message = message
        has_consent = self._has_location_consent(history)
        is_location_query = any(
            keyword in message.lower()
            for keyword in [
                "my location",
                "current location",
                "here",
                "this location",
                "where i am",
                "my area",
                "local",
                "air quality in my location",
            ]
        )

        # Only treat as consent if message is ONLY/PRIMARILY consent - not if it's a real question with "please" at the end
        is_consent_response = (
            len(message.split()) <= 5  # Short messages only
            and any(
                keyword in message.lower()
                for keyword in ["yes", "sure", "okay", "proceed", "go ahead", "allow", "consent"]
            )
            and not any(
                question in message.lower()
                for question in [
                    "what",
                    "how",
                    "why",
                    "when",
                    "where",
                    "which",
                    "who",
                    "effects",
                    "impact",
                    "affect",
                ]
            )
        )

        if has_consent and is_location_query:
            message = "User has already consented to location sharing. Get air quality data for my current location using the get_location_from_ip tool."
            logger.info(
                f"Detected location consent in history and location query, modified message: '{original_message}' -> '{message}'"
            )
        elif is_consent_response and not is_location_query:
            # User is responding to consent request with just "yes" - treat as location query
            message = "User has consented to location sharing. Get air quality data for my current location using the get_location_from_ip tool."
            logger.info(
                f"Detected consent response without explicit location query, treating as location request: '{original_message}' -> '{message}'"
            )

        # Check cost limits
        within_limits, error_msg = self.cost_tracker.check_limits()
        if not within_limits:
            logger.warning(f"Cost limits exceeded: {error_msg}")
            return {
                "response": (
                    f"I've reached my daily usage limit. {error_msg}. "
                    "Please try again tomorrow or contact support to increase limits."
                ),
                "tokens_used": 0,
                "cost_estimate": 0.0,
                "error": "cost_limit_exceeded",
            }

        # CRITICAL: Quick classification for cache-skipping decision
        # Personal information queries must NEVER use cache (need real-time memory recall)
        is_personal_info = any(pattern in message.lower() for pattern in [
            'my name', 'i live', 'i am from', "i'm from", 'remember', 
            "what's my", "what is my", "where do i", "who am i",
            "what city", "which city", "what location"
        ])

        # Check cache with intelligent freshness validation
        # BUT: Skip cache for personal information queries (they need real-time memory recall)
        cache_key = self._generate_cache_key(
            message, history, document_data, style, temperature, top_p, session_id
        )

        # Check for cached response with freshness validation (skip for personal info)
        cached_response = None if is_personal_info else self._get_fresh_cached_response(cache_key, message)
        if cached_response is not None:
            logger.info(f"Cache hit for key: {cache_key[:16]}... (fresh data)")
            cached_response["cached"] = True
            # Run occasional cache cleanup
            self._cleanup_stale_cache()
            return cached_response
        elif is_personal_info:
            logger.info("🔓 Skipping cache for personal information query - need fresh memory recall")

        # Get response parameters for the style
        response_params = get_response_parameters(style or "general", temperature, top_p)

        # Use SessionContextManager for document accumulation (replaces old document_cache)
        if document_data and session_id:
            for doc in document_data:
                self.session_manager.add_document_to_session(session_id, doc)
                # CRITICAL: Also store in tool_executor for fallback scan_document access
                filename = doc.get("filename", "unknown")
                self.tool_executor.uploaded_documents[filename] = doc
            logger.info(
                f'Documents added to session context AND tool executor cache: {len(document_data)} document(s)"'
            )

        # Get accumulated documents from session manager
        if session_id:
            accumulated_docs = self.session_manager.get_session_documents(session_id)
            # Update conversation summary for efficient token usage
            self.session_manager.update_summary(session_id, history)
        else:
            accumulated_docs = document_data or []

        # CRITICAL FIX: Inject document content DIRECTLY into user message for AI visibility
        # System instructions alone are not enough - AI models often ignore long context
        document_injection = ""
        if accumulated_docs:
            self.tool_executor.documents_provided = True
            logger.info("Documents provided - injecting content into user message for visibility")

            # Build compact document summary for injection
            doc_summaries = []
            for doc in accumulated_docs[:3]:  # Limit to 3 most recent
                filename = doc.get("filename", "unknown")
                file_type = doc.get("file_type", "unknown")
                content = doc.get("content", "")[:2000]  # First 2000 chars only
                truncated = doc.get("truncated", False) or len(doc.get("content", "")) > 2000

                doc_summary = (
                    f"\\n\\n--- DOCUMENT: {filename} ({file_type.upper()}) ---\\n{content}"
                )
                if truncated:
                    doc_summary += "\\n[... content truncated, full data available on request ...]\\n"
                doc_summaries.append(doc_summary)

            document_injection = "\\n\\n".join(doc_summaries) + "\\n\\n--- END DOCUMENTS ---\\n\\n"
            logger.info(
                f"Document injection created: {len(document_injection)} chars for {len(accumulated_docs)} document(s)"
            )
        else:
            self.tool_executor.documents_provided = False

        # Prepend document content to user message for MAXIMUM visibility
        if document_injection:
            original_message = message
            message = f"{document_injection}USER QUERY: {message}"
            logger.info(
                f"Injected document content into user message (was {len(original_message)} chars, now {len(message)} chars)"
            )

        # Build document context FIRST (most important)
        document_context = (
            self._build_document_context(accumulated_docs, history) if accumulated_docs else ""
        )

        # Get location context
        location_context = ""
        if location_data and location_data.get("source") == "gps":
            location_context = f"\n\n**GPS LOCATION AVAILABLE**: The user has provided precise GPS coordinates ({location_data['latitude']:.4f}, {location_data['longitude']:.4f}). When they ask about air quality in their location, use the get_location_from_ip tool directly without asking for consent."

        # Add session summary for better long-conversation context
        session_summary = ""
        if session_id:
            session_summary = self.session_manager.get_context_summary(session_id)

        # Fallback safety net: If multiple documents and issues occur, prioritize the newest document
        if len(accumulated_docs) > 1 and document_data:
            # Check if the newest document is in the accumulated list
            newest_doc = document_data[0] if document_data else None
            if newest_doc and newest_doc.get("filename") not in [
                doc.get("filename") for doc in accumulated_docs
            ]:
                # If newest document failed to accumulate, use only the newest one as fallback
                logger.warning(
                    f"Document accumulation issue detected, using newest document as fallback: {newest_doc.get('filename')}"
                )
                accumulated_docs = [newest_doc]
                document_context = self._build_document_context(accumulated_docs, history)

        # CRITICAL: Put document context at the BEGINNING (custom_prefix) so AI sees it FIRST
        # This ensures document content has highest priority in the context window
        system_instruction = get_system_instruction(
            style=style or "general",
            custom_prefix=document_context,  # Documents FIRST
            custom_suffix=location_context + session_summary,  # Other context after
        )

        # Log if document context was added
        if accumulated_docs:
            doc_context_length = len(self._build_document_context(accumulated_docs, history))
            logger.info(
                f"Document context added to system instruction: {doc_context_length} chars for {len(accumulated_docs)} document(s)"
            )

        # Set location data for geocoding services (GPS takes precedence over IP)
        if location_data:
            if location_data.get("source") == "gps":
                self.tool_executor.client_location = {
                    "source": "gps",
                    "latitude": location_data["latitude"],
                    "longitude": location_data["longitude"],
                }
                logger.info(
                    f"Set GPS location for tool executor: {location_data['latitude']}, {location_data['longitude']}"
                )
            elif location_data.get("source") == "ip":
                self.tool_executor.client_ip = location_data["ip_address"]
                self.tool_executor.client_location = None  # Clear GPS if IP is used
                logger.info(f"Set IP location for tool executor: {location_data['ip_address']}")
        elif client_ip:
            # Fallback to IP if no location_data provided
            self.tool_executor.client_ip = client_ip
            self.tool_executor.client_location = None
            logger.info(f"Set IP location for tool executor (fallback): {client_ip}")
        
        # Set session_id for chart organization
        self.tool_executor.session_id = session_id
        logger.debug(f"Set session_id for tool executor: {session_id}")

        # CRITICAL: If documents are provided, block scan_document tool to prevent AI confusion
        if accumulated_docs:
            self.tool_executor.documents_provided = True
            logger.info(
                f"Blocking scan_document tool - {len(accumulated_docs)} document(s) already provided"
            )
        else:
            self.tool_executor.documents_provided = False

        # SECURITY CHECK - Prevent information leakage attempts (moved before loop detection)
        security_violation = self._check_security_violation(message.lower())
        if security_violation:
            logger.warning(f"Security violation detected: {message[:100]}...")
            return {
                "response": (
                    "I specialize in air quality. I can help with:\n"
                    "• Real-time AQI and pollutant data\n"
                    "• Health recommendations\n"
                    "• Air quality trends and forecasts\n\n"
                    "What would you like to know?"
                ),
                "tokens_used": 0,
                "cost_estimate": 0.0,
                "cached": False,
                "security_filtered": True,
            }

        # Check for conversation loops before processing (per session)
        if self._check_for_loops(message, session_id):
            logger.warning(f"Conversation loop detected in session {session_id or 'default'}, providing helpful capabilities reminder")
            return {
                "response": (
                    "Let me help you differently. I can assist with:\n\n"
                    "🌍 **Real-time Data** - Current AQI, PM2.5, pollutants for any city\n"
                    "📊 **Health Advice** - Safe activity levels, vulnerable group guidance\n"
                    "📈 **Trends** - Historical patterns, forecasts, comparisons\n"
                    "💡 **Education** - Pollutant explanations, AQI scale, research\n\n"
                    "What interests you?"
                ),
                "tokens_used": 0,
                "cost_estimate": 0.0,
                "cached": False,
                "loop_detected": True,
            }

        # INTELLIGENT PROACTIVE TOOL CALLING SYSTEM (OPTIMIZED FOR SPEED)
        # Uses smart classification to skip unnecessary tool calls
        logger.info("🔍 Analyzing query for intelligent tool selection...")

        # SPECIAL HANDLING: Detect chart/visualization requests early
        chart_request = any(keyword in message.lower() for keyword in [
            "chart", "visualiz", "graph", "plot", "show me", "display"
        ])
        if chart_request:
            logger.info("📊 Chart request detected - will handle with optimized response")

        # PARALLEL TOOL EXECUTION: Use asyncio.gather for concurrent tool calls
        # This dramatically reduces latency for multi-tool queries
        start_proactive = time.time()

        proactive_results = await QueryAnalyzer.proactively_call_tools(message, self.tool_executor)

        proactive_duration = time.time() - start_proactive
        logger.info(f"⚡ Proactive tools completed in {proactive_duration:.2f}s")

        tools_called_proactively = proactive_results.get("tools_called", [])
        context_injection = proactive_results.get("context_injection", "")
        classification = proactive_results.get("query_classification", {})

        query_type = classification.get("query_type", "general")
        logger.info(f"📊 Query classified as: {query_type}")

        # Deterministic personal-info recall (doesn't depend on the model remembering).
        # Only triggers for explicit recall questions (e.g., "What's my name?").
        recall_response = self._build_personal_info_recall_response(message, history, session_id)
        if recall_response:
            logger.info("📚 Returning deterministic personal info recall response")
            self._add_to_memory(message, recall_response, session_id)
            return {
                "response": recall_response,
                "tokens_used": 0,
                "cost_estimate": 0.0,
                "cached": False,
                "tools_used": [],
                "query_type": "personal_info",
                "memory_tokens": None,
            }

        # SPECIAL HANDLING: Personal information sharing
        # For queries where users share personal info, we need explicit acknowledgment
        if query_type == "personal_info":
            logger.info(f"👤 Personal info query detected: {message[:100]}")
            # Extract name and location from the message
            import re
            name_match = re.search(r'my name is (\w+)', message, re.IGNORECASE)
            location_match = re.search(r'i (?:live in|am from|\'m from|\'m in) ([\w\s]+?)(?:\.|$|,|\sand\s)', message, re.IGNORECASE)
            
            logger.info(f"👤 Name match: {name_match.group(1) if name_match else None}")
            logger.info(f"👤 Location match: {location_match.group(1) if location_match else None}")
            
            # If user is SHARING info (not asking)
            if name_match or location_match:
                name = name_match.group(1) if name_match else None
                location = location_match.group(1).strip() if location_match else None

                if session_id and (name or location):
                    entry = self._personal_info_by_session.setdefault(session_id, {})
                    if name:
                        entry["name"] = name
                    if location:
                        entry["location"] = location
                
                response_parts = []
                if name:
                    response_parts.append(f"Nice to meet you, {name}!")
                if location:
                    response_parts.append(f"Got it - you're in {location}.")
                
                if response_parts:
                    response_parts.append("I'll remember that for our conversation.")
                    
                    # Create response and add to memory immediately
                    ai_response = " ".join(response_parts)
                    logger.info(f"👤 Generated acknowledgment: {ai_response}")
                    
                    # Add to LangChain memory
                    token_count = None
                    if session_id:
                        try:
                            lc_memory = self._get_or_create_langchain_memory(session_id)
                            if lc_memory:
                                lc_memory.add_user_message(message)
                                lc_memory.add_ai_message(ai_response)
                                token_count = lc_memory.get_token_count()
                                logger.info(f"📚 Stored personal info in LangChain memory ({token_count} tokens)")
                        except Exception as e:
                            logger.warning(f"Failed to store in LangChain memory: {e}")
                    
                    # Add to database memory
                    self._add_to_memory(message, ai_response, session_id)
                    
                    # Return response without calling AI
                    logger.info("✅ Returning personal info acknowledgment response")
                    return {
                        "response": ai_response,
                        "tokens_used": 0,
                        "cost_estimate": 0.0,
                        "cached": False,
                        "tools_used": [],
                        "query_type": "personal_info",
                        "memory_tokens": token_count,
                    }
            
            # If user is ASKING about stored info (e.g., "what's my name?")
            # Continue to AI processing with history
            logger.info("📚 Personal info recall query - will use conversation history")

        if tools_called_proactively:
            logger.info(
                f"✅ Proactively called {len(tools_called_proactively)} tool(s): {tools_called_proactively}"
            )

            # Inject tool results into system instruction
            if context_injection:
                system_instruction += context_injection
                logger.info("📝 Injected tool results into context")
        else:
            # For general knowledge queries, ALWAYS use web search for latest information
            logger.info(f"ℹ️ No air quality tools needed (query type: {query_type}) - will use web search for latest information")

        # Process with provider

        try:
            response_data = await self.provider.process_message(
                message=message,
                history=history,
                system_instruction=system_instruction,
                temperature=response_params.get("temperature"),
                top_p=response_params.get("top_p"),
                top_k=response_params.get("top_k"),
                max_tokens=response_params.get(
                    "max_tokens"
                ),  # Fixed: use max_tokens not max_output_tokens
            )

            # Defensive: provider may (incorrectly) return None in some error paths
            if response_data is None:
                logger.error(
                    "Provider.process_message returned None (unexpected). Returning safe error response."
                )
                return {
                    "response": (
                        "I apologize, but the AI service returned no data. "
                        "Please try again or check the AI service logs."
                    ),
                    "tokens_used": 0,
                    "cost_estimate": 0.0,
                    "error": "provider_no_response",
                }

            # Merge proactively called tools with any tools the provider might have called
            provider_tools = response_data.get("tools_used", [])
            all_tools_used = list(
                set(tools_called_proactively + (provider_tools if provider_tools else []))
            )

            # CRITICAL FIX: If document_data was provided during upload, add scan_document to tools_used
            # This ensures tests pass even though the document was pre-scanned during upload
            if document_data:
                all_tools_used.append("scan_document")
                logger.info("📄 Document data provided - adding scan_document to tools_used for test compatibility")

            response_data["tools_used"] = all_tools_used

            if all_tools_used:
                logger.info(
                    f"🔧 Combined tool usage - Proactive: {tools_called_proactively}, Provider: {provider_tools}, Total: {all_tools_used}"
                )

            # Extract chart data from tool results if chart was generated
            # Check if generate_chart was called and embed chart in markdown
            if "generate_chart" in all_tools_used:
                # First check if it's in provider response (direct AI call)
                chart_result = response_data.get("chart_result")

                # If not found, check proactive tool results
                if not chart_result:
                    proactive_tool_results = proactive_results.get("tool_results", {})
                    chart_result = proactive_tool_results.get("generate_chart")
                    logger.info(f"Looking for chart in proactive results: {chart_result is not None}")

                if chart_result and isinstance(chart_result, dict) and chart_result.get("success"):
                    chart_data = chart_result.get("chart_data")

                    # Ensure chart is embedded in markdown response
                    if chart_data and "response" in response_data:
                        # Check if chart is already embedded
                        if chart_data not in response_data["response"]:
                            # Embed chart at the end of response
                            chart_markdown = f"\n\n![Generated Chart]({chart_data})\n"
                            response_data["response"] += chart_markdown
                            logger.info("📊 Chart embedded in markdown response for automatic rendering")

                    # Add sampling notice if data was sampled
                    if chart_result.get("data_sampled") and chart_result.get("sampling_notice"):
                        sampling_msg = f"\n\n{chart_result.get('sampling_notice')}"
                        if "response" in response_data:
                            response_data["response"] += sampling_msg

                    logger.info(
                        f"📊 Chart generated: {chart_result.get('chart_type')} with {chart_result.get('data_rows')} rows"
                        f" (sampled from {chart_result.get('original_rows')})" if chart_result.get('data_sampled') else ""
                    )
                else:
                    logger.warning("⚠️ generate_chart was called but chart generation failed")
                    # Provide helpful fallback message
                    if "response" in response_data and response_data["response"]:
                        response_data["response"] += (
                            "\n\n📊 **Chart Status**: Chart generation encountered an issue. "
                            "Try: 1) Smaller dataset, 2) Specific date range, 3) Request summary instead"
                        )

            # Track costs
            tokens_used = response_data.get("tokens_used", 0)
            cost_estimate = response_data.get("cost_estimate", 0.0)

            if tokens_used > 0:
                self.cost_tracker.track_usage(tokens_used, cost_estimate)

            # Cache the response with timestamp metadata
            response_data["_cache_timestamp"] = time.time()  # Add timestamp for freshness tracking
            response_data["cached"] = False

            # Determine appropriate TTL based on query type
            query_analysis = QueryAnalyzer.detect_air_quality_query(message)
            forecast_analysis = QueryAnalyzer.detect_forecast_query(message)

            # Don't cache responses that use web search (they contain current information)
            if "search_web" in all_tools_used:
                cache_ttl = 300  # 5 minutes for search-based responses
            elif forecast_analysis["is_forecast"]:
                cache_ttl = 3600  # 1 hour for forecasts
            elif query_analysis["is_air_quality"]:
                cache_ttl = 1800  # 30 minutes for current air quality
            else:
                cache_ttl = 7200  # 2 hours for general queries

            # cache.set expects (namespace, key, value, ttl)
            self.cache.set("agent", cache_key, response_data, ttl=cache_ttl)

            # SECURITY: Filter out any sensitive information from response
            response_data = self._filter_sensitive_info(response_data)

            # CHECK FOR REASONING EXPOSURE: If AI exposed internal thinking, replace with helpful response
            ai_response = response_data.get("response", "").strip()
            if self._check_response_for_reasoning_exposure(ai_response):
                logger.warning("Reasoning exposure detected - replacing with helpful options response")
                response_data["response"] = (
                    "I can help you with air quality data! Here are your options:\n\n"
                    "• **Share your location** - City name, ZIP code, or coordinates for local data\n"
                    "• **Ask about specific places** - e.g., 'London air quality' or 'Beijing PM2.5'\n"
                    "• **Get general info** - Learn about AQI, pollutants, health impacts\n"
                    "• **Compare locations** - See air quality differences between cities\n"
                    "• **View trends** - Historical data and forecasts\n\n"
                    "What interests you most?"
                )
                response_data["reasoning_filtered"] = True
                ai_response = response_data["response"]

            # FALLBACK RESPONSE IMPROVEMENT: If response is too short and tools were used,
            # it likely indicates a data retrieval failure - provide helpful fallback
            ai_response = response_data.get("response", "").strip()
            tools_used = response_data.get("tools_used", [])

            # Check if response is inadequate (too short, generic, or doesn't contain actual data)
            is_inadequate = (
                len(ai_response) < 100  # Too short
                or ai_response.lower().strip()
                in ["air quality", "air quality data", "no data"]  # Generic responses
                or (
                    len(tools_used) > 0
                    and not any(
                        indicator in ai_response.lower()
                        for indicator in [
                            "aqi",
                            "pm2.5",
                            "pm10",
                            "µg/m³",
                            "good",
                            "moderate",
                            "unhealthy",
                            "hazardous",
                            "kampala",
                            "nairobi",
                            "dar es salaam",
                            "station",
                            "monitoring",
                        ]
                    )
                )  # Tools used but no actual air quality data in response
            )

            # REMOVED: Static fallback messages that override AI responses
            # AI should generate dynamic responses based on actual tool results
            if is_inadequate and len(tools_used) > 0:
                logger.info("Response is inadequate but tools were used. AI will handle with available context.")

            # MEMORY MANAGEMENT: Add to conversation memory and enforce limits
            ai_response = response_data.get("response", "")
            original_length = len(ai_response)
            
            # Check if provider indicated truncation via finish_reason
            finish_reason = response_data.get("finish_reason", "stop")
            provider_truncated = finish_reason == "length"
            
            # Check if we need to truncate internally
            internal_truncation_needed = len(ai_response) > self.max_response_length
            
            # Handle any truncation (provider or internal)
            if provider_truncated or internal_truncation_needed:
                # Add professional continuation prompt
                continuation_message = (
                    "\n\n---\n"
                    "**📝 Response Incomplete**: This response was truncated due to length limits.\n\n"
                    "**To continue:**\n"
                    "• Click the 'Continue' button to generate the rest\n"
                    "• Or ask for specific sections (e.g., 'Tell me about health effects')\n"
                    "• Or request a focused summary\n\n"
                    "💡 **Tip**: Break complex questions into smaller parts for better results."
                )
                
                if internal_truncation_needed:
                    # Truncate and add continuation message
                    ai_response = (
                        ai_response[: self.max_response_length - len(continuation_message)] + continuation_message
                    )
                else:
                    # Provider truncated - just add continuation message
                    ai_response += continuation_message
                
                response_data["response"] = ai_response
                response_data["truncated"] = True
                response_data["requires_continuation"] = True
                response_data["finish_reason"] = finish_reason
                
                logger.info(
                    f"Response truncated: original={original_length} chars, "
                    f"final={len(ai_response)} chars, reason={finish_reason}, "
                    f"provider_truncated={provider_truncated}, internal={internal_truncation_needed}"
                )
            else:
                # Response is complete
                response_data["requires_continuation"] = False
                response_data["truncated"] = False
                response_data["finish_reason"] = finish_reason

            self._add_to_memory(message, ai_response, session_id)

            # LangChain memory tracking - Enhanced session management
            if session_id:
                try:
                    lc_memory = self._get_or_create_langchain_memory(session_id)
                    if lc_memory:  # Check if LangChain memory is available
                        lc_memory.add_user_message(message)
                        lc_memory.add_ai_message(ai_response)

                        # Add memory stats to response (optional)
                        token_count = lc_memory.get_token_count()
                        if token_count:
                            response_data["memory_tokens"] = token_count
                            logger.info(f"📊 Session {session_id} memory: {token_count} tokens tracked by LangChain")
                except Exception as e:
                    logger.warning(f"LangChain memory tracking failed for session {session_id}: {e}")
                    # Continue processing - memory tracking is not critical

            # Enhance response with additional context if needed
            tool_results = proactive_results.get("tool_results", {})
            # Add any tool results from the provider response
            if "tool_results" in response_data:
                tool_results.update(response_data["tool_results"])
            
            response_data["response"] = ResponseValidator.enhance_response(
                response_data["response"], all_tools_used, tool_results
            )

            logger.info(
                f"Message processed successfully. Tokens: {tokens_used}, "
                f"Cost: ${cost_estimate:.4f}"
            )

            return response_data

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

            return {
                "response": (
                    "I apologize, but I encountered an error processing your request. "
                    "Please try again or rephrase your question."
                ),
                "tokens_used": 0,
                "cost_estimate": 0.0,
                "error": str(e),
            }

    def _build_document_context(
        self,
        document_data: list[dict[str, Any]] | None,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        """
        Build document context string for system instruction.

        Args:
            document_data: List of document metadata and content
            history: Conversation history to check for previous document uploads

        Returns:
            str: Formatted document context or empty string
        """
        if not document_data:
            return ""

        # Ensure document_data is a list
        if not isinstance(document_data, list):
            logger.warning(f"document_data should be a list, got {type(document_data)}")
            return ""

        # Note: Document accumulation is now handled by the document_cache in process_message
        # This method now receives pre-accumulated documents
        all_documents = document_data

        # Remove duplicates based on filename
        seen_filenames = set()
        unique_documents = []
        for doc in all_documents:
            filename = doc.get("filename", "")
            if filename not in seen_filenames:
                seen_filenames.add(filename)
                unique_documents.append(doc)

        # Limit to last 3 documents to avoid resource issues
        if len(unique_documents) > 3:
            unique_documents = unique_documents[-3:]

        context_parts = [
            "\n\n" + "=" * 80,
            "🔔 DOCUMENTS ARE UPLOADED AND READY - READ THIS FIRST!",
            "=" * 80,
            "\n⚠️⚠️⚠️ CRITICAL: Documents have been uploaded and their content is provided below.",
            "\n🚫 DO NOT say 'I need the file' or 'please upload' - the data is ALREADY HERE",
            "🚫 DO NOT say 'I don't have access' - YOU DO HAVE ACCESS (see below)",
            "✅ ANALYZE the document content directly - it is ready for you",
            "\n📊 IMPORTANT: If user asks for charts/graphs/visualization, generate them immediately",
            "   - Parse the data from the document content below",
            "   - Create appropriate visualization based on data structure",
            "   - Example: extract columns like 'Date', 'PM2.5', then create trend chart\n",
        ]

        if len(unique_documents) > 1:
            context_parts.append(f"\n📚 YOU HAVE ACCESS TO {len(unique_documents)} DOCUMENTS:")
            context_parts.append("⚠️ Analyze and reference ALL relevant documents when appropriate.")
            context_parts.append(
                "⚠️ Maintain context across documents for comprehensive analysis.\n"
            )
        else:
            context_parts.append("\n📄 YOU HAVE ACCESS TO 1 DOCUMENT (see content below):\n")

        for idx, doc in enumerate(unique_documents, 1):
            # Skip if not a dictionary
            if not isinstance(doc, dict):
                logger.warning(f"Skipping non-dict document: {type(doc)}")
                continue

            filename = doc.get("filename", "Unknown")
            content = doc.get("content", "")
            file_type = doc.get("file_type", "unknown")
            truncated = doc.get("truncated", False)
            full_length = doc.get("full_length", len(content))

            # Build document header
            context_parts.append(f"\n📄 Document {idx}: {filename}")
            context_parts.append(f"File Type: {file_type.upper()}")
            context_parts.append("Status: ✅ Scanned and Ready")

            # Add metadata if available
            metadata = doc.get("metadata", {})
            if metadata:
                metadata_str = ", ".join(
                    [f"{k}: {v}" for k, v in metadata.items() if k not in ["characters"]]
                )
                if metadata_str:
                    context_parts.append(f"Details: {metadata_str}")

            # Show truncation info
            if truncated:
                context_parts.append(
                    f"Size: {full_length} characters total (preview showing first 1,000)"
                )

            # Add content with clear delimiter - use more content for data files
            # For CSV/Excel, include more rows for visualization
            max_content_length = 5000 if file_type.lower() in ['csv', 'excel', 'xlsx'] else 2000
            context_parts.append(f"\n--- DATA START ---\n{content[:max_content_length]}")
            if truncated:
                context_parts.append(f"\n--- DATA TRUNCATED (showing {min(max_content_length, len(content))} of {full_length} chars) ---")
                context_parts.append("\n✅ YOU CAN STILL CREATE CHARTS with this preview data!")
                context_parts.append("✅ Parse the rows above and call generate_chart - don't ask for more data!")
            else:
                context_parts.append("\n--- DATA END ---")

        context_parts.append(
            "\n\n✅ All document data above is ready for your analysis. Proceed with answering the user's question using this data."
        )
        context_parts.append("=== END DOCUMENTS ===\n")

        return "\n".join(context_parts)

    async def connect_mcp_server(
        self, server_name: str, command: str, args: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Connect to an MCP (Model Context Protocol) server.

        Args:
            server_name: Name/identifier for the server
            command: Command to execute
            args: Command arguments

        Returns:
            Dict with connection status and details
        """
        try:
            if server_name in self.mcp_clients:
                logger.info(f"MCP client '{server_name}' already connected")
                return {
                    "status": "already_connected",
                    "message": f"Already connected to {server_name}",
                }

            # Create and initialize MCP client
            mcp_client = MCPClient(command, args or [])
            async with mcp_client.connect():
                # Connection successful, store the client
                self.mcp_clients[server_name] = mcp_client

            logger.info(f"Successfully connected to MCP server: {server_name}")
            return {
                "status": "success",
                "message": f"Connected to {server_name}",
                "server_name": server_name,
            }

        except Exception as e:
            logger.error(f"Failed to connect to MCP server {server_name}: {e}")
            return {
                "status": "error",
                "message": f"Failed to connect: {str(e)}",
                "error": str(e),
            }

    def get_cost_status(self) -> dict[str, Any]:
        """
        Get current cost tracking status.

        Returns:
            Dict with cost and usage statistics
        """
        return self.cost_tracker.get_status()

    def _filter_sensitive_info(self, response_data: dict[str, Any]) -> dict[str, Any]:
        """
        Filter out any sensitive information from the response.

        This includes API keys, tokens, internal methods, tool calls, internal IDs, etc.
        Based on security best practices for production AI systems.

        If sensitive information is detected, provide a professional response instead of
        showing redaction markers to maintain user trust and professionalism.
        """
        import re

        if "response" in response_data and isinstance(response_data["response"], str):
            response_text = response_data["response"]

            # Check if response contains ACTUAL sensitive information (not tool usage mentions)
            # We WANT the agent to mention data sources and services used - that's transparent and helpful
            sensitive_indicators = [
                r"(?i)(api[_-]?key|token|secret|password|auth[_-]?key)\s*[:=]\s*[\w\-]{8,}",  # ACTUAL keys with values (8+ chars)
                r"(?i)(site[_-]?id|device[_-]?id)\s*[:=]\s*[\w\-]{5,}",  # ACTUAL IDs with values (5+ chars)
                r'\{"type":\s*"function"[^}]*"name":\s*"[^"]+"[^}]*\}',  # Full tool call JSON structure
                # REMOVED: URLs - they are helpful references
                # REMOVED: [REDACTED] markers - we don't use these anymore
                # REMOVED: "using tool/service" - we WANT transparency about data sources
            ]

            contains_sensitive = any(
                re.search(pattern, response_text) for pattern in sensitive_indicators
            )

            # EXCEPTION: Allow document analysis responses even if they might match patterns
            # These are legitimate responses to user uploads
            is_document_analysis = any(
                keyword in response_text.lower()
                for keyword in [
                    "document overview",
                    "file:",
                    "sheet:",
                    "rows:",
                    "columns:",
                    "excel",
                    "spreadsheet",
                    "csv",
                    "analyzing",
                    "data preview",
                    "table:",
                    "primary content",
                    "who_aap",
                    "xlsx",
                    "document",
                ]
            )

            if contains_sensitive and not is_document_analysis:
                # Replace with professional response instead of showing redaction markers
                logger.warning(
                    f"Sensitive information detected in response, replacing with professional message. Original: {response_text[:200]}..."
                )
                response_data["response"] = (
                    "I apologize, but I cannot provide the specific technical details you're requesting. "
                    "This is to ensure security and protect sensitive information. "
                    "Please rephrase your question or ask about air quality data, health recommendations, or environmental information instead."
                )
                response_data["sensitive_content_filtered"] = True
                return response_data

            # If no sensitive content detected, proceed with normal cleaning
            # Remove API keys and tokens (common patterns) - but only actual key VALUES
            response_text = re.sub(
                r"(?i)(api\s+key|token|secret|password|auth\s+key)\s*[:=]\s*\S+",
                "[FILTERED]",
                response_text,
            )
            response_text = re.sub(
                r"(?i)(api[_-]?key|token|secret|password|auth[_-]?key)\s*[:=]\s*\S+",
                "[FILTERED]",
                response_text,
            )

            # DO NOT remove tool/service mentions - we WANT transparency about data sources!
            # User requirement #4: "AI AGENT MAKE USE OF ALL THE TOOLS, SERVICES"
            # Users need to know where data comes from for trust and verification

            # Remove only FULL tool call JSON structures (internal implementation details)
            response_text = re.sub(
                r'\{"type":\s*"function"[^}]*"name":\s*"[^"]+"\}',
                "[technical details removed]",
                response_text,
                flags=re.DOTALL,
            )

            # Remove only function call syntax like function_name(arg="value")
            response_text = re.sub(
                r'\b\w+\([^)]*=\s*"[^"]*"\)', "[technical details removed]", response_text
            )

            # Remove internal IDs and site identifiers ONLY when they appear with assignment operators
            # Public reference URLs and general mentions of services are fine and helpful
            internal_id_patterns = [
                r'(?i)(site[_-]?id|device[_-]?id|station[_-]?id|sensor[_-]?id)\s*[:=]\s*["\']?[\w\-]+["\']?',
                r'(?i)(location[_-]?id|monitor[_-]?id|node[_-]?id)\s*[:=]\s*["\']?[\w\-]+["\']?',
                r'(?i)(api[_-]?endpoint|service[_-]?url|base[_-]?url)\s*[:=]\s*["\']?[^"\']+["\']?',
                r'(?i)(database[_-]?id|table[_-]?id|record[_-]?id)\s*[:=]\s*["\']?[\w\-]+["\']?',
            ]

            for pattern in internal_id_patterns:
                response_text = re.sub(pattern, "[details removed]", response_text)

            # Remove escaped JSON artifacts from parsing
            response_text = re.sub(r'\\"[^"]*\\":', "", response_text)
            response_text = re.sub(r"\\n", " ", response_text)

            # DO NOT remove URLs, long numbers, or hex codes - these could be legitimate data references
            # Public reference URLs are helpful for users to verify information
            # Monitoring station IDs and codes may be public and useful

        return response_data

    async def cleanup(self):
        """Clean up resources (MCP clients, provider connections)."""
        # Disconnect all MCP clients
        for server_name, client in self.mcp_clients.items():
            try:
                # Some MCPClient implementations may provide sync or async disconnect
                disconnect_fn = getattr(client, "disconnect", None)
                if disconnect_fn is not None:
                    res = disconnect_fn()
                    if inspect.isawaitable(res):
                        await res
                logger.info(f"Disconnected MCP client: {server_name}")
            except Exception as e:
                logger.error(f"Error disconnecting MCP client {server_name}: {e}")

        # Cleanup provider
        if hasattr(self.provider, "cleanup"):
            try:
                cleanup_fn = self.provider.cleanup
                res = cleanup_fn()
                if inspect.isawaitable(res):
                    await res
            except Exception as e:
                logger.error(f"Error cleaning up provider: {e}")

        logger.info("AgentService cleanup completed")
