#!/usr/bin/env python3
"""Transcribe a podcast/video with word timestamps.

  python3 transcribe.py INPUT.mp4 OUT.json [--lang es] [--model small|medium|large-v3] [--engine auto|faster|sherpa]

Output JSON: {"engine":..., "lang":..., "duration":..., "words":[{"s":..,"e":..,"w":..}], "segments":[{"s","e","text"}]}
Engine 1: faster-whisper (real word timestamps; downloads the model from Hugging Face).
Engine 2 (fallback when Hugging Face is blocked): sherpa-onnx Whisper, model from the k2-fsa GitHub release,
          with silero-VAD phrase splitting; word times are interpolated inside each short phrase.
"""
import argparse, json, os, subprocess, sys, tarfile, tempfile, urllib.request
import numpy as np, soundfile as sf

CACHE = os.environ.get("CLIP_CACHE", os.path.expanduser("~/.cache/podcast-clip-studio"))
GH = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"

def to_wav16(src):
    out = os.path.join(tempfile.mkdtemp(), "a16.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000", out], check=True)
    return out

def run_faster(wav, lang, model):
    from faster_whisper import WhisperModel
    m = WhisperModel(model, device="auto", compute_type="int8")
    segs, info = m.transcribe(wav, language=lang, word_timestamps=True, vad_filter=True, beam_size=5,
                              condition_on_previous_text=False)
    words, segments = [], []
    for s in segs:
        segments.append({"s": round(s.start, 3), "e": round(s.end, 3), "text": s.text.strip()})
        for w in s.words or []:
            if w.word.strip(): words.append({"s": round(w.start, 3), "e": round(w.end, 3), "w": w.word.strip()})
    return words, segments

def fetch(url, dst):
    if os.path.exists(dst) and os.path.getsize(dst) > 0: return dst
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    print("downloading", url, file=sys.stderr)
    urllib.request.urlretrieve(url, dst + ".part"); os.replace(dst + ".part", dst); return dst

def sherpa_model(size):
    d = os.path.join(CACHE, f"sherpa-onnx-whisper-{size}")
    enc = os.path.join(d, f"{size}-encoder.int8.onnx")
    if not os.path.exists(enc):
        tb = fetch(GH + f"sherpa-onnx-whisper-{size}.tar.bz2", os.path.join(CACHE, f"whisper-{size}.tar.bz2"))
        with tarfile.open(tb) as t:
            members = [m for m in t.getmembers() if m.name.endswith((f"{size}-encoder.int8.onnx", f"{size}-decoder.int8.onnx", f"{size}-tokens.txt"))]
            for m in members:
                if os.path.isabs(m.name) or ".." in m.name: continue
                t.extract(m, CACHE)
        os.remove(tb)
    vad = fetch(GH + "silero_vad.onnx", os.path.join(CACHE, "silero_vad.onnx"))
    return d, vad

def run_sherpa(wav, lang, size):
    import sherpa_onnx
    d, vad_path = sherpa_model(size)
    rec = sherpa_onnx.OfflineRecognizer.from_whisper(encoder=f"{d}/{size}-encoder.int8.onnx", decoder=f"{d}/{size}-decoder.int8.onnx",
                                                     tokens=f"{d}/{size}-tokens.txt", language=lang, task="transcribe", num_threads=os.cpu_count() or 2)
    a, sr = sf.read(wav, dtype="float32")
    cfg = sherpa_onnx.VadModelConfig(); cfg.sample_rate = 16000
    v = cfg.silero_vad; v.model = vad_path; v.min_silence_duration = 0.12; v.min_speech_duration = 0.12; v.threshold = 0.5; v.max_speech_duration = 6
    vad = sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=int(len(a) / 16000) + 60)
    pad = np.zeros(1600, np.float32); words, segments = [], []
    def flush():
        while not vad.empty():
            s = vad.front; st = s.start / 16000; smp = np.array(s.samples, np.float32); en = st + len(smp) / 16000
            stv = rec.create_stream(); stv.accept_waveform(16000, np.concatenate([pad, smp, pad])); rec.decode_stream(stv)
            txt = stv.result.text.strip(); vad.pop()
            if not txt or txt.startswith("["): continue
            segments.append({"s": round(st, 3), "e": round(en, 3), "text": txt})
            toks = txt.split(); tot = sum(len(t) + 1 for t in toks); acc = 0
            for t in toks:  # interpolate inside the (short) phrase by character count
                ws = st + (en - st) * acc / tot; acc += len(t) + 1
                words.append({"s": round(ws, 3), "e": round(st + (en - st) * acc / tot, 3), "w": t})
            print(f"{st:7.2f}-{en:7.2f} {txt}", file=sys.stderr, flush=True)
    for i in range(0, len(a), 512):
        vad.accept_waveform(a[i:i + 512]); flush()
    vad.flush(); flush()
    return words, segments

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input"); ap.add_argument("out")
    ap.add_argument("--lang", default="es"); ap.add_argument("--model", default="medium")
    ap.add_argument("--engine", default="auto", choices=["auto", "faster", "sherpa"])
    a = ap.parse_args()
    wav = to_wav16(a.input); dur = sf.info(wav).duration; engine = None
    if a.engine in ("auto", "faster"):
        try:
            words, segs = run_faster(wav, a.lang, a.model); engine = "faster-whisper"
        except Exception as e:
            if a.engine == "faster": raise
            print("faster-whisper unavailable (%s) -> sherpa-onnx fallback" % str(e)[:120], file=sys.stderr)
    if engine is None:
        words, segs = run_sherpa(wav, a.lang, a.model if a.model in ("tiny", "base", "small", "medium") else "medium"); engine = "sherpa-onnx"
    json.dump({"engine": engine, "lang": a.lang, "duration": dur, "words": words, "segments": segs}, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(f"{engine}: {len(words)} words, {len(segs)} segments, {dur:.1f}s -> {a.out}")

if __name__ == "__main__":
    main()
