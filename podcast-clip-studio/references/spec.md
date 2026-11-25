# Clip spec reference (clipkit.py)

Paths are relative to the spec file. Times called "src" are seconds in the source video; `"at"` on cards is a source time, too.

```jsonc
{
  "sources": {"main": "episode.mp4", "cam2": "guest_cam.mp4"},  // 1..n cameras, same timeline (sync first if needed)
  "audio_source": "main",              // which source's audio is the voice
  "transcript": "transcript.json",     // from transcribe.py (on the audio_source)
  "output": "out/clip01.mp4",
  "width": 1080, "height": 1920, "fps": 30,   // 1080x1080 feed, 1920x1080 YouTube
  "speed": 1.0,                        // 1.03–1.08 tightens pace without sounding fast
  "focus": [0.5, 0.42],                // default face point (fraction of source frame)
  "flip": false,                       // true for mirrored front-camera footage
  "tighten": {"max_gap": 0.45, "keep_gap": 0.14},  // null = keep all pauses
  "intro": {"dur": 0},                 // leading silence/time before the first segment (e.g. for a title)

  "segments": [
    {"in": 812.4, "out": 836.0, "zoom": 1.0, "push": 0.03},            // fill (default)
    {"in": 836.0, "out": 850.2, "zoom": 1.25, "focus": [0.62, 0.38]},   // punch-in on the guest
    {"in": 850.2, "out": 861.0, "layout": "split", "top": "main", "bottom": "cam2",
     "top_focus": [0.3, 0.4], "bottom_focus": [0.5, 0.4]},
    {"in": 861.0, "out": 870.0, "layout": "fit", "box_w": 1080, "y_center": 0.42},
    {"in": 870.0, "out": 875.0, "cam": "cam2", "tighten": false}
  ],
  // split with a reaction shot from another moment of the same camera:
  //  {"in": 900, "out": 905, "layout": "split", "top": "main", "bottom": "main", "bottom_time": 950.0}

  "captions": {"enabled": true, "style": "stroke", "y": 0.74, "size": 66, "max_chars": 16,
               "uppercase": false, "highlight": ["gratis", "nunca"]},
  "hook": {"text": "¿Por qué nadie habla de esto?", "start": 0.0, "dur": 2.6, "y": 0.2},
  "cards": [
    {"at": 820.3, "dur": 2.2, "text": "3 PASOS CLAVE", "style": "accent", "y": 0.62, "deg": -2},
    {"at": 830.0, "dur": 2.0, "text": "¡SÍ EXISTE!", "style": "stamp"},
    {"at": 813.0, "dur": 3.0, "text": "Ana López", "sub": "fundadora", "style": "name", "y": 0.62},
    {"at": 845.0, "dur": 2.5, "text": "", "style": "image", "image": "logo.png", "width": 700, "y": 0.6},
    {"at": 850.0, "dur": 2.0, "text": "COMUNIDAD", "style": "bar"}
  ],
  "watermark": "@mi_canal",
  "progress_bar": false,
  "end_card": {"dur": 3.5, "image": "cover.jpg", "title": "EPISODIO 42",
               "lines": ["Disponible en Spotify y YouTube"], "cta": ["ESCÚCHALO COMPLETO", "link.en/bio"], "handle": "@mi_canal"},

  "brand": {"bg": "#F2E1C4", "ink": "#161416", "accent": "#E2A030", "accent2": "#AC3428", "text": "#FFFFFF",
            "font_head": "Anton.ttf", "font_body": "DMSans.ttf"},   // any .ttf in the fonts cache or an absolute path

  "music": {"file": "bgm.wav", "level_db": -16, "duck": true, "loop": true, "fade_in": 0.5, "fade_out": 1.5},
  "sfx": true, "sfx_level": 0.7, "sfx_on_cuts": false,
  "voice": {"highpass": 80, "compress": 2, "gate": true, "denoise": false},
  "loudness": -14,
  "crf": 18, "preset": "medium", "keep_temp": false
}
```

## Layout guide (vertical 1080×1920)
- **Safe zones.** The platform UI covers the top ~170 px, the bottom ~380 px and a right column (~140 px) from y≈900 down. Keep text between y = 0.09 and 0.80 of the height and x ≤ 0.87 of the width.
- **Faces.** At zoom 1.0 a seated speaker's face sits around y 0.35–0.5. Put cards on the chest area (y 0.55–0.70) or in the empty top band, never over the eyes or mouth. Captions go at 0.72–0.76.
- **Two people in one wide shot.** Use two `fill` segments with different `focus` points to cut between them, or `split` with `top_focus` and `bottom_focus` to show both.
- **Landscape screen share or slides.** Use `fit`.
- **Pacing.** Change the shot every 3–6 s: punch-ins (zoom 1.15–1.4), a split screen, a card. A long static shot loses viewers.
