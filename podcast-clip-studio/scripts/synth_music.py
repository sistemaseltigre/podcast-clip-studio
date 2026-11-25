#!/usr/bin/env python3
"""Pure-numpy music generator (no FluidSynth needed). 100 % original, procedurally arranged from hand-written patterns.

  python3 synth_music.py --style lofi --dur 60 --out bgm.wav
  python3 synth_music.py --style cinematic --dur 13 --then rumba --switch 12.9 --total 48 --out bgm.wav --impacts 1.25
  python3 synth_music.py --list

Styles: lofi (chill podcast bed), upbeat (pop/energetic), rumba (Spanish guitar + palmas), cinematic (mysterious
magic waltz: celesta + strings + timpani), suspense (drone + pulses), corporate (bright, light piano + claps).
--then/--switch: change style at a time (with a record-scratch and a downbeat), e.g. a movie intro that turns into a groove.
Loudness: the file is peak-normalized; mix.py levels and ducks it under the voice.
For richer orchestral cues, use bgm_motor.py (FluidSynth) — see references/music.md.
"""
import argparse, numpy as np, soundfile as sf
from scipy.signal import lfilter, butter, sosfilt, fftconvolve

SR = 44100
rng = np.random.default_rng(7)
NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
def m(s): return 12 * (int(s[-1]) + 1) + NOTE[s[:-1]]
def hz(n): return 440.0 * 2 ** ((n - 69) / 12)
def lp(x, f, o=2): return sosfilt(butter(o, f / (SR / 2), output="sos"), x)
def hp(x, f, o=2): return sosfilt(butter(o, f / (SR / 2), btype="high", output="sos"), x)
def place(buf, x, t, g=1.0):
    i = int(t * SR)
    if i >= len(buf) or i + len(x) <= 0: return
    if i < 0: x = x[-i:]; i = 0
    seg = buf[i:i + len(x)]; seg += g * x[:len(seg)]
def reverb(x, secs=2.4, mix=0.3, damp=4000):
    n = int(secs * SR); t = np.arange(n) / SR; ir = lp(rng.standard_normal(n) * np.exp(-t * 6.9 / secs), damp); ir /= np.sqrt((ir ** 2).sum())
    return (1 - mix) * x + mix * 2.2 * fftconvolve(x, ir)[:len(x)]

# ---------------- instruments ----------------
def celesta(f, dur, vel=1.0):
    n = int((dur + 1.6) * SR); t = np.arange(n) / SR
    y = np.sin(2 * np.pi * f * t) + .35 * np.sin(4 * np.pi * f * t) * np.exp(-t * 3) + .18 * np.sin(2 * np.pi * 4.01 * f * t) * np.exp(-t * 6)
    return vel * .28 * y * np.minimum(1, t / .003) * np.exp(-t * 2.2)
def epiano(f, dur, vel=1.0):
    n = int((dur + .8) * SR); t = np.arange(n) / SR
    y = np.sin(2 * np.pi * f * t + 1.2 * np.exp(-t * 5) * np.sin(2 * np.pi * f * t)) * (1 + .15 * np.sin(2 * np.pi * 5 * t))
    return vel * .22 * y * np.minimum(1, t / .004) * np.exp(-t * 1.3) * np.clip((dur + .8 - t) / .3, 0, 1)
def pad(freqs, dur, att=.8, rel=1.2, bright=1600):
    n = int((dur + rel) * SR); t = np.arange(n) / SR; y = np.zeros(n)
    for f in freqs:
        for det in (-.12, 0, .11): y += 2 * ((f * 2 ** (det / 12) * t + rng.uniform()) % 1) - 1
    return .22 * lp(y / (3 * len(freqs)), bright) * np.clip(t / att, 0, 1) * np.clip((dur + rel - t) / rel, 0, 1)
