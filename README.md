# 🎬 Podcast Clip Studio: a skill for Claude

Turns long podcasts and talking-head videos into short clips ready for **TikTok, Reels, Shorts and X**, with:

- ✂️ **Automatic cutting.** Transcription with word timestamps, viral-moment finder, silence cutting and jump cuts that look like camera changes.
- 📱 **Vertical reframing.** 9:16, 1:1 or 16:9, punch-in zooms, split screen for two hosts or two cameras, and landscape fitted over a blurred background.
- 💬 **Animated captions.** Highlighted keywords, plus a hook title, info cards, lower-thirds, watermark, progress bar and end card with a CTA.
- 🎵 **Original background music**, two engines:
  - pure Python: lofi, upbeat, Spanish rumba, cinematic, suspense, corporate;
  - FluidSynth orchestra composed note by note.
- 🔊 **Synthesized sound effects** (pop, whoosh, stamp, sparkle, boom, scratch, riser…), **music ducking** under the voice and **loudness** at −14 LUFS.
- ✅ **Quality checks.** A frame contact sheet and an audio report.

Everything is generated in code, with no third-party samples, melodies or fonts (fonts are SIL OFL), so clips don't get copyright claims.

---

## 📥 Install

### Option A: Claude.ai (web / desktop app)
1. Download **[podcast-clip-studio.zip](https://github.com/sistemaseltigre/podcast-clip-studio/raw/main/podcast-clip-studio.zip)**. Don't unzip it.
2. In Claude go to **Settings → Capabilities** and check that *Code execution and file creation* is on.
3. Under **Skills**, click **Upload skill** and choose the ZIP.
4. Done. Ask something like *"Cut 3 clips from this podcast for TikTok"* and attach the video.

### Option B: Claude Code (terminal)
```bash
git clone https://github.com/sistemaseltigre/podcast-clip-studio.git
mkdir -p ~/.claude/skills && cp -r podcast-clip-studio/podcast-clip-studio ~/.claude/skills/
```

The first time it is used, Claude runs `scripts/setup.sh` to install what it needs (Python libraries, fonts, transcription model and, optionally, FluidSynth). `ffmpeg` is required.

---

## 🗣️ Example requests
- "Here's my episode (1 hour). Find the 5 best moments and give me vertical clips of 30–45 s with captions."
- "Make a 40-second clip from minute 12:30 to 13:10, with lofi music and my brand colours #0F172A / #F59E0B."
- "Both hosts are in a wide shot: split the screen when they talk to each other."
- "Give it a movie-style intro and then switch to upbeat music."
- "Just make me 60 seconds of chill background music for my podcast."

## 📁 Contents
```
podcast-clip-studio/
├── SKILL.md              ← instructions Claude follows
├── scripts/
│   ├── setup.sh          ← dependencies and fonts
│   ├── transcribe.py     ← transcription with word timestamps (faster-whisper / sherpa-onnx)
│   ├── find_moments.py   ← readable transcript and candidate clips
│   ├── clipkit.py        ← renders the clip from a JSON spec
│   ├── gfx.py            ← captions, cards, titles, particles
│   ├── mix.py            ← voice + ducked music + SFX + loudness
│   ├── synth_music.py    ← original music in pure Python
│   ├── bgm_motor.py      ← MIDI + FluidSynth orchestral composer
│   ├── sfx.py            ← synthesized sound effects
│   └── qa.py             ← contact sheet and audio report
├── references/           ← spec reference, music guide, lessons learned
└── examples/             ← example clip spec and example music cue
```

## 🔒 Security and privacy
- The skill only runs local scripts you can read in this repository. It doesn't send your videos anywhere.
- The only downloads are public dependencies: Python packages, Google Fonts (OFL) and open-source transcription models from GitHub / Hugging Face.
- Before installing a skill from anyone, review its `SKILL.md` and `scripts/`.

## License
MIT. Use it, modify it and share it.
