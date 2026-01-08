# Test Suite

## Overview

This directory contains comprehensive tests for the AERIS-AQ Air Quality Agent.

## Test Files

### 1. `test_agent.py` - Core Features (15 tests)

Tests all core agent functionality:

- Human-like reasoning engine
- Cost optimization (caching, token tracking, warnings)
- Image upload configuration and capability detection
- Full system integration

**Run:** `python -m pytest tests/test_agent.py -v`

### 2. `comprehensive_test_suite.py` - Production Tests (22 tests)

End-to-end integration tests simulating real user scenarios:

- Chat with tool usage
- Document upload and processing
- Security and information leak prevention
- Conversation memory and context
- Error handling and edge cases
- Performance and concurrency
- Web scraping capabilities

**Run:** `python tests/comprehensive_test_suite.py`

### 3. `test_all_services.py` - Service Integration Tests

Tests all external API integrations:

- WAQI (World Air Quality Index)
- AirQo (African air quality data)
- OpenMeteo (weather and forecast)
- Web search and scraping

**Run:** `python -m pytest tests/test_all_services.py -v`

## Running All Tests

```bash
# Run all pytest tests
python -m pytest tests/ -v

# Run comprehensive production suite
python tests/comprehensive_test_suite.py
```

## Expected Results

- ✅ **test_agent.py**: 15/15 tests passing (100%)
- ✅ **comprehensive_test_suite.py**: 22/22 tests passing (100%)
- ✅ **test_all_services.py**: Service integration tests

## Test Coverage

- Core features: Reasoning, cost optimization, configuration
- API endpoints: Chat, sessions, health checks
- Data sources: WAQI, AirQo, OpenMeteo
- Document processing: PDF, CSV, Excel
- Security: Prompt injection, information leakage
- Performance: Response times, concurrency
- Cost optimization: Caching, token tracking, warnings