def pizz(f, vel=1.0):
    n = int(1.2 * SR); t = np.arange(n) / SR
    return vel * .35 * (np.sin(2 * np.pi * f * t) + .3 * np.sin(4 * np.pi * f * t)) * np.minimum(1, t / .004) * np.exp(-t * 5)
def timpani(f=41.2, vel=1.0):
    n = int(2.5 * SR); t = np.arange(n) / SR
    return vel * .9 * (np.sin(2 * np.pi * (f + 25 * np.exp(-t * 8)) * t) * np.exp(-t * 1.6) + .3 * lp(rng.standard_normal(n), 300) * np.exp(-t * 10))
def cymbal_swell(dur=1.0):
    n = int((dur + 1.5) * SR); t = np.arange(n) / SR
    return .12 * hp(rng.standard_normal(n), 5000) * np.where(t < dur, (t / dur) ** 3, np.exp(-(t - dur) * 3))
def ks(f, dur, bright=.5, decay=.996, vel=1.0):
    n = int(dur * SR); P = max(2, int(round(SR / f))); exc = np.zeros(n)
    exc[:P] = lfilter([bright, 1 - bright], [1], rng.uniform(-1, 1, P))
    a = np.zeros(P + 2); a[0] = 1; a[P] = a[P + 1] = -decay * .5
    return vel * .45 * lp(lfilter([1], a, exc), 5200)
def strum(buf, notes, t0, down=True, spread=.012, vel=1.0, dur=1.0, decay=.994):
    for k, nn in enumerate(notes if down else notes[::-1]):
        place(buf, ks(hz(nn), dur, .55 if down else .7, decay, vel * (.9 + .2 * rng.random())), t0 + k * spread)
def kick(vel=1.0):
    n = int(.35 * SR); t = np.arange(n) / SR
    return vel * .9 * np.sin(2 * np.pi * np.cumsum(48 + 90 * np.exp(-t * 35)) / SR) * np.exp(-t * 9)
def snare(vel=1.0):
    n = int(.25 * SR); t = np.arange(n) / SR
    return vel * (.35 * hp(rng.standard_normal(n), 1500) * np.exp(-t * 22) + .25 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30))
def clap(vel=1.0):
    n = int(.25 * SR); t = np.arange(n) / SR
    nz = sosfilt(butter(2, [900 / (SR / 2), 5000 / (SR / 2)], btype="band", output="sos"), rng.standard_normal(n)); e = np.zeros(n)
    for d in (0, .009, .019): e += (t >= d) * np.exp(-np.maximum(0, t - d) * 60)
    return vel * .32 * nz * (e + (t >= .028) * np.exp(-np.maximum(0, t - .028) * 18))
def hat(vel=1.0, open_=False):
    n = int((.25 if open_ else .06) * SR); t = np.arange(n) / SR
    return vel * .09 * hp(rng.standard_normal(n), 7000) * np.exp(-t * (12 if open_ else 60))
def bass(f, dur, vel=1.0):
    n = int((dur + .1) * SR); t = np.arange(n) / SR
    y = np.sin(2 * np.pi * f * t) + .25 * np.sin(4 * np.pi * f * t) + .1 * np.sign(np.sin(2 * np.pi * f * t))
    return vel * .42 * lp(y, 900) * np.minimum(1, t / .005) * np.exp(-t * 2.5) * np.clip((dur + .1 - t) / .1, 0, 1)
def scratch():
    n = int(.45 * SR); t = np.arange(n) / SR; rate = np.where(t < .2, 1 - t / .2 * 1.8, -.8 + (t - .2) * 4)
    base = lp(rng.standard_normal(n * 2), 2500); y = base[np.clip(np.cumsum(np.abs(rate)), 0, len(base) - 1).astype(int)] * np.abs(rate)
    y = sosfilt(butter(2, [300 / (SR / 2), 3000 / (SR / 2)], btype="band", output="sos"), y)
    return .6 * y / (np.abs(y).max() + 1e-9) * np.minimum(1, t / .01) * np.clip((.45 - t) / .1, 0, 1)
