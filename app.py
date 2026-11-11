import time, os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from kb import T, SAMPLES
import llm
from engine import analyze, triage, evaluate

app = FastAPI(title="RxRosetta")
EVENTS = []
class Txt(BaseModel): text: str
class Img(BaseModel): data: str; mime: str
class Chk(BaseModel): keys: list[str] = []; symptoms: list[str] = []
class Ev(BaseModel): type: str; detail: str; level: str = "info"

def log(type, detail, level="info"):
    EVENTS.append(dict(t=time.strftime("%H:%M:%S"), type=type, detail=detail, level=level)); del EVENTS[:-60]

@app.post("/api/analyze")
def a(r: Txt): return analyze(r.text)
@app.post("/api/scan")
def scan(r: Img):
    try: txt = llm.scan(r.data, r.mime)
    except llm.NoKey: return dict(error="Photo scan needs an API key. Set ANTHROPIC_API_KEY or GEMINI_API_KEY and restart, or paste the text instead.")
    except Exception as e:
        msg = str(e)
        for k in (os.getenv("GEMINI_API_KEY"), os.getenv("ANTHROPIC_API_KEY")):
            if k: msg = msg.replace(k, "***")
        return dict(error=f"Scan failed. {msg}")
    return dict(text="" if txt.upper().startswith("NONE") else txt)
@app.post("/api/checkin")
def c(r: Chk):
    lv = triage(r.keys, r.symptoms)
    log("check-in", f"{lv.upper()}: {', '.join(r.symptoms) or 'no symptoms'}", {"ok": "info", "call": "warn", "er": "bad"}[lv])
    return dict(level=lv)
@app.post("/api/event")
def e(r: Ev): log(r.type, r.detail, r.level); return {}
@app.get("/api/events")
def ev(): return EVENTS[::-1]
@app.get("/api/i18n")
def i(): return T
@app.get("/api/samples")
def s(): return SAMPLES
@app.get("/api/eval")
def v(): return evaluate()
app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True))
