"""bgm_motor: compose BGM note by note in Python -> MIDI -> FluidSynth (General MIDI orchestra) -> mastered wav/mp3/ogg.
Needs: fluidsynth + FluidR3_GM soundfont (bash setup.sh --music) and pretty_midi.
Usage and composition rules: references/music.md.  Example: examples/bgm_example.py
"""
import json, os, random, re, subprocess
import pretty_midi as pm
SF2 = next((p for p in ("/usr/share/sounds/sf2/FluidR3_GM.sf2", "/usr/share/soundfonts/FluidR3_GM.sf2", "/opt/homebrew/share/soundfonts/default.sf2", os.path.expanduser("~/.cache/podcast-clip-studio/FluidR3_GM.sf2")) if os.path.exists(p)), "/usr/share/sounds/sf2/FluidR3_GM.sf2"); N = pm.note_name_to_number
GM = dict(piano=0, celesta=8, glock=9, music_box=10, marimba=12, organ=19, accordion=21, nylon=24, steel=25,
          clean_guitar=27, overdrive=29, distortion=30, ac_bass=32, fingered_bass=33, picked_bass=34, violin=40,
          viola=41, cello=42, contrabass=43, tremolo_str=44, pizzicato=45, harp=46, timpani=47, strings=48,
          slow_strings=49, choir=52, voice_oohs=53, orch_hit=55, trumpet=56, trombone=57, tuba=58, french_horn=60,
          brass=61, oboe=68, english_horn=69, bassoon=70, clarinet=71, piccolo=72, flute=73, recorder=74,
          pan_flute=75, shakuhachi=77, whistle=78, ocarina=79, square_lead=80, saw_lead=81, pad_warm=89,
          pad_choir=91, pad_halo=94, sitar=104, banjo=105, shamisen=106, koto=107, kalimba=108, bagpipe=109,
          fiddle=110, taiko=116, melodic_tom=117)
DR = dict(kick=36, snare=38, rim=37, clap=39, hat=42, hat_open=46, ride=51, crash=49, tom_lo=45, tom_mid=47,
          tom_hi=50, tamb=54, shaker=70, conga_lo=64, conga_hi=63, bongo=60, cowbell=56, triangle=81)
QUAL = {"maj":[0,4,7], "min":[0,3,7], "dim":[0,3,6], "sus4":[0,5,7], "7":[0,4,7,10], "maj7":[0,4,7,11],
        "m7":[0,3,7,10], "add9":[0,4,7,14], "5":[0,7]}
def chord(name, octave=3):                     # 'D' 'Bm' 'F#m7' 'Gmaj7' 'Asus4' 'E5'
    m = re.match(r"([A-G][#b]?)(.*)", name); q = {"": "maj", "m": "min"}.get(m.group(2), m.group(2))
    r = N(f"{m.group(1)}{octave}"); return [r + i for i in QUAL[q]]
class Song:
    def __init__(self, bpm, beats_per_bar=4, seed=7, swing=0.0):
        random.seed(seed); self.bpm, self.bpb, self.B, self.swing = bpm, beats_per_bar, 60/bpm, swing
        self.mid = pm.PrettyMIDI(initial_tempo=bpm); self.tr = {}
    def inst(self, key, program, drum=False):
        i = pm.Instrument(program=0 if drum else GM.get(program, program), name=key, is_drum=drum)
        self.mid.instruments.append(i); self.tr[key] = i; return i
    def note(self, key, pitch, beat, dur_beats, vel, human=0.012):   # beat = absolute position in beats
        t = beat*self.B
        if self.swing and abs((beat*2) % 2 - 1) < 1e-6: t += self.swing*self.B/2
        j = random.uniform(-human, human); p = N(pitch) if isinstance(pitch, str) else pitch
        self.tr[key].notes.append(pm.Note(velocity=max(1, min(127, int(vel + random.randint(-6, 6)))), pitch=p,
                                          start=max(0, t+j), end=max(t+j+0.03, t+j+dur_beats*self.B)))
    def line(self, key, notes, start_beat, vel, octave=0, legato=0.95):   # [('A4',1),('R',.5),...]
        b = start_beat
        for p, d in notes:
            if p != "R": self.note(key, N(p)+12*octave, b, d*legato, vel)
            b += d
        return b
    def chord_hit(self, key, notes, beat, dur, vel):
        for p in notes: self.note(key, p, beat, dur, vel)
    def arpeggio(self, key, notes, beat, beats, step=0.5, vel=60, pattern=(0,2,1,2), octave=1):
        i, b = 0, beat
        while b < beat + beats - 1e-6:
            self.note(key, notes[pattern[i % len(pattern)] % len(notes)] + 12*octave, b, step*0.9, vel if i else vel+6)
            b += step; i += 1
    def drum(self, name, beat, vel, dur=0.1): self.note("drums", DR[name], beat, dur, vel, human=0.006)
    def render(self, out, total_beats, lufs=-20, gain=0.7, reverb=0.55, room=0.75, tail=4.0, fade=3.5, loop=False):
        self.mid.write(out + ".mid")
        subprocess.run(["fluidsynth", "-ni", "-g", str(gain), "-r", "48000", "-o", "synth.reverb.active=1",
                        "-o", f"synth.reverb.room-size={room}", "-o", "synth.reverb.width=0.9",
                        "-o", f"synth.reverb.level={reverb}", "-o", "synth.chorus.active=1",
                        "-F", out + "_raw.wav", SF2, out + ".mid"], check=True, capture_output=True)
        L = total_beats*self.B; src = out + "_raw.wav"
        pre = "highpass=f=35,equalizer=f=3500:t=q:w=1:g=1.5,acompressor=threshold=-18dB:ratio=2:attack=20:release=250"
        if loop:   # wrap the reverb tail onto the start and cut at exactly L -> seamless loop
            import numpy as np, soundfile as sf
            a, sr = sf.read(src, always_2d=True); n = int(round(L*sr)); k = int(round(tail*sr))
            body = a[:n].copy(); tl = a[n:n+k]; body[:len(tl)] += tl
            sf.write(out + "_loopraw.wav", body, sr); src = out + "_loopraw.wav"; dur = L; pre_f = pre
        else:
            dur = L + tail; pre_f = pre + f",afade=out:st={L+tail-fade:.2f}:d={fade}"
        m = subprocess.run(["ffmpeg", "-hide_banner", "-i", src, "-t", f"{dur:.4f}", "-af",
                            pre_f + f",loudnorm=I={lufs}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                           capture_output=True, text=True).stderr
        j = json.loads(re.findall(r"\{[^{}]*\}", m)[-1])
        ln = (f"loudnorm=I={lufs}:TP=-1.5:LRA=11:linear=true:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
              f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-t", f"{dur:.4f}", "-af", pre_f + "," + ln,
                        "-ar", "48000", out + ".wav"], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out+".wav", "-c:a", "libmp3lame", "-b:a", "192k", out+".mp3"], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out+".wav", "-c:a", "libvorbis", "-q:a", "5", out+".ogg"], check=True)
        for f in (out + "_raw.wav", out + "_loopraw.wav"):
            if os.path.exists(f): os.remove(f)
        return dur