def vinyl(n):
    crack = (rng.random(n) > .9995) * rng.uniform(-.6, .6, n); return .02 * lp(rng.standard_normal(n), 3000) + lp(crack, 6000)
def chord(name, octave=3):
    root = name[0] + (name[1] if len(name) > 1 and name[1] in "#b" else ""); q = name[len(root):]
    r = m(root + str(octave))
    iv = {"": [0, 4, 7], "m": [0, 3, 7], "7": [0, 4, 7, 10], "maj7": [0, 4, 7, 11], "m7": [0, 3, 7, 10], "sus4": [0, 5, 7], "dim": [0, 3, 6]}[q]
    return [r + i for i in iv]

# ---------------- styles: each writes into buf between t0 and t1 ----------------
def style_cinematic(buf, t0, t1, impacts=(), sparkles=()):
    bt = 60 / 92; bar = 3 * bt
    prog = [["E3", "B3", "G4"], ["D3", "A3", "F#4"], ["C3", "G3", "E4"], ["B2", "F#3", "D#4"]] * 2
    prog[4:] = [["E3", "B3", "G4"], ["C3", "G3", "E4"], ["A2", "E3", "C4"], ["B2", "F#3", "D#4"]]
    mel = [(0, 0, "E5", 1), (0, 1, "G5", 1), (0, 2, "B5", 1), (1, 0, "A5", 2), (1, 2, "F#5", 1), (2, 0, "G5", 1), (2, 1, "E5", 1), (2, 2, "C5", 1),
           (3, 0, "D#5", 2.5), (4, 0, "B4", 1), (4, 1, "E5", 1), (4, 2, "G5", 1), (5, 0, "C6", 2), (5, 2, "B5", 1), (6, 0, "A5", 1), (6, 1, "G5", 1),
           (6, 2, "E5", 1), (7, 0, "F#5", 1.5), (7, 1.5, "D#5", 1.5)]
    b = 0
    while t0 + b * bar < t1:
        t = t0 + b * bar; ch = prog[b % 8]
        place(buf, pad([hz(m(x)) for x in ch], bar, .5 if b else 1.2, 1.0, 1400), t)
        place(buf, pizz(hz(m(ch[0]) - 12)), t, .9)
        for k in (1, 2): place(buf, pizz(hz(m(ch[1]))), t + k * bt, .35)
        for (bb, beat, nn, d) in mel:
            if bb == b % 8 and t + beat * bt < t1 - .2:
                place(buf, celesta(hz(m(nn)), d * bt), t + beat * bt); place(buf, celesta(hz(m(nn) + 12), d * bt, .25), t + beat * bt)
        b += 1
    for t in impacts: place(buf, cymbal_swell(.9), t - .9); place(buf, timpani(), t)
    for t in sparkles:
        for k, nn in enumerate(["E6", "G6", "B6", "E7", "G7"]): place(buf, celesta(hz(m(nn)), .2, .5), t + k * .045)
    return 3.0, .42

