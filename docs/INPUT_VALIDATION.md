# Input Validation & Security

## Overview

The API **sanitizes dangerous patterns first**, then validates only critical threats. All legitimate technical content (code blocks, scientific notation, tutorials) passes through.

**Strategy:** Sanitize → Validate Critical Only → Allow

## How It Works

### Request Flow

1. Check length (max 100KB)
2. **Check CRITICAL patterns** → Block if found
3. **Sanitize content** → Remove dangerous patterns
4. **Allow request** → Pass to AI agent

### Pattern Types

**CRITICAL (Blocked Immediately):**

- Multi-stage SQL injection: `'; DROP TABLE; SELECT`
- Command chains with destructive flags: `rm -rf /`
- Code execution chains: `eval(__import__('os').system())`
- Deep path traversal: `../../../../etc/passwd`

**SANITIZE (Cleaned & Allowed):**

- SQL keywords in text → `[removed]`
- Shell command references → Neutralized
- XSS patterns → Stripped
- Single `eval`, `exec`, `__import__` mentions → Removed

## What Works

**✅ Always Accepted:**

- Scientific papers: `µg/m³`, `NO₂`, `(peak 180 µg/m³)`
- Programming guides: ` ```python `, `` `code` ``, `!pip install`
- Installation commands: Full code blocks preserved
- Technical tutorials: Complete examples with imports
- Markdown docs: All formatting maintained
- Content up to 100KB

**❌ Always Blocked (Critical Only):**

- `test; rm -rf / && shutdown`
- `'; DROP TABLE users; SELECT * FROM passwords`
- `eval(__import__('os').system('rm -rf /'))`

**⚠️ Sanitized & Allowed:**

- "Please select and drop old data" → Cleaned, allowed
- `` `whoami` command`` → Neutralized, allowed
- `Use __import__('module')` → Reference removed, allowed

## Examples

### ✅ GPT-OSS Colab Guide (Accepted)

```python
!pip install -q --upgrade torch
!pip install transformers accelerate

from transformers import AutoTokenizer, AutoModelForCausalLM
model = AutoModelForCausalLM.from_pretrained("gpt-oss-20b")
```

**Result:** Passed through, some patterns sanitized

### ✅ Scientific Query (Accepted)

```
A city experiencing high ozone (180 µg/m³) and elevated NO₂ (85 µg/m³).
Explain the photochemical reaction chain including OH radicals.
```

**Result:** Accepted as-is, notation preserved

### ❌ Critical Attack (Blocked)

```bash
test; rm -rf / && shutdown -h now
```

**Result:** Blocked - Critical security threat detected

## Technical Details

**Core Flow:**

```python
validate_request_data(data):
  1. Length check (100KB max)
  2. CRITICAL pattern check → Block if match
  3. Sanitize SANITIZE patterns → Clean
  4. Return sanitized data → Allow request
```

**Files Modified:**

- `src/utils/security.py`

**Status:** ✅ Production ready
