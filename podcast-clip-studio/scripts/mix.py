#!/usr/bin/env python3
"""Audio for a clipkit render: cut the voice to the output timeline, gentle voice chain, music ducked
under the voice, synthesized SFX, two-pass loudness to the target, then mux with the rendered video.

  python3 mix.py spec.json        (clipkit.py calls this automatically)

Spec fields used: sources, audio_source, output, speed, music {file, level_db, duck, loop}, sfx (bool),
voice {highpass, compress, gate}, loudness (default -14 LUFS).
"""
import json, os, re, subprocess, sys, tempfile
import numpy as np, soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clipkit import load_spec
import sfx as SFX

def run(cmd): subprocess.run(cmd, check=True)

def two_pass_loudnorm(src, dst, I=-14, TP=-1.5, LRA=11, extra=""):
    pre = (extra + ",") if extra else ""
    m = subprocess.run(["ffmpeg", "-hide_banner", "-i", src, "-af", pre + f"loudnorm=I={I}:TP={TP}:LRA={LRA}:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    j = json.loads(re.findall(r"\{[^{}]*\}", m)[-1])
    ln = (f"loudnorm=I={I}:TP={TP}:LRA={LRA}:linear=true:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
          f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}")
    run(["ffmpeg", "-v", "error", "-y", "-i", src, "-af", pre + ln + ",aresample=48000", "-ar", "48000", dst])

def main():
    S = load_spec(sys.argv[1]); tl_j = json.load(open(S["output"] + ".timeline.json"))
    tl, total, speed = tl_j["timeline"], tl_j["total"], S["speed"]
    tmp = tempfile.mkdtemp(); src = S["sources"][S["audio_source"]]
    V = S.get("voice", {})
    # 1) voice cut to the timeline (each range: tiny fades, tempo, exact length)
    filt, labels = [], []
    lead = tl[0]["t0"] if tl else 0
    filt.append(f"anullsrc=r=48000:cl=mono,atrim=0:{max(0.001, lead):.4f}[lead]"); labels.append("[lead]")
    for i, r in enumerate(tl):
        d = r["src_out"] - r["src_in"]; od = d / speed
        tempo = f",atempo={speed}" if abs(speed - 1) > 1e-3 else ""
        filt.append(f"[0:a]atrim={r['src_in']:.4f}:{r['src_out']:.4f},asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=mono,"
                    f"afade=t=in:d=0.015,afade=t=out:st={max(0, d - 0.03):.4f}:d=0.03{tempo},apad=whole_dur={od:.5f},atrim=0:{od:.5f}[a{i}]")
        labels.append(f"[a{i}]")
    filt.append("".join(labels) + f"concat=n={len(labels)}:v=0:a=1,apad=whole_dur={total:.4f},atrim=0:{total:.4f}[v]")
    raw = os.path.join(tmp, "voice_raw.wav")
    run(["ffmpeg", "-v", "error", "-y", "-i", src, "-filter_complex", ";".join(filt), "-map", "[v]", "-ar", "48000", raw])
    # 2) gentle voice chain. Heavy denoise + strong compression pumps up room echo ("my voice sounds doubled").
    chain = [f"highpass=f={V.get('highpass', 80)}"]
    if V.get("gate", True): chain.append("agate=threshold=0.015:range=0.3:attack=5:release=150:ratio=2")
    if V.get("denoise"): chain.append("afftdn=nr=6:nf=-40")
    chain.append(f"acompressor=threshold=-18dB:ratio={V.get('compress', 2)}:attack=10:release=200:makeup=1.5")
    voice = os.path.join(tmp, "voice.wav"); two_pass_loudnorm(raw, voice, I=-16, TP=-2, extra=",".join(chain))
    inputs = ["-i", voice]; mixlabels = ["[vx]"]; fc = ["[0:a]asplit=2[vx][key]"]
    # 3) music
    M = S.get("music")
    if M and M.get("file"):
        inputs += ["-stream_loop", "-1" if M.get("loop", True) else "0", "-i", M["file"]]
        lvl = M.get("level_db", -16)
        mus = f"[1:a]aresample=48000,aformat=channel_layouts=mono,atrim=0:{total:.4f},volume={lvl}dB,afade=t=out:st={max(0, total - M.get('fade_out', 1.5)):.3f}:d={M.get('fade_out', 1.5)}"
        if M.get("fade_in", 0): mus += f",afade=t=in:d={M['fade_in']}"
        if M.get("duck", True):
            fc.append(mus + "[mu]"); fc.append("[mu][key]sidechaincompress=threshold=0.02:ratio=8:attack=15:release=350[md]"); mixlabels.append("[md]")
        else:
            fc.append(mus + "[md]"); fc.append("[key]anullsink"); mixlabels.append("[md]")
    else:
        fc.append("[key]anullsink")
    # 4) sfx
    sj = S["output"] + ".sfx.json"
    if S.get("sfx", True) and os.path.exists(sj):
        ev = json.load(open(sj))["sfx"]
        if ev:
            sp = os.path.join(tmp, "sfx.wav"); sf.write(sp, SFX.render(ev, total).astype(np.float32), 48000)
            idx = len([x for x in inputs if x == "-i"]); inputs += ["-i", sp]
            fc.append(f"[{idx}:a]volume={S.get('sfx_level', 0.7)}[sx]"); mixlabels.append("[sx]")
    fc.append("".join(mixlabels) + f"amix=inputs={len(mixlabels)}:normalize=0:duration=first[mix]")
    pre = os.path.join(tmp, "premaster.wav")
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", "[mix]", "-ar", "48000", pre])
    master = os.path.join(tmp, "master.wav"); two_pass_loudnorm(pre, master, I=S.get("loudness", -14), TP=-1.5)
    run(["ffmpeg", "-v", "error", "-y", "-i", S["output"] + ".video.mp4", "-i", master, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-shortest", "-movflags", "+faststart", S["output"]])
    for f in (S["output"] + ".video.mp4",):
        if os.path.exists(f) and not S.get("keep_temp"): os.remove(f)
    print("done ->", S["output"])

if __name__ == "__main__":
    main()
