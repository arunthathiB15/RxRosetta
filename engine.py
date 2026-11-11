import re, difflib, random
from collections import Counter
from kb import KB, INTER, SLOTS

NAMES = {n: k for k, v in KB.items() for n in [k] + v["al"]}
ORDER = ["morning", "afternoon", "evening", "night"]

def find(l):
    for n, k in sorted(NAMES.items(), key=lambda x: -len(x[0])):
        if re.search(r"\b" + re.escape(n) + r"\b", l): return k, n, "exact"
    for tok in re.findall(r"[a-z]{5,}", l):
        m = difflib.get_close_matches(tok, list(NAMES), 1, 0.8)
        if m: return NAMES[m[0]], tok, "fuzzy"
    return None, None, None

def freq(l, key):
    m = re.search(r"\b([01])\s*-\s*([01])\s*-\s*([01])(?:\s*-\s*([01]))?\b", l)
    if m:
        g = m.groups(); names = ORDER if g[3] else ["morning", "afternoon", "night"]
        return [n for n, v in zip(names, g) if v == "1"]
    for pat, s in [(r"\b(qid|qds|four times|4 times)\b", ORDER),
                   (r"\b(tds|tid|thrice|three times|3 times|8 hourly)\b", ["morning", "afternoon", "night"]),
                   (r"\b(bd|bid|twice|two times|2 times|12 hourly)\b", ["morning", "night"]),
                   (r"\b(hs|bedtime|at night|nocte)\b", ["night"]), (r"\b(sos|prn|as needed)\b", ["asneeded"]),
                   (r"\b(od|once|daily|morning|empty stomach)\b", [(KB.get(key) or {}).get("t", "morning")])]:
        if re.search(pat, l): return s
    return []

def food(l, key):
    for pat, f in [(r"empty stomach", "empty"), (r"before (food|meals?|breakfast)", "before"),
                   (r"after (food|meals?)|\bpc\b", "after"), (r"with (food|meals?)", "with")]:
        if re.search(pat, l): return f
    return (KB.get(key) or {}).get("food", "any")

def interactions(keys):
    ks = set(keys); out = []
    for a, b, sev, eff in INTER:
        if a in ks and b in ks: out.append(dict(a=a, b=b, sev=sev, eff=eff))
    for k, c in Counter(keys).items():
        if c > 1: out.append(dict(a=k, b=k, sev="mod", eff="dupe"))
    if {"pantoprazole", "omeprazole"} <= ks: out.append(dict(a="pantoprazole", b="omeprazole", sev="low", eff="ppi"))
    return out

def analyze(text):
    meds = []
    for raw in re.split(r"[\n;]+", text):
        l = raw.strip().lower()
        if not l: continue
        key, typed, how = find(l)
        if not key:
            m = re.match(r"(?:tab|tabs|tablet|cap|capsule|syp|inj)\.?\s+([a-z]+)", l)
            if not m: continue
            typed = m.group(1)
        d = re.search(r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml)\b", l)
        slots = freq(l, key); v = KB.get(key, {})
        meds.append(dict(key=key, name=(key or typed).title(), typed=typed, known=bool(key), how=how,
            dose=f"{d.group(1)} {d.group(2)}" if d else None, slots=slots, food=food(l, key), cat=v.get("cat"),
            notes=v.get("n", []), verify=(not key) or (not d) or (not slots) or how == "fuzzy",
            link=f"https://dailymed.nlm.nih.gov/dailymed/search.cfm?labeltype=all&query={key or typed}"))
    return dict(meds=meds, issues=interactions([m["key"] for m in meds if m["key"]]))

THIN = {"warfarin", "aspirin", "clopidogrel", "ibuprofen"}
def triage(keys, sym):
    s, k = set(sym), set(keys)
    if s & {"chest", "breath", "swell", "faint"}: return "er"
    if "bleed" in s and k & THIN: return "er"
    if "low" in s and "glimepiride" in k: return "er"
    return "call" if s else "ok"

def evaluate(n=40, seed=7):
    R = random.Random(seed); ALL = ORDER
    F = [("OD", None), ("once daily", None), ("BD", ["morning", "night"]), ("twice daily", ["morning", "night"]),
         ("TDS", ["morning", "afternoon", "night"]), ("1-0-1", ["morning", "night"]), ("0-0-1", ["night"]),
         ("HS", ["night"]), ("QID", ALL)]
    tp = fp = fn = dose = slot = hit = 0; ir = [0, 0]; fails = []
    for i in range(n):
        gold, lines = {}, []
        for k in R.sample(list(KB), R.randint(4, 7)):
            v = KB[k]; d = R.choice(v["d"]); u = v.get("u", "mg"); name = R.choice([k] + v["al"])
            if R.random() < .25 and len(name) > 5:
                j = R.randrange(1, len(name) - 2); name = name[:j] + name[j + 1] + name[j] + name[j + 2:]
            if R.random() < .15: name = name.replace("i", "l", 1)   # OCR-style confusion
            if R.random() < .10: name = name.replace("o", "0", 1)   # OCR-style confusion
            f, s = R.choice(F); s = s or [v.get("t", "morning")]
            fmt = R.choice(["Tab {n} {d} {u} {f}", "T. {n} {d}{u} - {f}", "{n} {d} {u} ({f})", "Cap {n} {d} {u} {f} x {x} days"])
            lines.append(fmt.format(n=name.title() if R.random() < .5 else name.upper(), d=d, u=u, f=f, x=R.randint(3, 30)))
            gold[k] = (f"{d} {u}", s)
        got = {m["key"]: m for m in analyze("\n".join(lines))["meds"] if m["key"]}
        for k, (gd, gs) in gold.items():
            if k in got:
                tp += 1; hit += 1; dose += got[k]["dose"] == gd; slot += got[k]["slots"] == gs
                if got[k]["dose"] != gd or got[k]["slots"] != gs: fails.append(f"case {i}: {k} parsed as {got[k]['dose']} {got[k]['slots']}, expected {gd} {gs}")
            else:
                fn += 1; fails.append(f"case {i}: missed {k}")
        fp += len(set(got) - set(gold))
        gp = {(x["a"], x["b"], x["eff"]) for x in interactions(list(gold))}
        pp = {(x["a"], x["b"], x["eff"]) for x in interactions(list(got))}
        ir[0] += len(gp & pp); ir[1] += len(gp)
    r = lambda a, b: round(100 * a / b, 1) if b else 100.0
    return dict(cases=n, medicines=tp + fn, drug_recall=r(tp, tp + fn), drug_precision=r(tp, tp + fp), dose_accuracy=r(dose, hit),
        schedule_accuracy=r(slot, hit), interaction_recall=r(*ir), failures=fails[:8],
        note="Synthetic notes (seeded) with brand names, typos and mixed formats. This measures the rule-based parser baseline, not real hospital documents.")
