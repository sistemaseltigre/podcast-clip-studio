#!/usr/bin/env python3
"""clipkit: render a finished social clip (vertical by default) from a JSON spec.

  python3 clipkit.py spec.json            # full render  -> spec["output"]
  python3 clipkit.py spec.json --stills 1.5,8,20   # contact sheet of chosen output times (fast QA)
  python3 clipkit.py spec.json --plan     # print the output timeline (after silence-tightening and speed)

See references/spec.md for every field. Minimal spec:
{
  "sources": {"main": "episode.mp4"},
  "transcript": "transcript.json",
  "output": "clip01.mp4",
  "segments": [{"in": 812.4, "out": 861.0}]
}
"""
import json, math, os, subprocess, sys, time
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gfx
from gfx import Brand, Sprite, blend, ease_out, ease_out_back, ease_in_out

# ---------------------------------------------------------------- spec & timeline
def load_spec(path):
    S = json.load(open(path)); base = os.path.dirname(os.path.abspath(path))
    def P(p): return p if (p is None or os.path.isabs(p)) else os.path.join(base, p)
    S["sources"] = {k: P(v) for k, v in S["sources"].items()}
    for k in ("transcript", "output"):
        if S.get(k): S[k] = P(S[k])
    if S.get("music", {}).get("file"): S["music"]["file"] = P(S["music"]["file"])
    if S.get("end_card", {}).get("image"): S["end_card"]["image"] = P(S["end_card"]["image"])
    for c in S.get("cards", []):
        if c.get("image"): c["image"] = P(c["image"])
    S.setdefault("width", 1080); S.setdefault("height", 1920); S.setdefault("fps", 30); S.setdefault("speed", 1.0)
    S.setdefault("audio_source", next(iter(S["sources"])))
    return S

def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:stream_side_data=rotation",
                          "-show_entries", "format=duration", "-of", "json", path], capture_output=True, text=True).stdout
    j = json.loads(out); st = (j.get("streams") or [{}])[0]
    w, h = st.get("width", 0), st.get("height", 0)
    rot = 0
    for sd in st.get("side_data_list", []) or []:
        if "rotation" in sd: rot = int(sd["rotation"])
    if abs(rot) in (90, 270): w, h = h, w
    return w, h, float(j["format"]["duration"])

def tighten(seg, words, max_gap, keep_gap):
    """Split a segment at silences longer than max_gap (from word timestamps); keep keep_gap of air."""
    ws = [w for w in words if w["e"] > seg["in"] and w["s"] < seg["out"]]
    if not ws or max_gap is None: return [(seg["in"], seg["out"])]
    parts, a = [], seg["in"]
    for i in range(len(ws) - 1):
        gap = ws[i + 1]["s"] - ws[i]["e"]
        if gap > max_gap:
            b = ws[i]["e"] + keep_gap; parts.append((a, min(b, seg["out"]))); a = max(seg["in"], ws[i + 1]["s"] - keep_gap * 0.7)
    parts.append((a, seg["out"]))
    return [(x, y) for x, y in parts if y - x > 0.08]

def build_timeline(S, words):
    tl, t = [], float(S.get("intro", {}).get("dur", 0.0)) if S.get("intro") else 0.0
    T = S.get("tighten", {"max_gap": 0.45, "keep_gap": 0.14})
    for k, seg in enumerate(S["segments"]):
        parts = tighten(seg, words, T.get("max_gap") if T else None, T.get("keep_gap", 0.14) if T else 0) if seg.get("tighten", True) else [(seg["in"], seg["out"])]
        for j, (a, b) in enumerate(parts):
            d = (b - a) / S["speed"]
            tl.append(dict(seg=k, part=j, src_in=a, src_out=b, t0=t, t1=t + d)); t += d
    return tl, t

def src_to_out(tl, s):
    for r in tl:
        if r["src_in"] - 1e-3 <= s <= r["src_out"] + 1e-3: return r["t0"] + (s - r["src_in"]) / SPEED
    return None

