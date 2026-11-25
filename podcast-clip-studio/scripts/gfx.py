"""Graphics toolkit for vertical/horizontal clips: sprites, alpha blending, glow particles,
brand-styled captions, chips, stamps, bars, name tags and end cards. Pure PIL + numpy + OpenCV."""
import os, math, random
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT_DIR = os.environ.get("CLIP_FONTS", os.path.expanduser("~/.cache/podcast-clip-studio/fonts"))

def hexc(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

DEFAULT_BRAND = dict(bg="#F2E1C4", ink="#161416", accent="#E2A030", accent2="#AC3428", text="#FFFFFF",
                     font_head="Anton.ttf", font_body="DMSans.ttf")

class Brand:
    def __init__(self, d=None):
        d = {**DEFAULT_BRAND, **(d or {})}
        self.bg, self.ink, self.accent, self.accent2, self.text = (hexc(d[k]) for k in ("bg", "ink", "accent", "accent2", "text"))
        self.font_head, self.font_body = d["font_head"], d["font_body"]
        self._c = {}
    def _load(self, name, sz):
        for p in (os.path.join(FONT_DIR, name), name, "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
            if os.path.exists(p):
                return ImageFont.truetype(p, sz)
        return ImageFont.load_default()
    def head(self, sz):
        k = ("h", sz)
        if k not in self._c: self._c[k] = self._load(self.font_head, sz)
        return self._c[k]
    def body(self, sz, w=800):
        k = ("b", sz, w)
        if k not in self._c:
            f = self._load(self.font_body, sz)
            try:
                axes = f.get_variation_axes(); vals = []
                for a in axes:
                    n = a.get("name", b"")
                    n = n.decode() if isinstance(n, bytes) else str(n)
                    if "eight" in n or n.lower().startswith("wght"): vals.append(w)
                    elif "ptical" in n or n.lower().startswith("opsz"): vals.append(min(a["maximum"], max(a["minimum"], sz // 2)))
                    else: vals.append(a.get("default", a["minimum"]))
                f.set_variation_by_axes(vals)
            except Exception:
                pass
            self._c[k] = f
        return self._c[k]

W, H = 1080, 1920
def set_canvas(w, h):
    global W, H; W, H = w, h

def text_size(font, s, stroke=0):
    b = font.getbbox(s, stroke_width=stroke); return b[2] - b[0], b[3] - b[1], b

def star4(d, cx, cy, r, fill, thin=0.28):
    pts = []
    for k in range(8):
        a = math.pi / 4 * k - math.pi / 2; rr = r if k % 2 == 0 else r * thin
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=fill)

def check(d, x, y, s, fill, w=None):
    d.line([(x, y + s * 0.55), (x + s * 0.38, y + s * 0.9), (x + s, y + s * 0.1)], fill=fill, width=w or max(4, int(s * 0.18)), joint="curve")

def shadow_card(img, offset=(10, 10), color=(0, 0, 0, 255)):
    w, h = img.size
    out = Image.new("RGBA", (w + abs(offset[0]), h + abs(offset[1])), (0, 0, 0, 0))
    sh = Image.new("RGBA", img.size, color); sh.putalpha(img.split()[3].point(lambda v: min(v, color[3])))
    out.alpha_composite(sh, (max(0, offset[0]), max(0, offset[1]))); out.alpha_composite(img, (max(0, -offset[0]), max(0, -offset[1])))
    return out

def rot(im, deg): return im.rotate(deg, resample=Image.BICUBIC, expand=True)

# ---------------- sprites & blending ----------------
class Sprite:
    def __init__(self, im):
        im = im.convert("RGBA"); self.im = im
        a = np.asarray(im).astype(np.float32) / 255.0
        self.pm = a[:, :, [2, 1, 0]] * a[:, :, 3:4]; self.al = a[:, :, 3:4]
        self.w, self.h = im.size; self._sc = {}
    def scaled(self, s):
        s = round(s, 3)
        if abs(s - 1) < 1e-3: return self.pm, self.al
        if s not in self._sc:
            w, h = max(1, int(self.w * s)), max(1, int(self.h * s)); it = cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR
            if len(self._sc) > 40: self._sc.clear()
            self._sc[s] = (cv2.resize(self.pm, (w, h), interpolation=it), cv2.resize(self.al[:, :, 0], (w, h), interpolation=it)[:, :, None])
        return self._sc[s]

def blend(fr, sp, cx, cy, scale=1.0, alpha=1.0, anchor="c"):
    """fr: float32 BGR 0..1 (H,W,3). anchor 'c' = centre, 'tl' = top-left."""
    if alpha <= 0.003 or scale <= 0.01: return
    pm, al = sp.scaled(scale); h, w = al.shape[:2]; FH, FW = fr.shape[:2]
    x0, y0 = (int(round(cx - w / 2)), int(round(cy - h / 2))) if anchor == "c" else (int(round(cx)), int(round(cy)))
    fx0, fy0, fx1, fy1 = max(0, x0), max(0, y0), min(FW, x0 + w), min(FH, y0 + h)
    if fx0 >= fx1 or fy0 >= fy1: return
    p = pm[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0]; a = al[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0]
    if alpha < 1: p = p * alpha; a = a * alpha
    roi = fr[fy0:fy1, fx0:fx1]; roi *= (1 - a); roi += p

def glow_sprite(r, rgb):
    s = int(r * 6); y, x = np.mgrid[0:s, 0:s] - s / 2; d = np.sqrt(x ** 2 + y ** 2) / r
    a = np.exp(-d ** 2 * 1.2) + 0.6 * np.exp(-d * 3) * (d < 0.4)
    return (np.clip(a, 0, 1)[..., None] * np.array(rgb[::-1], np.float32)[None, None] / 255).astype(np.float32)

def add_glow(fr, g, x, y, a):
    h, w = g.shape[:2]; x0, y0 = int(x - w / 2), int(y - h / 2); FH, FW = fr.shape[:2]
    fx0, fy0, fx1, fy1 = max(0, x0), max(0, y0), min(FW, x0 + w), min(FH, y0 + h)
    if fx0 < fx1 and fy0 < fy1: fr[fy0:fy1, fx0:fx1] += g[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0] * a

class Particles:
    """Additive glowing sparkles (magic, confetti-light, dust)."""
    def __init__(self, seed=1, colors=((255, 220, 140), (255, 200, 110), (255, 235, 180), (190, 170, 255))):
        self.p = []; self.r = np.random.default_rng(seed); self.g = [glow_sprite(rr, c) for rr, c in zip((3, 5, 8, 4), colors)]
    def emit(self, n, x, y, spread=60, speed=(40, 220), up=-30, life=(0.8, 2.0)):
        for _ in range(n):
            a = self.r.uniform(0, 2 * np.pi); sp = self.r.uniform(*speed)
            self.p.append([x + self.r.normal(0, spread * .3), y + self.r.normal(0, spread * .3), math.cos(a) * sp, math.sin(a) * sp + up,
                           0.0, self.r.uniform(*life), int(self.r.integers(0, len(self.g))), self.r.uniform(0, 6.28)])
    def step(self, dt):
        for q in self.p: q[0] += q[2] * dt; q[1] += q[3] * dt; q[2] *= .985; q[3] = q[3] * .985 - 12 * dt; q[4] += dt
        self.p = [q for q in self.p if q[4] < q[5]]
    def draw(self, fr, t):
        for q in self.p:
            u = q[4] / q[5]; add_glow(fr, self.g[q[6]], q[0], q[1], (1 - u) * min(1, q[4] / .1) * (.6 + .4 * math.sin(t * 14 + q[7])))

def ease_out_back(x, s=1.7):
    x = min(max(x, 0), 1) - 1; return 1 + (s + 1) * x ** 3 + s * x ** 2
def ease_out(x): x = min(max(x, 0), 1); return 1 - (1 - x) ** 3
def ease_in_out(x): x = min(max(x, 0), 1); return 3 * x * x - 2 * x ** 3

# ---------------- brand elements ----------------
def is_kw(word):
    letters = [c for c in word if c.isalpha()]
    return (len(letters) >= 2 and all(c.isupper() for c in letters)) or any(c.isdigit() for c in word)

def caption(words, B, style="stroke", size=66, max_w=900, highlight=None):
    """TikTok-style caption. style: 'stroke' (white + black outline) | 'box' (text on dark box).
    Words in ALLCAPS, with digits, or listed in `highlight` get the accent colour."""
    hl = set(w.lower().strip(".,!?¿¡…:;\"'") for w in (highlight or []))
    f = B.body(size, 850); stroke = 7 if style == "stroke" else 0
    space = text_size(f, " ")[0] + 14; sizes = [text_size(f, w, stroke) for w in words]
    total = sum(s[0] for s in sizes) + space * (len(words) - 1)
    lines = [list(range(len(words)))]
    if total > max_w and len(words) > 1:
        best = min(range(1, len(words)), key=lambda k: max(sum(sizes[i][0] for i in range(k)) + space * (k - 1),
                                                             sum(sizes[i][0] for i in range(k, len(words))) + space * (len(words) - k - 1)))
        lines = [list(range(best)), list(range(best, len(words)))]
    lh = int(size * 1.3); lw = [sum(sizes[i][0] for i in ln) + space * (len(ln) - 1) for ln in lines]
    w, h = max(lw) + 70, lh * len(lines) + 40
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    if style == "box": d.rounded_rectangle([0, 0, w - 1, h - 1], radius=16, fill=B.ink + (225,))
    for li, ln in enumerate(lines):
        x = (w - lw[li]) / 2; y = 20 + li * lh
        for i in ln:
            wd = words[i]; key = wd.lower().strip(".,!?¿¡…:;\"'")
            col = B.accent if (is_kw(wd) or key in hl) else (B.bg if style == "box" else B.text)
            if style == "stroke":
                d.text((x - sizes[i][2][0] + 4, y + 12), wd, font=f, fill=(0, 0, 0, 110), stroke_width=stroke, stroke_fill=(0, 0, 0, 110))
                d.text((x - sizes[i][2][0], y + 8), wd, font=f, fill=col, stroke_width=stroke, stroke_fill=B.ink)
            else:
                d.text((x - sizes[i][2][0], y + 8), wd, font=f, fill=col)
            x += sizes[i][0] + space
    return Sprite(im)

def chip(text, B, size=74, fg=None, bg=None, border=False, padx=30, pady=14, deg=0, shadow=True):
    f = B.head(size); tw, th, b = text_size(f, text); w, h = tw + 2 * padx, th + 2 * pady
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w - 1, h - 1], fill=bg or B.ink, outline=B.ink if border else None, width=5 if border else 0)
    d.text((padx - b[0], pady - b[1]), text, font=f, fill=fg or B.bg)
    if shadow: im = shadow_card(im, (9, 9), (B.accent2 if (bg or B.ink) == B.ink else B.ink) + (255,))
    return rot(im, deg) if deg else im

def stamp(text, B, size=120, deg=-6, color=None):
    color = color or B.accent2; f = B.head(size); tw, th, b = text_size(f, text); w, h = tw + 80, th + 60
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w - 1, h - 1], fill=B.bg + (255,), outline=color, width=9); d.rectangle([14, 14, w - 15, h - 15], outline=color, width=3)
    d.text((40 - b[0], 30 - b[1]), text, font=f, fill=color)
    return rot(shadow_card(im, (10, 10), B.ink + (255,)), deg)

