"""check_ai.py - find out why "Write complaint with AI" fails.

Run from your project folder:   python check_ai.py
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    print("Tip: pip install python-dotenv")

key = os.getenv("GEMINI_API_KEY")
print("Step 1: API key")
if not key:
    raise SystemExit("  FAILED: GEMINI_API_KEY is empty. Add it to your .env file "
                     "(GEMINI_API_KEY=your-key, no quotes), then run this again.")
print(f"  OK, key found ({len(key)} characters)\n")

try:
    from google import genai
except ImportError:
    raise SystemExit("  FAILED: library missing. Run:  pip install -U google-genai")

client = genai.Client(api_key=key)

print("Step 2: models your key can use")
try:
    names = []
    for m in client.models.list():
        actions = getattr(m, "supported_actions", None) or []
        if "generateContent" in actions and "gemini" in m.name:
            names.append(m.name.replace("models/", ""))
    flash = [n for n in names if "flash" in n]
    print("  Found", len(names), "Gemini models.")
    print("  Flash models:", ", ".join(flash[:15]) or "(none)")
except Exception as e:
    print("  Could not list models:", e)
    flash = []

print("\nStep 3: test a real request")
from ai import candidate_models  # noqa: E402

tried = [m for m in candidate_models()] + [n for n in flash if n not in candidate_models()][:3]
working = None
for model in tried:
    try:
        r = client.models.generate_content(model=model, contents="Reply with the single word OK")
        print(f"  {model}: WORKS -> {(r.text or '').strip()[:20]}")
        working = working or model
        break
    except Exception as e:
        print(f"  {model}: failed -> {str(e)[:140]}")

if working:
    print(f"\nAI is working with '{working}'. Restart civic.py and try the website again.")
    print(f"To always use it, add to .env:   GEMINI_MODEL={working}")
else:
    print("\nNo model worked. Check the messages above:")
    print("  - 'API key not valid'  -> make a new key at aistudio.google.com and update .env")
    print("  - '429' / 'quota'      -> free quota used up; wait or enable billing")
    print("  - 'not found'/'404'    -> set GEMINI_MODEL to one of the Flash models listed in step 2")
    print("  - 'location'/'region'  -> the API is not available from your network/country")