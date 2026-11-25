# Music for clips

Two engines, both 100 % original (no samples or melodies from existing songs, so no copyright claims):

| Engine | Needs | Use for |
|---|---|---|
| `scripts/synth_music.py` | numpy/scipy only | Fast beds: lofi, upbeat, rumba (Spanish guitar + palmas), cinematic (magic waltz), suspense, corporate. Style switch with record-scratch (`--then/--switch`). |
| `scripts/bgm_motor.py` | fluidsynth + FluidR3_GM, pretty_midi (`setup.sh --music`) | Real orchestral/band cues written note by note (MIDI), mastered to wav/mp3/ogg, seamless loops. |

Say honestly what it is: a simple orchestral/production-music sound, not a studio recording.

### bgm_motor gotchas already solved
One-pass `loudnorm` makes the volume pump → the engine uses two-pass `linear=true`. FluidSynth renders seconds of silence after the last note → it cuts with `-t`. ffmpeg `asplit/atrim/amix` tail-wrap produced empty files → loop wrap is done in numpy.

## Writing a piece (one script per cue)
```python
from bgm_motor import Song, chord
s = Song(bpm=92, beats_per_bar=4, seed=3)
for k, prog in [("flauta","flute"),("arpa","harp"),("cuerdas","slow_strings"),("chelo","cello"),("drums",0)]:
    s.inst(k, prog, drum=(k == "drums"))
PROG = ["Am","G","D","Am","Am","G","Em","Am"]*2
MEL = [[("E5",1.5),("D5",.5),("C5",1),("A4",1)], ...]      # one list of (note, beats) per bar, summing to the bar length
beat = 0
for bar, c in enumerate(PROG):
    n = chord(c, 3)
    s.arpeggio("arpa", n, beat, 4, step=.5, vel=50); s.note("chelo", n[0]-12, beat, 3.9, 58)
    if bar >= 4: s.chord_hit("cuerdas", [x+12 for x in n], beat, 4, 44)
    if bar >= 8: s.line("flauta", MEL[bar % 8], beat, 76)
    s.drum("conga_lo", beat, 40)
    beat += s.bpb
s.render("bgm_bosque", total_beats=beat, loop=True)       # loop=False for video cues (fade-out ending)
```
Composition rules that worked:
- **Form**: video cue = intro (2–4 bars, sparse) → A (8–16) → B (8, contrast: new chords/instrument) → A' (full: melody doubled an octave lower by strings, percussion, sparkles) → outro (2–4) with a fade; 1:20–2:30. Game loop = 16–32 bars, no intro/outro, the last bar must lead back to the first chord (end on V or on the tonic with a pickup); `loop=True`.
- **Energy arc**: introduce layers progressively (arp → bass → pad → melody → doubling/percussion). Keep accompaniment velocities ~45–60, melody ~70–90, so the climax is actually louder after mastering. Check with librosa RMS per 5 s window: values should rise toward A'.
- **Melody**: write it by hand per bar, stepwise motion with occasional leaps of a 4th/6th, chord tones on strong beats, a clear 2-bar motif repeated and varied; second phrase higher; cadence on the tonic. Humanize (±12 ms, ±6 velocity), legato 0.9–0.95.
- **Mood cookbook** (key / tempo / meter / instruments / harmony):
  - Warm village / town: D or G major, 96–108, 3/4 waltz, flute + harp/nylon arp + cello + light frame drum + celesta sparkle; I–IV–I–V–vi–IV–V–I.
  - Forest / nature: A Dorian or E minor, 84–96, 4/4 or 6/8, kalimba/harp + flute/ocarina + slow strings + congas/shaker; i–VII–IV–i.
  - Mystery / night: D minor or C# minor, 60–76, celesta/music box + pizzicato + low strings pad + choir oohs, sparse; i–♭VI–iv–V, add dim chords.
  - Tension: minor, 90–110, ostinato on low strings/tremolo strings, timpani pulses, rising chromatic line, no resolution.
  - Battle: E or D minor, 150–180, 4/4, overdrive/distortion guitar power chords (`chord('E5')`), picked bass on 8ths, kick/snare/crash, brass stabs + strings melody; i–♭VI–♭VII–i.
  - Hero / main character: major, 120–140, brass/french horn melody, strings, snare march, big I–V–vi–IV.
  - Comedy: C or F major, 110–130, pizzicato + bassoon/clarinet + marimba, staccato (legato 0.5), swing 0.2.
  - Sadness: A or D minor, 60–72, piano + cello + slow strings, i–VI–III–VII; sparse melody.
  - Hope / victory: modulate up a step for the last A', choir pad, timpani roll, crash.
  - Cathedral / sacred: church organ + choir, 60–70, modal (Dorian/Mixolydian), long chords.
  - Desert: Phrygian dominant (E F G# A B C D), sitar/shamisen + flute, darbuka-like congas. Ice / snow: celesta, glock, harp, pad_halo, high register, slow. Sea / coast: harp waves (fast arps), strings swells, 6/8. Cave / dungeon: low drones, timpani, reverb room 0.9, sparse metallic hits. Boss: battle + choir + orch_hit, half-time breakdown.

## 4. Mastering & delivery
- Loudness: **−20 LUFS** for background under dialogue (podcast/video clips); **−16 to −18 LUFS** for game map loops (no dialogue). Peaks ≤ −1.5 dBTP.
- Outputs per cue: `.wav` (48 kHz master), `.mp3` (192k, preview), `.ogg` (Vorbis q5, for the web game) + the `.mid` and the generating `.py` (so any cue can be lengthened, re-orchestrated or re-keyed later).
- Naming: `bgm_<mood>_<bpm>.wav` next to the clip specs; keep the generating `.py` and `.mid`.
- Verify every render: duration, RMS curve (librosa, 5 s windows), no clipping (`volumedetect`), and for loops the seam: `abs(y[0]-y[-1])` must be about the typical sample-to-sample difference and the RMS across `concat(y, y)` must not dip at the joint.
- Mixing under a podcast: BGM 12–15 dB under the voice, ducked (clipkit/mix.py does it: `music.level_db`, `duck: true`).

## 5. Workflow
1. Read the clip plan and list cues with mood, length, loop or not (a loop is handy when clips have different lengths).
2. Pick key/tempo/meter/instrumentation from the cookbook; write progression and melody by hand.
3. Render, check the numbers, adjust velocities/layers, re-render.
4. Deliver mp3 previews to the user; save wav/mid/py next to the project; keep a short table (cue, mood, key, BPM, length, file).