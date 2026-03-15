import os
import json
import requests
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic()

def ask_claude(prompt: str, max_tokens: int = 1000) -> str:
    """Primary inference — Claude API via Anthropic."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()

def ask_ollama(prompt: str, model: str = "qwen2.5:14b") -> str:
    """Fallback inference — local Ollama on M5."""
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model":  model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 200,
            }
        },
        timeout=120
    )
    data = response.json()
    text = (data.get("response") or "").strip()
    if not text:
        # fallback — some Ollama versions use different response format
        text = data.get("message", {}).get("content", "").strip()
    return text

def ask_barren(prompt: str, max_tokens: int = 1000) -> tuple[str, str]:
    """
    Three-tier inference with automatic fallback.
    Returns (response_text, source_used)
    """
    # Tier 1 — Claude API
    try:
        print("   🧠 Trying Claude API...")
        result = ask_claude(prompt, max_tokens)
        return result, "claude"
    except Exception as e:
        print(f"   ⚠️  Claude API failed: {e}")

    # Tier 2 — Ollama local (disabled until M5 Metal fix ships)
    # try:
    #     print("   🏠 Falling back to Ollama (local M5)...")
    #     result = ask_ollama(prompt)
    #     return result, "ollama"
    # except Exception as e:
    #     print(f"   ⚠️  Ollama failed: {e}")

    # Tier 2 placeholder — re-enable when Ollama fixes M5 Metal support
    print("   ⏭️  Ollama skipped (M5 Metal incompatibility — pending fix)")

    # Tier 3 — Hard failure
    raise RuntimeError("All inference tiers failed. Check your connection and Ollama status.")

if __name__ == "__main__":
    print("🧪 Testing Barren's inference chain...\n")

    # Start Ollama server first
    import subprocess, time
    print("Starting Ollama server...")
    subprocess.Popen(["ollama", "serve"],
                     stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)
    time.sleep(3)

    test_prompt = """You are Barren Wuffett, a warmhearted fanatic dividend investor 
    with a mad-scientist edge. In 2 sentences, explain why dividend investing is the 
    greatest pursuit known to humankind."""

    print("Testing Claude API (primary):")
    response, source = ask_barren(test_prompt)
    print(f"   Source: {source}")
    print(f"   Response: {response}\n")

    print("Testing Ollama fallback directly:")
    try:
        response = ask_ollama(test_prompt)
        print(f"   Response: {response}\n")
    except Exception as e:
        print(f"   ❌ {e}")

    print("✅ Inference chain test complete!")