# ---------------------------------------------------------------- frame sources
class Reader:
    def __init__(self, path, start, w, h, vf=None):
        self.w, self.h = w, h
        args = ["ffmpeg", "-v", "error", "-ss", f"{max(0, start):.3f}", "-i", path, "-an"]
        if vf: args += ["-vf", vf]
        self.p = subprocess.Popen(args + ["-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE, bufsize=w * h * 3 * 2)
        self.idx, self.fr = -1, None
    def get(self, i):
        while self.idx < i:
            b = self.p.stdout.read(self.w * self.h * 3)
            if len(b) < self.w * self.h * 3: break
            self.fr = np.frombuffer(b, np.uint8).reshape(self.h, self.w, 3); self.idx += 1
        return self.fr if self.fr is not None else np.zeros((self.h, self.w, 3), np.uint8)
    def close(self):
        try: self.p.kill()
        except Exception: pass

def crop_to(fr, tw, th, zoom=1.0, fx=0.5, fy=0.42, flip=False):
    """Crop around focus point (fx,fy as fractions of the source) to aspect tw:th, zoom>=1 punches in."""
    h, w = fr.shape[:2]; asp = tw / th
    cw, ch = (h * asp, h) if w / h > asp else (w, w / asp)
    cw, ch = cw / zoom, ch / zoom
    x0 = min(max(0, fx * w - cw / 2), w - cw); y0 = min(max(0, fy * h - ch / 2), h - ch)
    M = np.float32([[tw / cw, 0, -x0 * tw / cw], [0, th / ch, -y0 * th / ch]])
    out = cv2.warpAffine(fr, M, (tw, th), flags=cv2.INTER_AREA if cw > tw * 1.2 else cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return out[:, ::-1] if flip else out

def fit_blur(fr, tw, th, box_w=None, y_center=0.5):
    """Landscape (or any) frame fitted to width over a blurred, darkened copy of itself (no crop)."""
    h, w = fr.shape[:2]; bw = box_w or tw; bh = int(h * bw / w)
    bg = crop_to(fr, tw // 8, th // 8); bg = cv2.GaussianBlur(bg, (0, 0), 6); bg = cv2.resize(bg, (tw, th)); bg = (bg * 0.45).astype(np.uint8)
    fg = cv2.resize(fr, (bw, bh), interpolation=cv2.INTER_AREA); y = int(th * y_center - bh / 2); x = (tw - bw) // 2
    y0, y1 = max(0, y), min(th, y + bh); bg[y0:y1, x:x + bw] = fg[y0 - y:y1 - y]
    return bg

# ---------------------------------------------------------------- main renderer
def main():
    global SPEED
    spec_path = sys.argv[1]; S = load_spec(spec_path); SPEED = S["speed"]
    W, H, FPS = S["width"], S["height"], S["fps"]; gfx.set_canvas(W, H)
    B = Brand(S.get("brand"))
    T = json.load(open(S["transcript"])) if S.get("transcript") else {"words": []}
    words = T["words"]
    tl, body_end = build_timeline(S, words)
    end_dur = float(S.get("end_card", {}).get("dur", 0)) if S.get("end_card") else 0
    TOTAL = body_end + end_dur; NF = int(round(TOTAL * FPS))
    if "--plan" in sys.argv:
        for r in tl: print(f"seg{r['seg']}.{r['part']}  src {r['src_in']:8.2f}-{r['src_out']:8.2f}  ->  out {r['t0']:6.2f}-{r['t1']:6.2f}")
        print(f"body {body_end:.2f}s  total {TOTAL:.2f}s"); return
    json.dump(dict(timeline=tl, total=TOTAL, body_end=body_end, speed=SPEED, intro=tl[0]["t0"] if tl else 0), open(S["output"] + ".timeline.json", "w"), indent=1)

    # --- captions mapped onto the output timeline
    C = S.get("captions", {"enabled": True})
    subs = []
    if C.get("enabled", True) and words:
        mapped = []
        for w in words:
            a = src_to_out(tl, (w["s"] + w["e"]) / 2)
            if a is None: continue
            dur = (w["e"] - w["s"]) / SPEED; mapped.append(dict(s=a - dur / 2, e=a + dur / 2, w=w["w"]))
        maxc = C.get("max_chars", 16); cur = []
        def flush():
            if cur: subs.append([cur[0]["s"], cur[-1]["e"], [x["w"].upper() if C.get("uppercase") else x["w"] for x in cur]])
        for i, w in enumerate(mapped):
            if cur and (w["s"] - cur[-1]["e"] > 0.6): flush(); cur = []
            cur.append(w); ln = len(" ".join(x["w"] for x in cur))
            if ln >= maxc or w["w"].endswith((".", "?", "!", "…", ",")) and ln > 6: flush(); cur = []
        flush()
        for k in range(len(subs) - 1):
            subs[k][1] = subs[k + 1][0] if subs[k + 1][0] - subs[k][1] < 0.4 else subs[k][1] + 0.2
        if subs: subs[-1][1] += 0.3
        subs = [(a, b, gfx.caption(ws, B, C.get("style", "stroke"), C.get("size", 66), highlight=C.get("highlight"))) for a, b, ws in subs]
    CAP_Y = C.get("y", 0.74) * H

    # --- overlays (hook, cards, name tags)
    events, sfx = [], []
    def add(t0, t1, im, x, y, anim="pop", sound="pop", scale=1.0):
        sp = im if isinstance(im, Sprite) else Sprite(im); events.append(dict(t0=t0, t1=t1, sp=sp, x=x, y=y, anim=anim, scale=scale))
        if sound: sfx.append((t0, sound))
    hook = S.get("hook")
    if hook:
        hs = float(hook.get("start", 0.0)); add(hs, hs + float(hook.get("dur", 2.6)), gfx.hook_card(hook["text"], B, size=hook.get("size", 92)),
                                                W / 2, hook.get("y", 0.2) * H, anim="stamp", sound="whoosh")
    for c in S.get("cards", []):
        t0 = src_to_out(tl, c["at"]) if "at" in c else c.get("t", 0)
        if t0 is None: print("card outside clip, skipped:", c.get("text")); continue
        st = c.get("style", "chip"); deg = c.get("deg", 0)
        if st == "chip": im = gfx.chip(c["text"], B, c.get("size", 74), fg=gfx.hexc(c["fg"]) if c.get("fg") else None,
                                       bg=gfx.hexc(c["bg"]) if c.get("bg") else None, deg=deg)
        elif st == "accent": im = gfx.chip(c["text"], B, c.get("size", 74), fg=B.ink, bg=B.accent, deg=deg)
        elif st == "stamp": im = gfx.stamp(c["text"], B, c.get("size", 120), deg=deg or -6)
        elif st == "bar": im = gfx.star_bar(c["text"], B, c.get("size", 50))
        elif st == "name": im = gfx.name_tag(c["text"], c.get("sub", ""), B)
        elif st == "image":
            from PIL import Image as _I; im = _I.open(c["image"]).convert("RGBA"); sc = c.get("width", 700) / im.width
            im = gfx.shadow_card(im.resize((int(im.width * sc), int(im.height * sc)), _I.LANCZOS), (12, 12), B.ink + (255,))
        else: raise SystemExit("unknown card style " + st)
        x = c.get("x", 0.5) * W
        if st == "name": x = 50 + im.width / 2
        add(t0, t0 + c.get("dur", 2.0), im, x, c.get("y", 0.6) * H, anim=c.get("anim", "stamp" if st == "stamp" else ("slide" if st == "name" else "pop")),
            sound=c.get("sound", "stamp" if st == "stamp" else ("whoosh" if st == "name" else "pop")))
    WM = gfx.watermark(S["watermark"], B) if S.get("watermark") else None
    PROG = S.get("progress_bar", False)
    EC = S.get("end_card")
    END_IMG = gfx.end_card(B, EC.get("title"), EC.get("lines", []), EC.get("image"), EC.get("cta"), EC.get("handle")) if EC else None
    if EC: sfx.append((body_end, "whoosh"))
    for r in tl[1:]:
        if r["part"] == 0 and S.get("sfx_on_cuts"): sfx.append((r["t0"], "whoosh"))
    json.dump(dict(sfx=sorted(sfx), total=TOTAL), open(S["output"] + ".sfx.json", "w"))

    # --- per-segment framing
    srcinfo = {k: probe(v) for k, v in S["sources"].items()}
    readers = {}; used = {}; FRAME = [0]
    def frame_of(cam, src_t, r_key, tw, th, sg):
        path = S["sources"][cam]; sw, sh, _ = srcinfo[cam]
        key = (cam, r_key); used[key] = FRAME[0]
        if key not in readers:
            for k in [k for k in readers if used.get(k, -9) < FRAME[0] - 1]: readers.pop(k)[0].close()
            # pre-scale big sources (4K) to at most 2x output for speed
            sc = min(1.0, 2.0 * max(tw / sw, th / sh)) if sw > 0 else 1.0
            vf = f"scale={int(sw * sc) // 2 * 2}:{int(sh * sc) // 2 * 2}" if sc < 0.95 else None
            readers[key] = (Reader(path, src_t, int(sw * sc) // 2 * 2 if vf else sw, int(sh * sc) // 2 * 2 if vf else sh, vf), src_t)
        rd, st0 = readers[key]
        return rd.get(int(round((src_t - st0) * FPS)))

    def render_body(fi):
        t = fi / FPS
        r = next((x for x in tl if x["t0"] <= t < x["t1"]), tl[-1] if t >= tl[-1]["t0"] else tl[0])
        sg = S["segments"][r["seg"]]; src_t = r["src_in"] + (min(t, r["t1"] - 1e-3) - r["t0"]) * SPEED
        lay = sg.get("layout", S.get("layout", "fill"))
        seg_span = sum(x["t1"] - x["t0"] for x in tl if x["seg"] == r["seg"]); seg_t0 = min(x["t0"] for x in tl if x["seg"] == r["seg"])
        prog = (t - seg_t0) / max(0.01, seg_span)
        # alternate zoom on jump cuts inside a segment so they read as camera angles
        z = sg.get("zoom", 1.0) * (1 + sg.get("push", 0.03) * prog) * (sg.get("cut_zoom", 1.08) if r["part"] % 2 else 1.0)
        fx, fy = sg.get("focus", S.get("focus", [0.5, 0.42])); flip = sg.get("flip", S.get("flip", False))
        cam = sg.get("cam", S["audio_source"])
        if lay == "split":
            top, bot = sg.get("top", cam), sg.get("bottom", cam)
            tt = sg["top_time"] + (t - seg_t0) * SPEED if "top_time" in sg else src_t
            bt = sg["bottom_time"] + (t - seg_t0) * SPEED if "bottom_time" in sg else src_t
            ft = frame_of(top, tt, (r["seg"], "t", r["part"] if "top_time" not in sg else 0), W, H // 2, sg)
            fb = frame_of(bot, bt, (r["seg"], "b", r["part"] if "bottom_time" not in sg else 0), W, H // 2, sg)
            ftop = sg.get("top_focus", [fx, fy]); fbot = sg.get("bottom_focus", [fx, fy])
            img = np.vstack([crop_to(ft, W, H // 2, sg.get("zoom", 1.0), *ftop, flip), crop_to(fb, W, H - H // 2, sg.get("zoom", 1.0), *fbot, flip)])
            img[H // 2 - 4:H // 2 + 4] = np.array(B.bg[::-1], np.uint8)
        else:
            fr = frame_of(cam, src_t, (r["seg"], r["part"]), W, H, sg)
            if lay == "fit": img = fit_blur(fr, W, H, sg.get("box_w"), sg.get("y_center", 0.42))
            else: img = crop_to(fr, W, H, z, fx, fy, flip)
        return img.astype(np.float32) / 255

    def anim(e, t):
        u = t - e["t0"]; al = min(1, (e["t1"] - t) / 0.15, u / 0.08)
        a = e["anim"]
        if a == "stamp": return (1.8 - 0.8 * ease_out(u / 0.22) if u < 0.22 else 1), al, 0
        if a == "slide": return 1, al, -(1 - ease_out(u / 0.35)) * 800
        if a == "fade": return 1, min(1, (e["t1"] - t) / 0.3, u / 0.3), 0
        return (0.6 + 0.4 * ease_out_back(u / 0.28) if u < 0.28 else 1), al, 0

    def render(fi):
        t = fi / FPS; FRAME[0] = fi
        if EC and t >= body_end:
            fr = END_IMG.copy(); u = (t - body_end) / 0.3
            if u < 1:  # wipe up
                prev = render_body(int(body_end * FPS) - 1); yoff = int(H * (1 - ease_in_out(u))); prev[yoff:] = END_IMG[:H - yoff]; fr = prev
            return fr
        fr = render_body(fi)
        if WM is not None: blend(fr, WM, W - 30 - WM.w, 0.09 * H, anchor="tl", alpha=0.9)
        for e in events:
            if e["t0"] <= t < e["t1"]:
                sc, al, dx = anim(e, t); blend(fr, e["sp"], e["x"] + dx, e["y"], scale=sc * e["scale"], alpha=al)
        for a, b, sp in subs:
            if a <= t < b:
                p = (t - a) / 0.12; blend(fr, sp, W / 2, CAP_Y, scale=0.88 + 0.12 * ease_out_back(p) if p < 1 else 1.0); break
        if PROG:
            fr[H - 14:H, :int(W * t / body_end)] = np.array(B.accent[::-1], np.float32) / 255
        return fr

    if "--stills" in sys.argv:
        ts = [float(x) for x in sys.argv[sys.argv.index("--stills") + 1].split(",")]
        ims = []
        for x in ts:
            for k in list(readers): readers.pop(k)[0].close()
            im = (np.clip(render(int(x * FPS)), 0, 1) * 255).astype(np.uint8)
            im = cv2.resize(im, (270, int(270 * H / W))); cv2.putText(im, f"{x:.1f}s", (6, 24), 0, 0.7, (0, 255, 255), 2); ims.append(im)
        while len(ims) % 6: ims.append(np.zeros_like(ims[0]))
        out = os.path.splitext(S["output"])[0] + "_stills.jpg"
        cv2.imwrite(out, np.vstack([np.hstack(ims[k:k + 6]) for k in range(0, len(ims), 6)])); print(out); return

    tmpv = S["output"] + ".video.mp4"
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                            "-c:v", "libx264", "-preset", S.get("preset", "medium"), "-crf", str(S.get("crf", 18)), "-pix_fmt", "yuv420p", tmpv], stdin=subprocess.PIPE)
    t0 = time.time()
    for fi in range(NF):
        enc.stdin.write((np.clip(render(fi), 0, 1) * 255).astype(np.uint8).tobytes())
        if fi % 300 == 0: print(f"frame {fi}/{NF}  {time.time() - t0:.0f}s", flush=True)
    enc.stdin.close(); enc.wait()
    for k in list(readers): readers.pop(k)[0].close()
    print("video done, mixing audio...", flush=True)
    # audio
    here = os.path.dirname(os.path.abspath(__file__))
    subprocess.run([sys.executable, os.path.join(here, "mix.py"), spec_path], check=True)

if __name__ == "__main__":
    main()
