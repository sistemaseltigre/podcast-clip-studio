#!/usr/bin/env python3
"""Read a transcript.json and help choose clips.

  python3 find_moments.py transcript.json                 # readable transcript: [mm:ss.s] sentence  (|| = pause > 0.7 s)
  python3 find_moments.py transcript.json --search "dinero,error"
  python3 find_moments.py transcript.json --candidates 45  # candidate windows of ~45 s that start/end on sentence boundaries

The candidate score is only a hint (speech density, questions/exclamations, numbers, hook words).
Always read the transcript yourself and pick moments with a clear hook, a payoff and a clean ending.
"""
import json, sys, re, argparse

HOOK = re.compile(r"\b(secreto|nadie|nunca|siempre|error|clave|truco|por qué|cómo|verdad|increíble|mejor|peor|"
                  r"secret|nobody|never|always|mistake|key|trick|why|how|truth|best|worst)\b", re.I)

def mmss(t): return f"{int(t // 60):02d}:{t % 60:04.1f}"

def sentences(words, gap=0.7):
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        end = w["w"].endswith((".", "?", "!", "…")) or nxt is None or (nxt["s"] - w["e"] > gap)
        if end:
            out.append({"s": cur[0]["s"], "e": cur[-1]["e"], "text": " ".join(x["w"] for x in cur),
                        "pause_after": (nxt["s"] - w["e"]) if nxt else 0}); cur = []
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("transcript"); ap.add_argument("--search"); ap.add_argument("--candidates", type=float)
    a = ap.parse_args(); T = json.load(open(a.transcript)); S = sentences(T["words"])
    if a.search:
        keys = [k.strip().lower() for k in a.search.split(",") if k.strip()]
        for s in S:
            if any(k in s["text"].lower() for k in keys): print(f"[{mmss(s['s'])}–{mmss(s['e'])}] {s['text']}")
        return
    if a.candidates:
        L = a.candidates; res = []
        for i in range(len(S)):
            for j in range(i, len(S)):
                d = S[j]["e"] - S[i]["s"]
                if d > L * 1.35: break
                if d < L * 0.6: continue
                txt = " ".join(s["text"] for s in S[i:j + 1]); nw = len(txt.split())
                score = nw / d + 0.6 * txt.count("?") + 0.4 * txt.count("!") + 0.3 * len(re.findall(r"\d", txt)) \
                        + 0.8 * len(HOOK.findall(S[i]["text"])) + (0.5 if S[j]["text"].endswith((".", "!", "?")) else 0)
                res.append((score, S[i]["s"], S[j]["e"], txt))
        res.sort(reverse=True); seen = []
        for sc, s, e, txt in res:
            if any(not (e <= a0 or s >= b0) for a0, b0 in seen): continue
            seen.append((s, e)); print(f"score {sc:4.2f}  in={s:.2f} out={e:.2f} ({e - s:.0f}s)\n   {txt[:240]}…\n")
            if len(seen) >= 10: break
        return
    for s in S:
        print(f"[{mmss(s['s'])}] {s['text']}" + ("  ||" if s["pause_after"] > 0.7 else ""))

if __name__ == "__main__":
    main()