def style_rumba(buf, t0, t1, **_):
    bb = 60 / 118; bar = 4 * bb
    prog = [(["A2", "E3", "A3", "C4", "E4"], "A1"), (["G2", "D3", "G3", "B3", "D4"], "G1"), (["F2", "C3", "F3", "A3", "C4"], "F1"), (["E2", "B2", "E3", "G#3", "B3"], "E1")]
    pat = [(0, True, 1), (1, True, .7), (1.5, False, .55), (2, True, .85), (2.75, False, .5), (3, True, .75), (3.5, False, .55)]
    hook = [(0, "E5"), (.5, "A5"), (1, "C6"), (1.5, "B5"), (2, "A5"), (3, "G5"), (3.5, "E5")]
    b = 0
    while t0 + b * bar < t1 - .05:
        t = t0 + b * bar; notes, root = prog[b % 4]; nm = [m(x) for x in notes]
        for o, d, v in pat:
            if t + o * bb < t1: strum(buf, nm, t + o * bb, d, vel=v * .8, dur=.9)
        for k in range(4):
            if t + k * bb < t1:
                place(buf, kick(.8), t + k * bb)
                if k in (1, 3): place(buf, clap(), t + k * bb)
        for k in range(8):
            if t + k * bb / 2 < t1: place(buf, hat(.9 if k % 2 else .5), t + k * bb / 2)
        for off in (1.5, 3.75):
            if t + off * bb < t1: place(buf, clap(.45), t + off * bb)
        for o, iv, d, v in [(0, 12, 1.5, 1), (1.5, 12, .9, .8), (2.5, 19, .9, .7), (3, 12, .9, .8)]:
            if t + o * bb < t1: place(buf, bass(hz(m(root) + iv), bb * d, v), t + o * bb)
        if b % 2 == 1:
            for o, nn in hook:
                if t + o * bb < t1 - .1: place(buf, ks(hz(m(nn) - 12), .8, .4, .995, .55), t + o * bb)
        b += 1
    strum(buf, [m(x) for x in ["E2", "B2", "E3", "G#3", "B3", "E4"]], t1, True, .03, 1.0, 2.6, .998); place(buf, kick(), t1); place(buf, bass(hz(m("E2")), 2), t1)
    return 1.2, .18

def style_lofi(buf, t0, t1, **_):
    bb = 60 / 78; bar = 4 * bb
    prog = ["Dm7", "G7", "Cmaj7", "Am7"]
    mel = [(0, "A4"), (1.5, "C5"), (2, "D5"), (3, "F5"), (4.5, "E5"), (6, "C5"), (7, "A4")]
    b = 0
    while t0 + b * bar < t1:
        t = t0 + b * bar; ch = chord(prog[b % 4], 3)
        for k, nn in enumerate(ch + [ch[1] + 12]): place(buf, epiano(hz(nn), bar * .95, .8), t + k * .02)
        place(buf, bass(hz(ch[0] - 12), bb * 2.5, .9), t); place(buf, bass(hz(ch[0] - 12), bb * 1.2, .7), t + 2.5 * bb)
        for k in range(4):
            sw = .06 if k % 2 else 0
            if k in (0, 2): place(buf, kick(.7), t + k * bb + (0.5 * bb if k == 2 and b % 2 else 0))
            if k in (1, 3): place(buf, snare(.55), t + k * bb)
            for h in (0, .5): place(buf, hat(.55 if h else .35), t + (k + h) * bb + (sw if h else 0))
        if b % 4 >= 2:
            for o, nn in mel:
                if (b % 2) * 4 <= o < (b % 2) * 4 + 4: place(buf, ks(hz(m(nn)), 1.2, .3, .996, .45), t + (o - (b % 2) * 4) * bb)
        b += 1
    buf[int(t0 * SR):int(t1 * SR)] += vinyl(int(t1 * SR) - int(t0 * SR))[:len(buf[int(t0 * SR):int(t1 * SR)])]
    return 1.6, .25

def style_upbeat(buf, t0, t1, **_):
    bb = 60 / 120; bar = 4 * bb
    prog = ["C", "G", "Am", "F"]; hook = [(0, "E5"), (.5, "G5"), (1, "A5"), (2, "G5"), (2.5, "E5"), (3, "D5")]
    b = 0
    while t0 + b * bar < t1:
        t = t0 + b * bar; ch = chord(prog[b % 4], 4)
        for k in range(8):
            if t + k * bb / 2 < t1:
                for nn in ch: place(buf, ks(hz(nn), .35, .7, .99, .35), t + k * bb / 2)
        for k in range(4):
            place(buf, kick(.9), t + k * bb); place(buf, hat(.7, open_=True), t + (k + .5) * bb)
            if k in (1, 3): place(buf, clap(.9), t + k * bb)
        place(buf, bass(hz(ch[0] - 24), bb * 1.8), t); place(buf, bass(hz(ch[0] - 24), bb * 1.8), t + 2 * bb)
        if b >= 2:
            for o, nn in hook: place(buf, celesta(hz(m(nn)), .3, .6), t + o * bb)
        b += 1
    return 1.0, .15