def star_bar(text, B, size=56, track=8, fg=None, bg=None, star=None):
    f = B.body(size, 800); chars = list(text); ws = [text_size(f, c)[0] for c in chars]
    tw = sum(ws) + track * (len(chars) - 1); th = text_size(f, "MH")[1]; w, h = tw + 220, th + 50
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im); d.rectangle([0, 0, w - 1, h - 1], fill=bg or B.ink)
    x = (w - tw) / 2; b = f.getbbox("M")
    for c, cw in zip(chars, ws): d.text((x, (h - th) / 2 - b[1]), c, font=f, fill=fg or B.bg); x += cw + track
    star4(d, 50, h / 2, 20, star or B.accent); star4(d, w - 50, h / 2, 20, star or B.accent)
    return im

def name_tag(name, sub, B):
    f1, f2 = B.head(70), B.body(32, 700); w1, h1, b1 = text_size(f1, name); w2, h2, b2 = text_size(f2, sub)
    w, h = max(w1, w2) + 70, 150
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w - 1, h - 1], fill=B.bg + (255,), outline=B.ink, width=5); d.rectangle([0, 0, 16, h], fill=B.accent)
    d.text((40 - b1[0], 14 - b1[1]), name, font=f1, fill=B.ink); d.text((40 - b2[0], 100 - b2[1]), sub, font=f2, fill=B.accent2)
    return shadow_card(im, (10, 10), B.ink + (255,))

