"""
Multi-Model Testing Script for Aeris-AQ v2.10.0
Tests all available Ollama models and compares performance.
"""

import asyncio
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

import httpx


class ModelTester:
    """Test multiple Ollama models and compare results."""

    def __init__(self):
        self.base_url = "http://localhost:8000/api/v1"
        self.test_query = "What's the current air quality in Kampala?"
        self.session_prefix = "model-test"
        self.results = []

    def get_available_models(self):
        """Get list of available Ollama models."""
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"❌ Error running ollama list: {result.stderr}")
                return []

            lines = result.stdout.strip().split("\n")[1:]  # Skip header
            models = []
            for line in lines:
                parts = line.split()
                if parts:
                    model_name = parts[0]
                    # Filter for local models (not cloud)
                    if ":cloud" not in model_name:
                        models.append(model_name)
            
            return models
        except Exception as e:
            print(f"❌ Error getting model list: {e}")
            return []

    def update_env_file(self, model_name: str):
        """Update .env file with new model."""
        env_path = Path(".env")
        if not env_path.exists():
            print(f"❌ .env file not found")
            return False

        try:
            content = env_path.read_text()
            lines = content.split("\n")
            updated = False

            for i, line in enumerate(lines):
                if line.startswith("AI_MODEL=") and not line.startswith("#"):
                    lines[i] = f"AI_MODEL={model_name}"
                    updated = True
                    break

            if updated:
                env_path.write_text("\n".join(lines))
                print(f"✅ Updated .env: AI_MODEL={model_name}")
                return True
            else:
                print(f"⚠️ AI_MODEL not found in .env")
                return False

        except Exception as e:
            print(f"❌ Error updating .env: {e}")
            return False

    async def test_model(self, model_name: str):
        """Test a specific model."""
        print(f"\n{'='*70}")
        print(f"Testing: {model_name}")
        print(f"{'='*70}")

        # Update .env file
        if not self.update_env_file(model_name):
            return None

        # Wait for server to reload (if auto-reload is enabled)
        print("⏳ Waiting 3 seconds for server reload...")
        await asyncio.sleep(3)

        session_id = f"{self.session_prefix}-{model_name.replace(':', '-').replace('.', '-')}"
        
        start_time = time.time()
        result = {
            "model": model_name,
            "query": self.test_query,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "success": False,
            "response_time": 0,
            "tools_used": [],
            "response_preview": "",
            "error": None
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url}/agent/chat",
                    data={"message": self.test_query, "session_id": session_id}
                )
                
                elapsed = time.time() - start_time
                result["response_time"] = round(elapsed, 2)

                if response.status_code == 200:
                    data = response.json()
                    result["success"] = True
                    result["tools_used"] = data.get("tools_used", [])
                    result["response_preview"] = data.get("response", "")[:200]
                    result["tokens_used"] = data.get("tokens_used", 0)
                    result["cached"] = data.get("cached", False)
                    
                    print(f"✅ SUCCESS ({elapsed:.2f}s)")
                    print(f"   Tools: {result['tools_used']}")
                    print(f"   Response: {result['response_preview'][:100]}...")
                else:
                    result["error"] = f"HTTP {response.status_code}: {response.text}"
                    print(f"❌ FAILED: {result['error']}")

        except asyncio.TimeoutError:
            result["error"] = "Request timeout (>120s)"
            print(f"❌ TIMEOUT: Model took too long to respond")
        except Exception as e:
            result["error"] = str(e)
            print(f"❌ ERROR: {e}")

        self.results.append(result)
        return result

    async def test_all_models(self):
        """Test all available models."""
        models = self.get_available_models()
        
        if not models:
            print("❌ No local Ollama models found. Run 'ollama list' to check.")
            return

        print(f"\n🎯 Found {len(models)} local model(s) to test:")
        for i, model in enumerate(models, 1):
            print(f"   {i}. {model}")

        print(f"\n🚀 Starting tests with query: '{self.test_query}'")
        print("="*70)

        for model in models:
            await self.test_model(model)

        self.generate_report()

    def generate_report(self):
        """Generate comparison report."""
        print(f"\n{'='*70}")
        print("MULTI-MODEL TEST REPORT")
        print(f"{'='*70}\n")

        # Summary table
        print(f"{'Model':<25} {'Status':<10} {'Time (s)':<12} {'Tools Used':<15}")
        print("-"*70)

        for result in self.results:
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            time_str = f"{result['response_time']:.2f}" if result["response_time"] > 0 else "N/A"
            tools = len(result["tools_used"])
            
            print(f"{result['model']:<25} {status:<10} {time_str:<12} {tools} tool(s)")

        # Performance ranking
        successful = [r for r in self.results if r["success"]]
        if successful:
            print(f"\n📊 Performance Ranking (Response Time):")
            sorted_results = sorted(successful, key=lambda x: x["response_time"])
            for i, result in enumerate(sorted_results, 1):
                print(f"   {i}. {result['model']}: {result['response_time']:.2f}s")

        # Tool usage comparison
        print(f"\n🔧 Tool Usage Comparison:")
        for result in self.results:
            if result["success"]:
                tools_str = ", ".join(result["tools_used"]) if result["tools_used"] else "No tools"
                print(f"   • {result['model']}: {tools_str}")

        # Save to JSON
        output_file = f"model_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n💾 Results saved to: {output_file}")
        print("="*70)


async def main():
    """Main execution."""
    tester = ModelTester()
    
    # Check if server is running
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:8000/health")
            if response.status_code != 200:
                print("❌ Server is not responding. Please start the server first:")
                print("   python start_server.py")
                return
    except Exception:
        print("❌ Server is not running. Please start it first:")
        print("   python start_server.py")
        return

    print("🎭 Aeris-AQ Multi-Model Testing Suite")
    print("="*70)
    print("This will test all available local Ollama models.")
    print("⚠️ Make sure the server is running with auto-reload enabled!")
    print("="*70)

    await tester.test_all_models()

    print("\n✅ Testing complete!")


if __name__ == "__main__":
    asyncio.run(main())
