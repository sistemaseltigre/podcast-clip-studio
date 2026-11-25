#!/usr/bin/env python3
"""Quality checks for a finished clip.

  python3 qa.py clip.mp4                 # contact sheet (clip_sheet.jpg) + audio report
  python3 qa.py clip.mp4 --times 1,5,12  # sheet at chosen times

Audio report: duration, integrated loudness (LUFS), true peak, and a "doubled voice" check:
cross-correlation of the clip's own energy envelope looking for a delayed copy (120 ms - 3 s).
A real duplicate shows a strong secondary peak. It is only a hint: steady music beats also create peaks, so for a
reliable answer run it on voice-only audio (e.g. the source, or a render with "music" removed).
If a user says the voice sounds doubled and this check is clean, the cause is usually room reverb
pumped by heavy compression/denoise, or the file playing in two players at once.
"""
import json, re, subprocess, sys, os, tempfile
import numpy as np, cv2, soundfile as sf

def duration(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p], capture_output=True, text=True).stdout)

def sheet(p, times, out):
    ims = []
    for t in times:
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", p, "-frames:v", "1", "-vf", "scale=240:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
                           capture_output=True).stdout
        im = cv2.imdecode(np.frombuffer(r, np.uint8), cv2.IMREAD_COLOR)
        if im is None: continue
        cv2.putText(im, f"{t:.1f}s", (5, 22), 0, .6, (0, 255, 255), 2); ims.append(im)
    h = max(i.shape[0] for i in ims); ims = [cv2.copyMakeBorder(i, 0, h - i.shape[0], 0, 0, cv2.BORDER_CONSTANT) for i in ims]
    while len(ims) % 6: ims.append(np.zeros_like(ims[0]))
    cv2.imwrite(out, np.vstack([np.hstack(ims[k:k + 6]) for k in range(0, len(ims), 6)])); return out

def audio_report(p):
    m = subprocess.run(["ffmpeg", "-hide_banner", "-i", p, "-af", "loudnorm=print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
    j = json.loads(re.findall(r"\{[^{}]*\}", m)[-1])
    tmp = os.path.join(tempfile.mkdtemp(), "a.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", p, "-ac", "1", "-ar", "8000", tmp], check=True)
    x, sr = sf.read(tmp); hop = 40
    e = np.array([np.abs(x[i:i + hop]).mean() for i in range(0, len(x) - hop, hop)]); e = np.diff(e); e = e - e.mean()
    ac = np.correlate(e, e, "full")[len(e) - 1:]; ac /= ac[0] + 1e-12
    lo, hi = int(.12 * sr / hop), min(len(ac) - 1, int(3 * sr / hop))
    k = lo + int(np.argmax(ac[lo:hi])); peak = float(ac[k])
    return dict(lufs=float(j["input_i"]), true_peak=float(j["input_tp"]), echo_lag_s=round(k * hop / sr, 3), echo_strength=round(peak, 3),
                repeat_hint=peak > .5)

if __name__ == "__main__":
    p = sys.argv[1]; d = duration(p)
    times = [float(t) for t in sys.argv[sys.argv.index("--times") + 1].split(",")] if "--times" in sys.argv else list(np.linspace(.5, d - .3, 12))
    print("sheet:", sheet(p, times, os.path.splitext(p)[0] + "_sheet.jpg"))
    print(json.dumps(dict(duration=round(d, 2), **audio_report(p)), indent=1))
