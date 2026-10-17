"""Free check of the Anthropic API key and the detector lookup request (no lookup is run)."""
import getpass
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "trm4"))
import anthropic
import detector_lookup as DL

key = os.environ.get("ANTHROPIC_API_KEY") or getpass.getpass("Paste API key (hidden): ").strip()
client = anthropic.Anthropic(api_key=key)

print("1) Key check (free)...")
try:
    client.models.retrieve(DL.MODEL)
    print("   OK - key is valid and can see", DL.MODEL)
except anthropic.APIStatusError as e:
    sys.exit("   FAILED %s: %s" % (e.status_code, e.message))

print("2) Request format check with token counting (free)...")
fields = "\n".join("- %s [%s]: %s" % (k, unit or "-", desc) for k, _, _, unit, desc in DL.FIELDS)
try:
    n = client.messages.count_tokens(
        model=DL.MODEL,
        tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 4},
               {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 3}],
        messages=[{"role": "user", "content": DL.RESEARCH_PROMPT.format(name="SCD Blackbird 1280 XBn", fields=fields)}],
    )
    print("   OK - request format accepted (%d input tokens)" % n.input_tokens)
except anthropic.APIStatusError as e:
    print("   FAILED %s: %s" % (e.status_code, e.message))

print("3) Tiny real request (max 16 output tokens, costs < $0.001 if you have credit)...")
try:
    client.messages.create(model=DL.MODEL, max_tokens=16, messages=[{"role": "user", "content": "Hi"}])
    print("   OK - account has credit and requests work")
except anthropic.APIStatusError as e:
    print("   FAILED %s: %s" % (e.status_code, e.message))

print("4) Fallback option (tiny request)...")
try:
    client.beta.messages.create(model=DL.MODEL, max_tokens=16, betas=["server-side-fallback-2026-07-01"],
                                fallbacks="default", messages=[{"role": "user", "content": "Hi"}])
    print("   OK")
except anthropic.APIStatusError as e:
    print("   FAILED %s: %s" % (e.status_code, e.message))

print("5) Effort option (tiny request)...")
try:
    client.messages.create(model=DL.MODEL, max_tokens=16, output_config={"effort": "high"},
                           messages=[{"role": "user", "content": "Hi"}])
    print("   OK")
except anthropic.APIStatusError as e:
    print("   FAILED %s: %s" % (e.status_code, e.message))

print("6) JSON format of the value-extraction step (small request, about $0.05)...")
print("   (the first request with a new schema can take up to a minute or two while the API compiles it)")
import time
t0 = time.time()
try:
    r = client.with_options(timeout=300, max_retries=0).messages.create(
        model=DL.MODEL, max_tokens=4000,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": DL.SCHEMA}},
        messages=[{"role": "user", "content": DL.EXTRACT_PROMPT.format(
            name="Test", notes="Test detector, 640x512 pixels, 15 um pitch, made by Test Inc.")}])
    print("   OK in %.0f s (stop_reason=%s)" % (time.time() - t0, r.stop_reason))
    print("  ", "".join(b.text for b in r.content if b.type == "text")[:300])
except anthropic.APIStatusError as e:
    print("   FAILED %s: %s" % (e.status_code, e.message))
except anthropic.APIError as e:
    print("   FAILED after %.0f s: %s: %s" % (time.time() - t0, type(e).__name__, e))
