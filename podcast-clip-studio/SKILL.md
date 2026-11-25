---
name: podcast-clip-studio
description: Turn long podcasts or talking-head videos into polished short clips for TikTok, Reels, Shorts and X. Covers transcription with word timestamps, picking viral moments, silence cutting, vertical reframing, multi-camera and split-screen layouts, animated captions, hook titles and cards, original background music, sound effects, voice ducking and loudness. Use it to cut, clip, edit or reformat video, or to make background music or sound effects for one.
---

# Podcast Clip Studio

Long podcast or video in, ready-to-post short clips out. Everything is original and generated in code: the captions, the graphics, the music (two engines) and the sound effects. That keeps the clips free of copyright claims.

Always answer in the user's language. Captions use the language spoken in the video.

## 0. Setup (once per machine or container)
```bash
bash scripts/setup.sh --asr --music     # pip deps, OFL fonts (~/.cache/podcast-clip-studio/fonts), whisper, fluidsynth
```
Needs `ffmpeg` and Python 3.9+. Without FluidSynth, `synth_music.py` still makes music. Without Hugging Face access, `transcribe.py` switches to its fallback engine automatically (see section 2).

## 1. Ask only what changes the edit
Before cutting, get these answers. If the request already covers them, don't ask.
- **Platform and format.** Default is vertical 1080×1920 at 30 fps. Use 1080×1080 for feed posts and 1920×1080 for YouTube.
- **How many clips, and how long.** Default is 3 clips of 30–60 s.
- **Brand.** Colours, fonts, logo or cover image, @handle for the watermark, and a CTA or link for the end card.
- **Music mood.** Choose from lofi, upbeat, rumba, cinematic, suspense or corporate, or none. Also ask whether they want SFX.

Look at the source before deciding anything. Run `ffprobe` and grab a few frames (`python3 scripts/qa.py source.mp4`) to check:
- orientation and the rotation tag;
- whether a phone front camera mirrored the image (text in the background reads backwards → set `"flip": true`);
- where the faces sit (this sets `focus`);
- that the audio is not silent (`ffmpeg -i src -af volumedetect -f null -`). A silent track is common: ask for the file that has the sound.

## 2. Transcribe
```bash
python3 scripts/transcribe.py episode.mp4 transcript.json --lang es --model medium
```
- It tries faster-whisper first, which gives real word timestamps.
- If Hugging Face is blocked, it falls back to sherpa-onnx Whisper downloaded from GitHub, with VAD phrase splitting and interpolated word times.
- Use `--model small` for speed and `medium` for accuracy.

Whisper on very short windows (under 4 s) hallucinates. Never judge a cut point or check sync from a tiny ASR probe. Use cross-correlation (qa.py) or longer windows instead.

## 3. Find the moments
```bash
python3 scripts/find_moments.py transcript.json                  # readable, timestamped transcript
python3 scripts/find_moments.py transcript.json --candidates 45  # ranked ~45 s windows (hint only)
python3 scripts/find_moments.py transcript.json --search "dinero,error"
```
Read the transcript yourself. A good clip has:
1. a **hook** in the first 2 s (a question, a strong claim, a number, a conflict);
2. one idea with a **payoff**;
3. a **clean ending** on a finished sentence.

When the speaker repeated a line (retakes), use the later, fluent take. Show the user the plan as a short table (clip, in–out, hook line, why it works) and let them change it before you render.

## 4. Write a spec per clip and render
Copy `examples/clip_spec.json` and edit it. `references/spec.md` documents every field.
```bash
python3 scripts/clipkit.py clip01.json --plan            # output timeline after silence cutting
python3 scripts/clipkit.py clip01.json --stills 0.5,3,10,25   # contact sheet: CHECK IT before the full render
python3 scripts/clipkit.py clip01.json                   # render video + mix audio -> output mp4
```
What clipkit does:
- **Silence cutting.** It reads the word timestamps and removes gaps longer than `tighten.max_gap` (default 0.45 s), keeping a 0.14 s breath. Each jump cut alternates the zoom (×1.08) so it reads as a second camera angle.
- **Layouts per segment:**
  - `fill` crops to the target aspect around `focus` (default; `zoom` punches in);
  - `fit` keeps a landscape frame whole over a blurred copy of itself;
  - `split` stacks two cameras or times vertically. Use it for two hosts, or for a reaction shot (`top_time` / `bottom_time`).
- **Captions.** 2–4 words at a time with a pop-in, placed at `captions.y` (default 0.74 of the height, inside the safe zone). ALLCAPS words, numbers and the `highlight` list are coloured with the accent. Style `stroke` (white text, black outline) or `box`.
- **Overlays.** A `hook` title in the first seconds. `cards` are pinned to source times (`"at"`) in five styles: chip, accent, stamp, bar, name (lower-third) and image. There is also an optional `watermark`, a `progress_bar` and an `end_card` (image, title, lines, CTA, handle).
- **Audio** (mix.py, which runs automatically):
  1. the voice is cut on the same timeline;
  2. a gentle voice chain is applied;
  3. music is ducked under the voice (sidechain);
  4. synthesized SFX are added on the cards and cuts;
  5. two-pass loudness takes it to −14 LUFS with true peak ≤ −1.5 dB.

## 5. Music and SFX
Quick and dependency-free:
```bash
python3 scripts/synth_music.py --style lofi --dur 60 --out bgm.wav
python3 scripts/synth_music.py --style cinematic --then rumba --switch 12.9 --total 48 --impacts 1.25 --out bgm.wav
python3 scripts/sfx.py --demo sfx_demo.wav     # audition: pop tick whoosh stamp clap ding sparkle boom scratch riser glitch...
```
For an orchestral or richer score, compose note by note with `scripts/bgm_motor.py` (FluidSynth GM orchestra). Read `references/music.md` (form, mood cookbook, mastering) and start from `examples/bgm_example.py`.

Set the music level in the spec: `music.level_db` from −14 to −20, with `duck: true`. Background music should sit 12–15 dB under the speech.

## 6. QA (always, before you deliver)
```bash
python3 scripts/qa.py out/clip01.mp4
```
Open the contact sheet and check:
- no card covers a face;
- the captions are readable and inside the safe zone;
- the zoom and crop are right;
- the end card works.

In the audio report, LUFS should be about −14. If `repeat_hint` is true on voice-only audio, look for a duplicated audio source. Then play back mentally against the transcript: the hook comes first and the ending is a full sentence.

## 7. Delivery
- One mp4 per clip (H.264, yuv420p, AAC, faststart).
- Plus a `.txt` with a post caption, the link and hashtags. X allows 280 characters, and a link counts as 23.
- Keep the specs so any clip can be re-rendered with changes.

## Hard rules
- **No copyrighted characters, logos, music or fonts.** If asked for a famous character or theme song, say so once and make an original "inspired-by" mood instead: a generic hooded wizard silhouette, magical gold serif titles, an original waltz. Brand assets the user owns, or has permission to use, are fine.
- **Never invent facts** (dates, prices, places) on the cards. Take them from the user or the source.
- Read `references/lessons.md` before a long or unusual job. It lists the traps already hit: transfers, echo, silent tracks, mirrored cameras, background-process limits and more.
