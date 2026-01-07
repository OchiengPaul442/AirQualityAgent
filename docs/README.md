# Documentation Index

Welcome to the Air Quality AI Agent documentation. This directory contains comprehensive guides to help you understand, deploy, and use the system.

## Quick Links

- **[Getting Started](./GETTING_STARTED.md)** - Installation and setup guide
- **[API Reference](./API_REFERENCE.md)** - Complete API documentation
- **[Architecture](./ARCHITECTURE.md)** - System design and architecture
- **[Deployment](./DEPLOYMENT.md)** - Production deployment guide
- **[Docker Guide](./DOCKER.md)** - Container-based deployment
- **[MCP Guide](./MCP_GUIDE.md)** - Model Context Protocol integration

## Documentation Overview

### For New Users

Start here if you're new to the project:

1. **[Getting Started](./GETTING_STARTED.md)** - Follow this guide to get the agent running locally in 15 minutes
2. **[API Reference](./API_REFERENCE.md)** - Learn about available endpoints and how to use them

### For Developers

Understanding the system:

1. **[Architecture](./ARCHITECTURE.md)** - Understand the system design, components, and data flow
2. **[API Reference](./API_REFERENCE.md)** - Detailed endpoint documentation with examples
3. **[MCP Guide](./MCP_GUIDE.md)** - Learn how to integrate external data sources

### For DevOps/Deployment

Deploying to production:

1. **[Deployment](./DEPLOYMENT.md)** - Traditional server deployment guide
2. **[Docker Guide](./DOCKER.md)** - Containerized deployment with Docker/Kubernetes
3. **[Architecture](./ARCHITECTURE.md)** - Understanding scalability and performance

## What is the Air Quality AI Agent?

The Air Quality AI Agent is a sophisticated AI system that provides:

- **Real-time air quality monitoring** for cities worldwide using intelligent query analysis
- **Guaranteed tool calling** across all AI providers (Ollama, Gemini, OpenAI)
- **Health impact assessments** and recommendations
- **Air quality forecasts** and historical data analysis
- **Research capabilities** with automatic web search and citation support
- **Policy development assistance** for governments and NGOs
- **Web scraping** for detailed content analysis
- **Integration with multiple data sources** (WAQI, AirQo, Weather APIs)
- **Support for multiple AI providers** (Gemini, OpenAI, Ollama)

### Key Features

- **QueryAnalyzer**: Intelligent pre-processing that detects query intent and proactively calls appropriate tools
- **Multi-Provider Support**: Works seamlessly with local (Ollama) and cloud AI providers
- **Real-Time Data**: Always uses live data instead of training data through proactive tool calling
- **Comprehensive Testing**: 22-test suite ensuring 100% functionality across all features
- **Security First**: Built-in protections against information leakage and abuse

## Key Features

### Multi-Role AI

- Environmental Consultant (default)
- Senior Researcher
- Policy Advisor

### Data Sources

- WAQI (World Air Quality Index) - Global coverage
- AirQo - African air quality network
- Weather Service - Global weather data
- Web Search - Latest research and news
- Document Scanner - PDF and text analysis

### Cost Optimization

- Client-side session management (90% storage cost reduction)
- Intelligent response caching (60-80% API cost reduction)
- Token tracking for cost visibility
- Rate limiting for abuse protection

### Scalability

- Stateless API design for horizontal scaling
- Async operations for high throughput
- Redis-backed caching
- Multi-provider AI support

## System Requirements

### Minimum

- Python 3.10+
- 2 CPU cores
- 4 GB RAM
- 10 GB storage

### Recommended

- Python 3.10+
- 4+ CPU cores
- 8+ GB RAM
- 20+ GB storage
- Redis server

## Quick Setup

```bash
# Clone repository
git clone https://github.com/OchiengPaul442/AirQualityAgent.git
cd AirQualityAgent

# Install dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

## Docker Quick Start

```bash
# Clone and configure
git clone https://github.com/OchiengPaul442/AirQualityAgent.git
cd AirQualityAgent
cp .env.example .env
# Edit .env

# Run with Docker
docker-compose up -d

# Check logs
docker-compose logs -f
```

## API Examples

### Chat with Agent

```bash
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the air quality in Nairobi?"
  }'
```

### Get Air Quality Data

```bash
curl -X POST http://localhost:8000/api/v1/air-quality/query \
  -H "Content-Type: application/json" \
  -d '{
    "city": "Kampala",
    "country": "UG"
  }'
```

## Support and Contributing

### Getting Help

- **Documentation Issues**: Check this docs folder
- **Bug Reports**: [GitHub Issues](https://github.com/OchiengPaul442/AirQualityAgent/issues)
- **Questions**: Open a discussion on GitHub

### Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write tests
5. Submit a pull request

## Documentation Updates

This documentation is regularly updated. Last updated: December 2025

## License

See the LICENSE file in the project root.

## Acknowledgments

Built with:

- FastAPI - Web framework
- Google Gemini - AI provider
- OpenAI - AI provider
- Ollama - Local AI
- WAQI - Air quality data
- AirQo - African air quality data
- Open-Meteo - Weather data

---

For the latest updates and detailed guides, explore the documentation files linked above.
