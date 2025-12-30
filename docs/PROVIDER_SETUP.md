# AI Provider Setup Guide

This guide covers how to configure the Air Quality AI Agent with different AI providers.

## Supported Providers

The agent supports multiple AI providers through a unified configuration interface:

1. **Google Gemini** - Google's advanced multimodal models
2. **OpenAI** - Direct access to GPT models
3. **OpenRouter** - Access to 100+ models through a single API
4. **DeepSeek** - Chinese AI company's powerful models
5. **Kimi (Moonshot)** - Long-context Chinese models
6. **Ollama** - Local open-source models

## Configuration Overview

All providers are configured through the `.env` file with three main variables:

```dotenv
AI_PROVIDER=<provider_name>
AI_MODEL=<model_name>
AI_API_KEY=<your_api_key>
OPENAI_BASE_URL=<base_url>  # For OpenAI-compatible providers
```

---

## Provider Setup Instructions

### 1. Google Gemini

**Advantages:**

- High quality responses
- Strong multimodal capabilities
- Competitive pricing
- Latest models (Gemini 2.5, Gemini 3 Preview)

**Setup:**

1. Visit [Google AI Studio](https://aistudio.google.com/)
2. Create a project and generate an API key
3. Configure your `.env`:

```dotenv
AI_PROVIDER=gemini
AI_MODEL=gemini-2.5-flash
AI_API_KEY=your_gemini_api_key_here
```

**Recommended Models:**

- `gemini-2.5-flash` - Fast and efficient (stable)
- `gemini-2.5-pro` - Best for complex reasoning (stable)
- `gemini-3-flash-preview` - Latest preview model
- `gemini-3-pro-preview` - Most advanced preview

---

### 2. OpenAI (Direct)

**Advantages:**

- Industry-leading GPT models
- Excellent tool calling support
- Reliable infrastructure

**Setup:**

1. Visit [OpenAI Platform](https://platform.openai.com/)
2. Create an account and add billing
3. Generate an API key
4. Configure your `.env`:

```dotenv
AI_PROVIDER=openai
AI_MODEL=gpt-4o
AI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
```

**Recommended Models:**

- `gpt-4o` - Best for complex tasks
- `gpt-4o-mini` - Fast and cost-effective
- `gpt-3.5-turbo` - Budget option

---

### 3. OpenRouter

**Advantages:**

- Access to 100+ models through one API
- Free tier available
- Unified billing across providers
- Pay-per-use pricing

**Setup:**

1. Visit [OpenRouter](https://openrouter.ai/)
2. Sign up and get your API key
3. Browse available models at [openrouter.ai/models](https://openrouter.ai/models)
4. Configure your `.env`:

```dotenv
AI_PROVIDER=openai
AI_MODEL=gpt-oss-120b
AI_API_KEY=sk-or-v1-your_openrouter_key_here
OPENAI_BASE_URL=https://openrouter.ai/api/v1
```

**Popular Free Models:**

- `gpt-oss-120b` - Free, powerful model
- `microsoft/phi-3-mini-128k-instruct:free` - Microsoft's efficient model
- `meta-llama/llama-3.2-3b-instruct:free` - Meta's latest

**Popular Paid Models:**

- `anthropic/claude-3.5-sonnet` - Anthropic's best
- `google/gemini-2.0-flash-exp:free` - Google's latest
- `openai/gpt-4o` - OpenAI flagship

---

### 4. DeepSeek

**Advantages:**

- Competitive pricing
- Strong reasoning capabilities
- Chinese and English support
- Specialized coding models

**Setup:**

1. Visit [DeepSeek Platform](https://platform.deepseek.com/)
2. Register and create an API key
3. Configure your `.env`:

```dotenv
AI_PROVIDER=openai
AI_MODEL=deepseek-chat
AI_API_KEY=your_deepseek_api_key_here
OPENAI_BASE_URL=https://api.deepseek.com/v1
```

**Available Models:**

- `deepseek-chat` - General purpose chat
- `deepseek-coder` - Specialized for coding tasks
- `deepseek-reasoner` - Enhanced reasoning capabilities

---

### 5. Kimi (Moonshot AI)

**Advantages:**

- Ultra-long context (up to 200K tokens)
- Chinese language expertise
- Competitive pricing in Asian markets

**Setup:**

1. Visit [Moonshot AI](https://platform.moonshot.cn/)
2. Register (requires Chinese phone number or international verification)
3. Generate an API key
4. Configure your `.env`:

```dotenv
AI_PROVIDER=openai
AI_MODEL=moonshot-v1-8k
AI_API_KEY=your_kimi_api_key_here
OPENAI_BASE_URL=https://api.moonshot.cn/v1
```

**Available Models:**

- `moonshot-v1-8k` - 8K context window
- `moonshot-v1-32k` - 32K context window
- `moonshot-v1-128k` - 128K context window

---

### 6. Ollama (Local Models)

**Advantages:**

- Completely free
- Privacy-focused (runs locally)
- No API rate limits
- Offline capability

**Setup:**

1. Install [Ollama](https://ollama.com/)
2. Pull a model: `ollama pull llama3.2`
3. Start Ollama server (usually auto-starts)
4. Configure your `.env`:

```dotenv
AI_PROVIDER=ollama
AI_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434
```

**Recommended Models:**

- `llama3.2` - Meta's latest (3B, 7B variants)
- `qwen2.5` - Alibaba's powerful model
- `deepseek-r1:7b` - DeepSeek reasoning model
- `mistral` - Fast and efficient

**Pull models:**

```bash
ollama pull llama3.2
ollama pull qwen2.5
ollama pull deepseek-r1:7b
```

---

## Switching Providers

To switch between providers, simply update your `.env` file and restart the server:

```bash
# Stop the server (Ctrl+C)
# Edit .env file
# Restart the server
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

The agent will automatically detect the new configuration and use the appropriate provider.

---

## Testing Your Configuration

After configuring, test with:

```bash
curl -X POST "http://localhost:8000/api/v1/agent/chat" \
     -H "Content-Type: application/json" \
     -d '{"message": "What is the air quality in London?"}'
```

Or use the interactive docs at `http://localhost:8000/docs`

---

## Provider Comparison

| Provider   | Cost   | Speed  | Quality   | Tool Calling | Free Tier        |
| ---------- | ------ | ------ | --------- | ------------ | ---------------- |
| Gemini     | Low    | Fast   | Excellent | ✅           | ✅ (60 RPM)      |
| OpenAI     | High   | Fast   | Excellent | ✅           | ❌               |
| OpenRouter | Varies | Varies | Varies    | ✅           | ✅ (Some models) |
| DeepSeek   | Low    | Fast   | Very Good | ✅           | ✅ (Limited)     |
| Kimi       | Medium | Fast   | Good      | ✅           | ✅ (Limited)     |
| Ollama     | Free   | Medium | Good      | ⚠️ (Limited) | ✅               |

---

## Troubleshooting

### Error: "AI_API_KEY is not set"

- Ensure your API key is properly set in `.env`
- No quotes or spaces around the key
- Restart the server after changing

### Error: "Invalid authentication"

- Verify your API key is active
- Check if you need to add billing (OpenAI, OpenRouter)
- Ensure base URL is correct

### Error: "Model not found"

- Check model name spelling
- Verify model is available for your API key
- For Ollama, ensure model is pulled: `ollama pull <model>`

### Slow responses

- Try a smaller/faster model
- Check your internet connection
- For Ollama, ensure sufficient RAM (8GB+ recommended)

---

## Best Practices

1. **Start with free tiers** - Test with Gemini, OpenRouter free models, or Ollama
2. **Monitor costs** - Set up billing alerts for paid providers
3. **Use appropriate models** - Don't use expensive models for simple queries
4. **Keep API keys secure** - Never commit `.env` to version control
5. **Test locally first** - Use Ollama for development, paid APIs for production

---

## Getting Help

If you encounter issues:

1. Check the server logs for detailed error messages
2. Verify your `.env` configuration
3. Test with a simple query first
4. Review provider-specific documentation

For provider-specific issues, consult:

- [Gemini API Docs](https://ai.google.dev/docs)
- [OpenAI API Docs](https://platform.openai.com/docs)
- [OpenRouter Docs](https://openrouter.ai/docs)
- [DeepSeek Docs](https://platform.deepseek.com/docs)
- [Moonshot Docs](https://platform.moonshot.cn/docs)
- [Ollama Docs](https://ollama.com/docs)
