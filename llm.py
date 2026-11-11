"""Optional vision step: an LLM only TRANSCRIBES medicine lines. All checking is done by the deterministic engine."""
import os, httpx
PROMPT = ("Transcribe ONLY the medicine lines from this discharge summary or prescription, one per line, as written, in the form "
          "'Tab <name> <dose> <frequency such as 1-0-1 or BD> <food instruction> x <days>'. Keep spellings as written. "
          "Do not add, correct, explain or infer anything. If nothing is legible, reply NONE.")
GBASE = "https://generativelanguage.googleapis.com/v1beta"

class NoKey(Exception): pass

def _err(r):
    try: m = r.json()["error"]["message"]
    except Exception: m = r.text[:200]
    return f"HTTP {r.status_code}: {m}"

def _gemini_models(h):
    r = httpx.get(f"{GBASE}/models", headers=h, params={"pageSize": 200}, timeout=30)
    if r.status_code != 200: raise RuntimeError("Could not list Gemini models. " + _err(r))
    ms = [m["name"].split("/")[-1] for m in r.json().get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
    ok = [m for m in ms if "flash" in m and not any(x in m for x in ("omni", "image", "tts", "live", "audio", "native", "thinking", "exp", "embed"))]
    # stable before preview, full Flash before Flash-Lite, newest name first
    return sorted(ok, key=lambda m: ("preview" not in m, "lite" not in m, m), reverse=True)

def _gemini(gk, b64, mime):
    h = {"x-goog-api-key": gk}; body = {"contents": [{"parts": [{"text": PROMPT}, {"inline_data": {"mime_type": mime, "data": b64}}]}]}
    first = [os.getenv("GEMINI_MODEL")] if os.getenv("GEMINI_MODEL") else []
    tried, last = [], ""
    for phase in range(2):
        for m in (first if phase == 0 else [x for x in _gemini_models(h) if x not in tried][:6]):
            r = httpx.post(f"{GBASE}/models/{m}:generateContent", headers=h, json=body, timeout=90); tried.append(m)
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            last = _err(r)
            if r.status_code not in (404, 429, 503): raise RuntimeError(f"Gemini model {m}: {last}")   # skip: missing, no free quota, busy
    raise RuntimeError("No Gemini model worked for this key. Tried: " + ", ".join(tried) + ". Last error: " + last[:160])

def scan(b64, mime):
    ak, gk = os.getenv("ANTHROPIC_API_KEY"), os.getenv("GEMINI_API_KEY")
    if ak:
        kind = "document" if mime == "application/pdf" else "image"
        r = httpx.post("https://api.anthropic.com/v1/messages", timeout=90, headers={"x-api-key": ak, "anthropic-version": "2023-06-01"},
            json={"model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"), "max_tokens": 1000, "messages": [{"role": "user", "content": [
                {"type": kind, "source": {"type": "base64", "media_type": mime, "data": b64}}, {"type": "text", "text": PROMPT}]}]})
        if r.status_code != 200: raise RuntimeError("Anthropic " + _err(r))
        return "".join(c.get("text", "") for c in r.json()["content"]).strip()
    if gk: return _gemini(gk, b64, mime)
    raise NoKey()
