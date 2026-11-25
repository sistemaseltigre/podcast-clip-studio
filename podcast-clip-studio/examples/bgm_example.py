"""Example cue with bgm_motor (run from the scripts/ folder or add it to sys.path).
Warm, optimistic podcast bed: D major, 100 BPM, nylon guitar arps + bass + soft strings + light percussion, ~40 s, loopable."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from bgm_motor import Song, chord

s = Song(bpm=100, beats_per_bar=4, seed=3)
for k, prog in [("gtr", "nylon"), ("bass", "fingered_bass"), ("str", "slow_strings"), ("lead", "flute"), ("drums", 0)]:
    s.inst(k, prog, drum=(k == "drums"))
PROG = ["D", "A", "Bm", "G"] * 4
MEL = [[("F#5", 1.5), ("E5", .5), ("D5", 1), ("A4", 1)], [("C#5", 2), ("E5", 1), ("A4", 1)],
       [("D5", 1), ("F#5", 1), ("B5", 1.5), ("A5", .5)], [("G5", 2), ("F#5", 1), ("E5", 1)]]
beat = 0
for bar, c in enumerate(PROG):
    n = chord(c, 3)
    s.arpeggio("gtr", n, beat, 4, step=.5, vel=52)
    s.note("bass", n[0] - 12, beat, 1.8, 62); s.note("bass", n[0] - 12, beat + 2.5, 1.2, 55)
    if bar >= 4: s.chord_hit("str", [x + 12 for x in n], beat, 4, 40)
    if bar >= 8: s.line("lead", MEL[bar % 4], beat, 72)
    for k in range(4):
        s.drum("shaker", beat + k + .5, 34)
        if k in (1, 3): s.drum("clap", beat + k, 40)
    s.drum("kick", beat, 50)
    beat += s.bpb
s.render("bgm_warm_100", total_beats=beat, lufs=-18, loop=True)
