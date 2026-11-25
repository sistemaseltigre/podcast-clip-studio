#!/usr/bin/env python3
"""Synthesized sound effects (100 % original, no samples, no rights issues).

  python3 sfx.py events.json out.wav [total_seconds]
      events.json = {"sfx": [[time_s, "pop"], [2.5, "whoosh"], ...]}
  python3 sfx.py --demo demo.wav            # every sound in a row, to audition

Sounds: pop, tick, whoosh, stamp, clap, ding, sparkle, boom, boom_small, scratch, buzz, riser, swoosh_down, glitch
"""
import json, sys
import numpy as np, soundfile as sf
from scipy.signal import butter, sosfilt

SR = 48000
rng = np.random.default_rng(1)

def env(n, a=0.002, d=0.08):
    t = np.arange(n) / SR; return np.minimum(1, t / a) * np.exp(-t / d)
def bandnoise(n, lo, hi):
    x = rng.standard_normal(n); X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1 / SR); X[(f < lo) | (f > hi)] = 0
    y = np.fft.irfft(X, n); return y / (np.abs(y).max() + 1e-9)

def pop():
    n = int(.12 * SR); t = np.arange(n) / SR; f = 900 * np.exp(-t * 18) + 280
    return .6 * np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, .001, .035)
def tick():
    n = int(.06 * SR); t = np.arange(n) / SR
    return .5 * (np.sin(2 * np.pi * 2400 * t) + .5 * np.sin(2 * np.pi * 3600 * t)) * env(n, .0005, .012)
def whoosh():
    n = int(.35 * SR); t = np.arange(n) / SR; return .35 * bandnoise(n, 400, 5000) * np.sin(np.pi * t / t[-1]) ** 2
def swoosh_down():
    n = int(.5 * SR); t = np.arange(n) / SR; y = bandnoise(n, 150, 2500) * np.sin(np.pi * t / t[-1]) ** 2
    return .35 * sosfilt(butter(2, 1800 / (SR / 2), output="sos"), y)
def stamp():
    n = int(.25 * SR); t = np.arange(n) / SR
    return .8 * np.sin(2 * np.pi * (70 + 60 * np.exp(-t * 30)) * t) * env(n, .001, .06) + .35 * bandnoise(n, 200, 4000) * env(n, .0005, .02)
def clap():
    n = int(.3 * SR); return .9 * (bandnoise(n, 800, 9000) * env(n, .0003, .03) + .4 * np.sin(2 * np.pi * 180 * np.arange(n) / SR) * env(n, .001, .03))
def ding():
    n = int(1.4 * SR); t = np.arange(n) / SR
    return .32 * (np.sin(2 * np.pi * 1318 * t) + .4 * np.sin(2 * np.pi * 2636 * t) + .2 * np.sin(2 * np.pi * 3951 * t)) * env(n, .002, .45)
def sparkle():
    out = np.zeros(int(1.4 * SR))
    for k, f in enumerate([1568, 1976, 2349, 3136, 3951, 4699]):
        n = int(SR); t = np.arange(n) / SR; i = int(k * .05 * SR)
        out[i:i + n] += .18 * np.sin(2 * np.pi * f * t) * np.minimum(1, t / .002) * np.exp(-t * 4)
    return out
def boom(big=True):
    n = int(2.5 * SR); t = np.arange(n) / SR
    y = np.sin(2 * np.pi * (38 + 40 * np.exp(-t * 6)) * t) * np.exp(-t * (1.4 if big else 3)) + .25 * bandnoise(n, 80, 1500) * np.exp(-t * 6)
    return .9 * y
def scratch():
    n = int(.45 * SR); t = np.arange(n) / SR
    rate = np.where(t < .2, 1 - t / .2 * 1.8, -.8 + (t - .2) * 4)
    base = sosfilt(butter(2, 2500 / (SR / 2), output="sos"), rng.standard_normal(n * 2))
    y = base[np.clip(np.cumsum(np.abs(rate)), 0, len(base) - 1).astype(int)] * np.abs(rate)
    y = sosfilt(butter(2, [300 / (SR / 2), 3000 / (SR / 2)], btype="band", output="sos"), y)
    return .6 * y / (np.abs(y).max() + 1e-9) * np.minimum(1, t / .01) * np.clip((.45 - t) / .1, 0, 1)
def buzz():
    n = int(.14 * SR); t = np.arange(n) / SR
    b = np.convolve(.3 * np.sign(np.sin(2 * np.pi * 880 * t)) * env(n, .002, .2), np.ones(6) / 6, mode="same")
    return np.concatenate([b, np.zeros(int(.07 * SR)), b])
def riser():
    n = int(1.5 * SR); t = np.arange(n) / SR; f = 200 * 2 ** (t / t[-1] * 3)
    y = .25 * np.sin(2 * np.pi * np.cumsum(f) / SR) + .2 * bandnoise(n, 2000, 9000)
    return y * (t / t[-1]) ** 2
def glitch():
    n = int(.3 * SR); y = np.zeros(n)
    for k in range(6):
        i = int(rng.uniform(0, .25) * SR); m = int(.02 * SR); y[i:i + m] += rng.choice([-1, 1]) * np.sign(np.sin(np.arange(m) * rng.uniform(.05, .4)))
    return .25 * y

LIB = dict(pop=(pop, .45), tick=(tick, .5), whoosh=(whoosh, .55), swoosh_down=(swoosh_down, .5), stamp=(stamp, .55), clap=(clap, .7),
           ding=(ding, .45), sparkle=(sparkle, .6), boom=(lambda: boom(True), .8), boom_small=(lambda: boom(False), .6),
           scratch=(scratch, .9), buzz=(buzz, .45), riser=(riser, .5), glitch=(glitch, .5))
_cache = {}
def sound(name):
    if name not in _cache: f, g = LIB[name]; _cache[name] = g * f()
    return _cache[name]

def render(events, total):
    out = np.zeros(int((total + 3) * SR))
    for t, k in events:
        if k not in LIB: continue
        y = sound(k); i = int(max(0, t) * SR); seg = out[i:i + len(y)]; seg += y[:len(seg)]
    return out[:int(total * SR)]

if __name__ == "__main__":
    if sys.argv[1] == "--demo":
        ev = [(i * 1.6 + .2, k) for i, k in enumerate(LIB)]; sf.write(sys.argv[2], render(ev, len(LIB) * 1.6 + 1).astype(np.float32), SR)
    else:
        j = json.load(open(sys.argv[1])); tot = float(sys.argv[3]) if len(sys.argv) > 3 else j.get("total", max(t for t, _ in j["sfx"]) + 3)
        sf.write(sys.argv[2], render(j["sfx"], tot).astype(np.float32), SR)