def hook_card(text, B, width=940, size=92):
    """Big opening title (the 'hook'), wrapped to 2-3 lines, ink box with accent shadow."""
    f = B.head(size); words = text.split(); lines, cur = [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if text_size(f, t)[0] > width - 80 and cur: lines.append(cur); cur = w_
        else: cur = t
    lines.append(cur); lh = int(size * 1.12)
    h = lh * len(lines) + 70; im = Image.new("RGBA", (width, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, width - 1, h - 1], fill=B.ink)
    for i, ln in enumerate(lines):
        tw, th, b = text_size(f, ln); col = B.accent if i == len(lines) - 1 else B.bg
        d.text(((width - tw) / 2 - b[0], 35 + i * lh - b[1] + (lh - th) / 2), ln, font=f, fill=col)
    return shadow_card(im, (14, 14), B.accent2 + (255,))

def watermark(text, B, size=34):
    f = B.body(size, 800); tw, th, b = text_size(f, text); w, h = tw + 36, th + 20
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=8, fill=B.ink + (200,)); d.text((18 - b[0], 10 - b[1]), text, font=f, fill=B.bg)
    return Sprite(im)

def end_card(B, title, lines=(), image=None, cta=None, handle=None):
    """Full-frame closing card: optional image (poster/logo/cover), title, info lines, CTA button, handle."""
    im = Image.new("RGB", (W, H), B.bg); d = ImageDraw.Draw(im); y = int(H * 0.07)
    if image and os.path.exists(image):
        p = Image.open(image).convert("RGB"); s = min((W - 160) / p.width, (H * 0.48) / p.height)
        p = p.resize((int(p.width * s), int(p.height * s)), Image.LANCZOS); px = (W - p.width) // 2
        d.rectangle([px + 14, y + 14, px + p.width + 14, y + p.height + 14], fill=B.accent2)
        d.rectangle([px - 5, y - 5, px + p.width + 5, y + p.height + 5], fill=B.ink); im.paste(p, (px, y)); y += p.height + 60
    else:
        y = int(H * 0.25)
    f = B.head(96)
    for t in [title] if title else []:
        tw, th, b = text_size(f, t)
        while tw > W - 120 and f.size > 40: f = B.head(f.size - 6); tw, th, b = text_size(f, t)
        d.text(((W - tw) / 2 - b[0], y - b[1]), t, font=f, fill=B.ink); y += th + 36
    f2 = B.body(40, 700)
    for t in lines:
        tw, th, b = text_size(f2, t); d.text(((W - tw) / 2 - b[0], y - b[1]), t, font=f2, fill=B.accent2); y += th + 22
    if cta:
        y += 24; f3, f4 = B.head(54), B.body(40, 800); t3, t4 = cta[0], (cta[1] if len(cta) > 1 else "")
        w3, h3, b3 = text_size(f3, t3); w4, h4, b4 = text_size(f4, t4 or " ")
        bw = max(w3, w4) + 90; bh = h3 + (h4 + 16 if t4 else 0) + 54; bx = (W - bw) // 2
        d.rectangle([bx + 12, y + 12, bx + bw + 12, y + bh + 12], fill=B.accent2); d.rectangle([bx, y, bx + bw, y + bh], fill=B.ink)
        d.text(((W - w3) / 2 - b3[0], y + 22 - b3[1]), t3, font=f3, fill=B.bg)
        if t4: d.text(((W - w4) / 2 - b4[0], y + 38 + h3 - b4[1]), t4, font=f4, fill=B.accent)
        y += bh + 40
    if handle:
        f5 = B.body(44, 850); tw, th, b = text_size(f5, handle); d.text(((W - tw) / 2 - b[0], y - b[1]), handle, font=f5, fill=B.ink)
    return np.asarray(im)[:, :, ::-1].astype(np.float32) / 255