def style_suspense(buf, t0, t1, **_):
    bb = 60 / 100; n = int((t1 - t0) * SR); t = np.arange(n) / SR
    drone = .18 * lp(np.sin(2 * np.pi * hz(m("D2")) * t) + .5 * np.sin(2 * np.pi * hz(m("A2")) * t * 1.003) + .3 * (2 * ((hz(m("D3")) * t) % 1) - 1), 700)
    place(buf, drone * np.clip(t / 2, 0, 1), t0)
    k = 0
    while t0 + k * bb / 2 < t1:
        place(buf, pizz(hz(m("D3") + [0, 0, 1, 0][k % 4]), .7), t0 + k * bb / 2); k += 1
    for j in range(int((t1 - t0) / (4 * bb))): place(buf, timpani(36.7, .6), t0 + j * 4 * bb)
    return 3.0, .4

def style_corporate(buf, t0, t1, **_):
    bb = 60 / 110; bar = 4 * bb; prog = ["F", "C", "Dm", "Bb"]
    b = 0
    while t0 + b * bar < t1:
        t = t0 + b * bar; ch = chord(prog[b % 4], 4)
        for k in range(8): place(buf, epiano(hz(ch[k % 3] + (12 if k % 4 == 3 else 0)), bb * .45, .55), t + k * bb / 2)
        place(buf, bass(hz(ch[0] - 24), bar * .9), t)
        for k in range(4):
            place(buf, kick(.6), t + k * bb)
            if k in (1, 3): place(buf, clap(.6), t + k * bb)
        b += 1
    return 1.4, .2

STYLES = dict(cinematic=style_cinematic, rumba=style_rumba, lofi=style_lofi, upbeat=style_upbeat, suspense=style_suspense, corporate=style_corporate)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", default="lofi"); ap.add_argument("--dur", type=float, default=60); ap.add_argument("--out", default="bgm.wav")
    ap.add_argument("--then"); ap.add_argument("--switch", type=float); ap.add_argument("--total", type=float)
    ap.add_argument("--impacts", default=""); ap.add_argument("--sparkles", default=""); ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list: print("\n".join(STYLES)); return
    global rng; rng = np.random.default_rng(a.seed)
    total = a.total or a.dur; N = int((total + 4) * SR)
    imp = [float(x) for x in a.impacts.split(",") if x]; spk = [float(x) for x in a.sparkles.split(",") if x]
    if a.then:
        A = np.zeros(N); B = np.zeros(N); sw = a.switch
        rv = STYLES[a.style](A, .25, sw, impacts=imp, sparkles=spk); A = reverb(A, *rv)
        fade = np.ones(N); i0, i1 = int((sw - .05) * SR), int((sw + .35) * SR); fade[i0:i1] = np.linspace(1, 0, i1 - i0); fade[i1:] = 0; A *= fade
        rv = STYLES[a.then](B, sw + .3, total - 1.2); B = reverb(B, *rv); place(B, scratch(), sw - .1, .9)
        mix = A + .9 * B
    else:
        buf = np.zeros(N); rv = STYLES[a.style](buf, .1, total - .3, impacts=imp, sparkles=spk); mix = reverb(buf, *rv)
    mix = mix[:int(total * SR)]; fo = int(min(1.5, total / 4) * SR); mix[-fo:] *= np.linspace(1, 0, fo)
    mix = mix / (np.abs(mix).max() + 1e-9) * .89
    st = np.stack([mix, np.concatenate([np.zeros(300), mix[:-300]]) * .6 + mix * .4], 1)
    sf.write(a.out, st.astype(np.float32), SR); print(a.out, f"{total:.1f}s")

if __name__ == "__main__":
    main()
