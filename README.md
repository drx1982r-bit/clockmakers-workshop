# The Clockmaker's Workshop at Dusk

An interactive 3D cinematic experience made in Blender. It is a 60-second film plus a version you can explore yourself.

**Try it in your browser:** <https://drx1982r-bit.github.io/clockmakers-workshop/> (no install needed)

**Download the project:** click the green **Code** button above, then **Download ZIP**.

The last light of evening streams through dusty windows into an old clockmaker's workshop. A long-case astronomical clock winds itself and starts ticking. Its orrery comes to life, the lamp flickers on, and the clock strikes the hour.

---

## Quick start (Windows)

You only need to do steps 1 and 2 once.

1. **Install Blender 5.2 LTS** from <https://www.blender.org/download/> (free) and accept the default settings.
2. **Unzip** this project folder anywhere, for example in *Documents*.
3. Double-click **`OPEN_PROJECT.bat`**. Blender opens the workshop.
   - Press **N** on your keyboard (with the mouse over the 3D view) and click the **Director** tab on the right.
   - Click **Cinematic preview**, then **Play**.

That's it. Everything else is optional.

| I want to... | Double-click |
|---|---|
| Explore the workshop in my web browser (no Blender needed) | `OPEN_BROWSER_VERSION.bat` |
| Quickly check that rendering works (one 4K image, a few minutes) | `RENDER_7_Still_4K_EEVEE.bat` |
| Make a quick preview video (1080p) | `RENDER_1_Preview_Film_1080p_EEVEE.bat` |
| Make the film in good quality (recommended) | `RENDER_2_Film_1440p_EEVEE.bat` |
| Make the film in 4K | `RENDER_3_Film_4K_EEVEE.bat` |
| Make ten photoreal 4K pictures | `RENDER_5_Stills_4K_Cycles.bat` |
| Make one 8K poster image | `RENDER_6_Still_8K_Cycles.bat` |

Finished videos and pictures appear in the **`renders`** folder.

A render window can be **closed at any time**. Every finished frame is kept, and running the same file again continues where it stopped.

> **If Blender shows a yellow bar saying "Auto-run disabled"** when you open `project.blend` directly, click **Allow Execution**. This loads the Director panel. (`OPEN_PROJECT.bat` does this for you.)

---

## The Director panel (inside Blender)

Press **N** in the 3D view and open the **Director** tab.

| Section | What it does |
|---|---|
| **Play / Restart / Stop** | Controls the film. The **Space** bar also plays and pauses. |
| **Speed** | Slow motion (0.1×) up to 3× speed in the viewport. |
| **Sequences** | Jump to *Dusk*, *The Bench*, *Awakening*, *The Heavens* or *The Hour*. |
| **Cinematic preview / Fast view** | Real-time rendered view through the film cameras, or a fast simple view. |
| **Cameras** | Look through any of the 10 cinematic cameras. *Cinematic cuts* follows the film's edit. *Free explore* lets you fly around. |
| **Inspect** | Left-click any object to read about it. *Frame selected* zooms to it; *Focus camera here* racks the camera's focus onto it. |
| **Quality & Render** | Choose **Cycles** (photoreal) or **EEVEE** (fast), choose **Low / Medium / High / Ultra**, then render an image or the film. |
| **Atmosphere** | Haze density (god-rays), dust motes, and the strength of the colour grade. |
| **Audio** | Master, music, ambience and effects volume, plus mute. |

**Mouse controls in Blender:**

- **Orbit:** hold the middle mouse button (the scroll wheel) and drag.
- **Zoom:** scroll.
- **Pan:** Shift + middle-mouse drag.
- **Select:** left-click.

---

## The browser version

Open `web_viewer/index.html` (or double-click `OPEN_BROWSER_VERSION.bat`). It runs in Chrome, Edge or Firefox with no installation and no internet needed (only the fonts download if you are online).

- **Play / pause / restart**, a **timeline** with chapter markers, and **speed** from 0.25× to 2×.
- **Cameras:** *Cinematic* (follows the film), any single shot, or a **free camera**: drag to orbit, scroll to zoom, right-drag to pan.
- **Click any object** to read about it. **Look closer** flies the camera to it.
- **Quality:** Low / Medium / High / Ultra. Use *Medium* or *Low* if it feels slow on integrated graphics.
- **Sound mixer** with separate music, ambience and effects volumes.
- **Keyboard:**
  - **Space** play/pause, **R** restart
  - **1–5** jump to a chapter, **← →** skip 2 seconds, **↑ ↓** change speed
  - **F** free camera, **C** cinematic camera, **?** show help

---

## Quality presets and render times on your PC

Your PC is an AMD Ryzen 7 PRO 4750G (8 cores, 16 threads) with built-in Radeon Vega graphics.

- **Cycles** is the photoreal path tracer. Blender's Cycles cannot use Vega integrated graphics, so it runs on your 16 CPU threads. It is ideal for still images but slow for a whole film.
- **EEVEE** is the real-time engine. It uses your Radeon graphics and is many times faster, so it is the best choice for rendering the film.

| Preset | Resolution | Cycles samples | Best use |
|---|---|---|---|
| Low | 1920 × 1080 | 64 | previews |
| Medium | 2560 × 1440 | 256 | good films |
| High | 3840 × 2160 (4K) | 1024 | 4K films (EEVEE), 4K photos (Cycles) |
| Ultra | 7680 × 4320 (8K) | 2048 | 8K poster images |

Rough time estimates on your PC (the render window shows the real speed after the first frames):

| Task | Engine | Estimate |
|---|---|---|
| 1080p film | EEVEE | 1–3 hours |
| 1440p film | EEVEE | 4–10 hours |
| 4K film | EEVEE | 12–24 hours |
| 1080p film | Cycles | about 1 day |
| One 4K photo | Cycles | 30–60 minutes |
| One 8K photo | Cycles | 6–12 hours |

A full **4K film in Cycles** would take several weeks on any CPU. That is why the 4K film launcher uses EEVEE. If you ever add a supported graphics card (NVIDIA RTX, or AMD Radeon RX 6000 or newer), Cycles will use it automatically and become 5–20× faster.

---

## What's in the folder

```
ClockmakersWorkshop/
├── project.blend                  the Blender project (open this)
├── OPEN_PROJECT.bat               opens it with the Director panel enabled
├── OPEN_BROWSER_VERSION.bat       opens the browser version
├── RENDER_*.bat                   one-click renders (see the table above)
├── REBUILD_PROJECT.bat            regenerates everything from the Python scripts
├── ClockmakersDirector_addon.py   the Director panel as an installable add-on (optional)
├── scripts/                       all Python source (scene, materials, animation, audio, export)
├── materials/textures/            generated textures (blueprint drawing)
├── audio/                         music, ambience and sound effects (WAV) + event timeline
├── web_viewer/                    the browser version (index.html)
├── renders/                       your renders appear here
└── docs/TECHNICAL.md              how everything is built
```

---

## Troubleshooting

- **"Blender was not found"**: install Blender 5.2 from blender.org. If you installed it somewhere unusual, open `scripts\windows\find_blender.bat` in Notepad and put the full path to `blender.exe` on the marked line.
- **The Director tab is missing**: open the file with `OPEN_PROJECT.bat`, or click *Allow Execution* in the yellow bar. You can also install `ClockmakersDirector_addon.py` permanently: in Blender go to *Edit → Preferences → Add-ons*, open the menu (˅) and choose *Install from Disk*.
- **The browser version is slow**: pick *Low* or *Medium* in the quality menu (bottom right).
- **No sound in the browser**: browsers only allow sound after a click. Press *Enter the workshop* or click the page.
