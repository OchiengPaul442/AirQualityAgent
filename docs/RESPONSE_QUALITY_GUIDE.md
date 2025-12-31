# AI Response Quality Configuration

## Quick Start

Add this to your `.env` file:

```bash
AI_RESPONSE_STYLE=general
```

The agent will provide clear, professional responses suitable for all audiences.

## Why Use General Preset?

The `general` preset is optimized to work effectively for everyone:

✅ **Adapts to any audience** - Executives, policymakers, researchers, or public  
✅ **Professional yet accessible** - Appropriate detail without jargon  
✅ **Reduces repetition** - Balanced parameters (temp: 0.5, top_p: 0.9)  
✅ **Natural communication** - Conversational and contextual  
✅ **Cost-effective** - Efficient token usage

**Only use specialized presets if you have a single, specific audience.**

## Configuration Options

### Style Presets

**`general` (DEFAULT - RECOMMENDED FOR ALL)**

```bash
AI_RESPONSE_STYLE=general
```

**Specialized Presets** (only for single-audience deployments):

- `executive` - Ultra-concise for CEOs only
- `technical` - Maximum detail for scientists only
- `simple` - Basic language for community only
- `policy` - Formal for government only

### Fine-Tuning (Optional)

```bash
AI_RESPONSE_TEMPERATURE=0.5  # 0.0-1.0 (lower=focused, higher=creative)
AI_RESPONSE_TOP_P=0.9       # 0.0-1.0 (lower=consistent, higher=diverse)
```

## Testing

Restart server after changes, then test:

```bash
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -F "message=What's the air quality in Kampala?"
```

## Troubleshooting

| Issue       | Solution                    |
| ----------- | --------------------------- |
| Too verbose | Lower temperature to 0.4    |
| Too brief   | Raise temperature to 0.6    |
| Repetitive  | Check for duplicate queries |
| Wrong tone  | Verify .env and restart     |

---

**That's all you need!** The `general` preset handles everything.
