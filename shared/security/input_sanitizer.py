"""
Input Sanitization Module - Prompt Injection Defense

Implements comprehensive input sanitization to prevent:
- Prompt injection attacks
- Jailbreaking attempts
- System prompt extraction
- Credential leakage
- Adversarial inputs

Based on OWASP LLM Security Best Practices and production testing.
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Patterns that indicate prompt injection attempts
BANNED_PATTERNS = [
    # Direct command overrides
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"disregard\s+(all\s+)?previous\s+(instructions|prompts)",
    r"forget\s+(all\s+)?previous\s+(instructions|context)",
    r"new\s+instructions?:?",
    r"system\s+prompt:?",
    r"you\s+are\s+now",
    r"act\s+as\s+(if\s+)?you",
    r"pretend\s+(to\s+)?be",
    r"from\s+now\s+on",
    r"roleplay\s+as",
    
    # Credential extraction attempts
    r"api[_\s-]?key",
    r"access[_\s-]?token",
    r"secret[_\s-]?key",
    r"password",
    r"credentials?",
    r"authorization\s+header",
    r"bearer\s+token",
    r"private[_\s-]?key",
    
    # System manipulation
    r"show\s+me\s+(your\s+)?system\s+prompt",
    r"what\s+(is|are)\s+(your\s+)?instructions",
    r"reveal\s+(your\s+)?prompt",
    r"display\s+(your\s+)?(system\s+)?instructions",
    r"print\s+(your\s+)?(system\s+)?prompt",
    r"echo\s+system",
    
    # Jailbreak attempts
    r"developer\s+mode",
    r"god\s+mode",
    r"sudo\s+mode",
    r"admin\s+mode",
    r"jailbreak",
    r"DAN\s+mode",  # "Do Anything Now"
    r"unrestricted\s+mode",
    
    # Context manipulation
    r"above\s+is\s+false",
    r"previous\s+(context|conversation)\s+is\s+(invalid|wrong)",
    r"reset\s+(your\s+)?memory",
    r"clear\s+(your\s+)?context",
    
    # Code injection attempts
    r"<script",
    r"<iframe",
    r"javascript:",
    r"eval\s*\(",
    r"exec\s*\(",
    r"__import__",
    r"subprocess\.",
    r"os\.system",
]

# Patterns for aggressive filtering (high false positive risk - use with caution)
SUSPICIOUS_PATTERNS = [
    r"\bsystem\b",  # Too broad, disabled by default
    r"\bprompt\b",  # Too broad, disabled by default
    r"\binstruction\b",  # Too broad, disabled by default
]

# Allowed security-related terms in legitimate queries
ALLOWED_CONTEXT = [
    "air quality system",
    "monitoring system",
    "alert system",
    "early warning system",
    "health protection system",
    "prompt action",
    "prompt response",
    "instructional materials",
    "instructions for",
]


class InputSanitizer:
    """
    Sanitizes user input to prevent prompt injection and other attacks.
    
    Features:
    - Pattern-based detection of injection attempts
    - Context-aware filtering (reduces false positives)
    - Configurable strictness levels
    - Detailed logging of suspicious inputs
    - Graceful degradation (sanitize vs reject)
    """
    
    def __init__(
        self,
        strictness: str = "balanced",  # "lenient", "balanced", "strict"
        log_suspicious: bool = True,
        redact_credentials: bool = True
    ):
        """
        Initialize the input sanitizer.
        
        Args:
            strictness: Detection sensitivity
                - "lenient": Only block obvious attacks
                - "balanced": Default, good balance of security and usability
                - "strict": Aggressive filtering, may have false positives
            log_suspicious: Log suspicious inputs for monitoring
            redact_credentials: Automatically redact detected credentials
        """
        self.strictness = strictness
        self.log_suspicious = log_suspicious
        self.redact_credentials = redact_credentials
        
        # Compile regex patterns for efficiency
        self.banned_regex = [
            re.compile(pattern, re.IGNORECASE) 
            for pattern in BANNED_PATTERNS
        ]
        
        self.suspicious_regex = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in SUSPICIOUS_PATTERNS
        ] if strictness == "strict" else []
        
        self.allowed_context_regex = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in ALLOWED_CONTEXT
        ]
    
    def sanitize(self, user_input: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Sanitize user input and return results.
        
        Args:
            user_input: Raw user input string
            session_id: Optional session ID for logging
            
        Returns:
            Dictionary with:
            - "sanitized": Cleaned input string
            - "is_safe": Boolean indicating if input is safe
            - "threats_detected": List of threat types detected
            - "original_length": Original input length
            - "sanitized_length": Sanitized input length
        """
        if not user_input or not isinstance(user_input, str):
            return {
                "sanitized": user_input,
                "is_safe": True,
                "threats_detected": [],
                "original_length": 0,
                "sanitized_length": 0
            }
        
        original_length = len(user_input)
        sanitized = user_input
        threats = []
        
        # Check for banned patterns
        for pattern in self.banned_regex:
            matches = pattern.findall(user_input)
            if matches:
                # Check if this is legitimate usage
                is_legitimate = self._is_legitimate_context(user_input, pattern)
                
                if not is_legitimate:
                    threat_type = self._categorize_threat(pattern.pattern)
                    threats.append(threat_type)
                    
                    # Log the attempt
                    if self.log_suspicious:
                        logger.warning(
                            f"Prompt injection attempt detected: {threat_type}",
                            extra={
                                "session_id": session_id,
                                "pattern": pattern.pattern,
                                "matches": matches,
                                "input_preview": user_input[:200]
                            }
                        )
                    
                    # Sanitize by redacting
                    sanitized = pattern.sub("[REDACTED]", sanitized)
        
        # Check for suspicious patterns (strict mode only)
        if self.strictness == "strict":
            for pattern in self.suspicious_regex:
                if pattern.search(sanitized):
                    is_legitimate = self._is_legitimate_context(sanitized, pattern)
                    if not is_legitimate:
                        threats.append("suspicious_pattern")
                        sanitized = pattern.sub("[FILTERED]", sanitized)
        
        # Redact potential credentials
        if self.redact_credentials:
            sanitized = self._redact_credentials(sanitized)
        
        # Size limits
        if original_length > 50000:  # 50KB limit
            threats.append("excessive_size")
            sanitized = sanitized[:50000] + "... [TRUNCATED]"
        
        is_safe = len(threats) == 0
        
        # Additional logging for blocked inputs
        if not is_safe and self.log_suspicious:
            logger.warning(
                f"Input sanitized: {len(threats)} threats detected",
                extra={
                    "session_id": session_id,
                    "threats": threats,
                    "size_reduction": original_length - len(sanitized)
                }
            )
        
        return {
            "sanitized": sanitized,
            "is_safe": is_safe,
            "threats_detected": threats,
            "original_length": original_length,
            "sanitized_length": len(sanitized)
        }
    
    def _is_legitimate_context(self, text: str, pattern: re.Pattern) -> bool:
        """
        Check if a matched pattern appears in legitimate context.
        
        Args:
            text: Full input text
            pattern: The pattern that matched
            
        Returns:
            True if this is likely legitimate usage
        """
        # Check for allowed context phrases
        for allowed_pattern in self.allowed_context_regex:
            if allowed_pattern.search(text):
                # The suspicious pattern might be part of legitimate phrase
                return True
        
        # If the text is asking about air quality systems/instructions legitimately
        legitimate_phrases = [
            "how does the monitoring system work",
            "what are the instructions for",
            "explain the system",
            "how to use the system"
        ]
        
        text_lower = text.lower()
        for phrase in legitimate_phrases:
            if phrase in text_lower:
                return True
        
        return False
    
    def _categorize_threat(self, pattern: str) -> str:
        """
        Categorize the type of threat based on the pattern.
        
        Args:
            pattern: Regex pattern that matched
            
        Returns:
            Threat category string
        """
        pattern_lower = pattern.lower()
        
        if any(word in pattern_lower for word in ["ignore", "disregard", "forget", "instructions"]):
            return "command_override"
        elif any(word in pattern_lower for word in ["api", "key", "token", "password", "credentials"]):
            return "credential_extraction"
        elif any(word in pattern_lower for word in ["system", "show", "reveal", "display", "print"]):
            return "system_manipulation"
        elif any(word in pattern_lower for word in ["mode", "jailbreak", "unrestricted"]):
            return "jailbreak_attempt"
        elif any(word in pattern_lower for word in ["script", "iframe", "eval", "exec"]):
            return "code_injection"
        else:
            return "unknown_threat"
    
    def _redact_credentials(self, text: str) -> str:
        """
        Redact potential credentials from text.
        
        Args:
            text: Input text
            
        Returns:
            Text with credentials redacted
        """
        # Redact patterns that look like API keys (alphanumeric strings of certain lengths)
        # Be cautious not to redact legitimate content
        
        # Pattern: sk-... (OpenAI style)
        text = re.sub(r'\bsk-[a-zA-Z0-9]{32,}\b', '[API_KEY_REDACTED]', text)
        
        # Pattern: long alphanumeric strings that might be keys
        text = re.sub(r'\b[a-zA-Z0-9]{32,64}\b', lambda m: '[KEY_REDACTED]' if not ' ' in m.group() else m.group(), text)
        
        # Pattern: Bearer tokens
        text = re.sub(r'Bearer\s+[a-zA-Z0-9_\-\.]+', 'Bearer [TOKEN_REDACTED]', text, flags=re.IGNORECASE)
        
        return text
    
    def is_safe_for_processing(self, user_input: str) -> bool:
        """
        Quick check if input is safe for processing.
        
        Args:
            user_input: Raw user input
            
        Returns:
            True if safe, False if suspicious
        """
        result = self.sanitize(user_input)
        return result["is_safe"]


# Global instance for convenience
_default_sanitizer = None


def get_input_sanitizer(strictness: str = "balanced") -> InputSanitizer:
    """
    Get or create the default input sanitizer instance.
    
    Args:
        strictness: Detection sensitivity level
        
    Returns:
        InputSanitizer instance
    """
    global _default_sanitizer
    if _default_sanitizer is None:
        _default_sanitizer = InputSanitizer(strictness=strictness)
    return _default_sanitizer


def sanitize_input(user_input: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to sanitize input using default sanitizer.
    
    Args:
        user_input: Raw user input
        session_id: Optional session ID
        
    Returns:
        Sanitization result dictionary
    """
    sanitizer = get_input_sanitizer()
    return sanitizer.sanitize(user_input, session_id)
