#!/usr/bin/env bash
# One-time setup for podcast-clip-studio. Safe to re-run.
# Usage: bash setup.sh [--music] [--asr]
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
FONTS="${CLIP_FONTS:-$HOME/.cache/podcast-clip-studio/fonts}"; mkdir -p "$FONTS"
PIP="pip install -q"; $PIP --help >/dev/null 2>&1 || true
python3 -m pip install -q numpy scipy soundfile opencv-python-headless pillow 2>/dev/null || \
python3 -m pip install -q --break-system-packages numpy scipy soundfile opencv-python-headless pillow
command -v ffmpeg >/dev/null || { echo "ffmpeg missing: install it (apt-get install ffmpeg / brew install ffmpeg)"; }

# Fonts (all SIL Open Font License, from the official Google Fonts repo)
get_font () { [ -s "$FONTS/$2" ] || curl -sfL -o "$FONTS/$2" "https://raw.githubusercontent.com/google/fonts/main/$1" || echo "font download failed: $2"; }
get_font "ofl/anton/Anton-Regular.ttf" Anton.ttf
get_font "ofl/dmsans/DMSans%5Bopsz,wght%5D.ttf" DMSans.ttf
get_font "ofl/bebasneue/BebasNeue-Regular.ttf" Bebas.ttf
get_font "ofl/caveat/Caveat%5Bwght%5D.ttf" Caveat.ttf
get_font "ofl/cinzel/Cinzel%5Bwght%5D.ttf" Cinzel.ttf
get_font "ofl/cinzeldecorative/CinzelDecorative-Bold.ttf" CinzelDecorative.ttf
get_font "ofl/cormorantgaramond/CormorantGaramond-Italic%5Bwght%5D.ttf" CormorantItalic.ttf

for a in "$@"; do
  if [ "$a" = "--asr" ]; then
    python3 -m pip install -q faster-whisper sherpa-onnx 2>/dev/null || python3 -m pip install -q --break-system-packages faster-whisper sherpa-onnx
  fi
  if [ "$a" = "--music" ]; then
    (command -v fluidsynth >/dev/null && [ -s /usr/share/sounds/sf2/FluidR3_GM.sf2 ]) || \
      { (apt-get update -q >/dev/null 2>&1; apt-get install -y -q --no-install-recommends fluidsynth fluid-soundfont-gm >/dev/null 2>&1) || \
        echo "FluidSynth not installed: synth_music.py (pure numpy) still works"; }
    python3 -m pip install -q pretty_midi 2>/dev/null || python3 -m pip install -q --break-system-packages pretty_midi
  fi
done
ls "$FONTS"
echo "setup done"
