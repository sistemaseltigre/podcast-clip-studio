# Lessons learned (real problems already hit, and their fixes)

## Source footage
- **Silent audio track.** A video can carry an audio stream that is pure silence (max_volume −91 dB). Check with `volumedetect` before transcribing, and ask for the version with sound.
- **Mirrored front camera.** Text on shirts or posters reads backwards. Set `"flip": true` so the image reads correctly.
- **4K HEVC phone footage is slow to decode.** clipkit pre-scales big sources to 2× the output resolution. For several long 4K files, make 1440p or 1080p H.264 proxies of only the ranges you need: `ffmpeg -ss IN -i src -t DUR -vf scale=1440:-2 -c:v libx264 -crf 17 -c:a pcm_s16le part.mov`.
- **Two recordings of one conversation** (each person filmed separately, with retakes). Transcribe both, pick the best take of every line, then order the lines by the script. Use `split` and reaction shots so both people seem to share the space. Unify the two rooms with the same colour grade and vignette.
- **Landscape source for vertical output.** A 640×720 centre crop scaled up from 720p looks soft. Prefer `fit`, or a 4:5 box with title bands above and below. Tell the user the image is softer than the original.

## Transcription
- **Hugging Face blocked by the network.** Use the sherpa-onnx Whisper models from the k2-fsa GitHub releases (transcribe.py does this automatically). Fonts come from raw.githubusercontent.com/google/fonts.
- **Whisper on very short windows hallucinates.** It returns words from a neighbouring phrase, or "[Música]". Don't use 1–3 s probes to verify cuts. To find an exact cut inside a phrase, test 3–4 candidate start points on ≥ 1.5 s windows and pick the first one that starts with the wanted word.
- **ASR errors are normal** (proper names, slang, English inside Spanish). Fix caption text by hand where it matters. Keep the speaker's actual words; don't "improve" them.

## Audio
- **"My voice sounds doubled / out of sync."** This was not a duplicated track. Heavy noise reduction (afftdn) plus strong compression and makeup gain lifted the room reverb into an audible echo. Fix it with a gentle chain: highpass 80 Hz, a soft gate, ratio-2 compression, two-pass loudnorm, no or very light denoise. Run qa.py to rule out a real duplicate. Also ask whether the file is playing in two players at once (chat preview plus a desktop player).
- **Single-pass loudnorm** undershoots the target and pumps. Always use the two-pass `linear=true` approach (mix.py does this).
- **ffmpeg `loudnorm` outputs 192 kHz.** Always `aresample=48000` afterwards.
- **Keep audio and video lengths exact per range.** Use `atempo` then `apad=whole_dur` and `atrim`, or rounding drift adds up over 30+ cuts.
- **Music under speech.** Use sidechain ducking (threshold 0.02, ratio 8–10) with the music at −14 to −20 dB. Re-check intelligibility by transcribing a long window of the final mix and comparing it with the voice-only transcript.
- **A strong timpani hit can dominate the peak normalization** of generated music. Mix it lower, or normalise by loudness rather than peak.

## Graphics
- **Card placement.** Verify placement on a contact sheet: in the first draft, cards sat right over the eyes. Faces live at y 0.35–0.5 of a vertical frame.
- **Fonts without the glyph.** Fonts often lack ✦ ✓ ★ and emoji; PIL draws empty boxes. Draw stars, checks and arrows as polygons (gfx.star4, gfx.check).
- **Anchor of slide-in tags.** Slide-in tags anchored at the centre ended up half off-screen. Use left anchoring for lower-thirds.
- **Overlaps.** Don't let a checklist, a card and a caption overlap. Give each its own vertical band, and time cards so they end before the next element appears.
- **Strong formats that worked:**
  - "behind the scenes" (REC dot, CAM A/B labels, viewfinder corners);
  - a countdown timer gag ("1 minute" that runs over);
  - a producer checklist that gets ticked;
  - a movie-style intro (stars, fog, gold serif title) that switches with a record scratch and a glitch to a bright branded part.

## Rendering and files
- **Remote or linked-computer shells may kill background jobs** when the call ends, and may limit each call to about 3 minutes. Split long encodes into chunks of ≤ 120 s of source per call, or render in a container that keeps background processes (`setsid nohup … &`).
- **Big file transfers through tools have size caps** (e.g. 20 MB per file, 100 MB per call). Split with `split -b 16000000`, transfer the parts, rejoin with `cat`, and verify with `md5sum`. One bridge corrupted a chunk that began with an MP4 header; prefixing that chunk with 16 dummy bytes (removed with `tail -c +17` on arrival) fixed it. Always compare checksums.
- **Prefer delivering several smaller files** (one mp4 per clip at CRF 18–20) over one huge master.
