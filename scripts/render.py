"""
render.py - command-line rendering for The Clockmaker's Workshop.

Usage (Blender installed):
  blender -b project.blend -P scripts/render.py -- [options]

Options:
  --preset LOW|MEDIUM|HIGH|ULTRA   quality preset (default HIGH)
  --engine CYCLES|EEVEE            render engine (default CYCLES)
  --still FRAME                    render a single still image of FRAME
  --stills                         render one hero still from every camera shot
  --start N --end N                frame range for the film (default whole film)
  --step N                         render every Nth frame (fast previews)
  --percent P                      resolution percentage (e.g. 50)
  --samples N                      override Cycles samples
  --vstep X                        override Cycles volume step rate (preview speed-up)
  --encode                         after rendering frames, build MP4 (with audio)
  --encode-only                    only build the MP4 from existing frames
  --out DIR                        output folder (default renders/)

Frames render as PNG files and already-finished frames are skipped, so a long
render can be stopped and resumed at any time.
"""
import argparse
import glob
import os
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import cw_presets  # noqa: E402


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="HIGH")
    ap.add_argument("--engine", default="CYCLES")
    ap.add_argument("--still", type=int)
    ap.add_argument("--stills", action="store_true")
    ap.add_argument("--start", type=int)
    ap.add_argument("--end", type=int)
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--percent", type=int, default=100)
    ap.add_argument("--samples", type=int)
    ap.add_argument("--vstep", type=float, help="Cycles volume step rate (higher = faster, noisier haze)")
    ap.add_argument("--encode", action="store_true")
    ap.add_argument("--encode-only", action="store_true")
    ap.add_argument("--out", default=os.path.join(ROOT, "renders"))
    ap.add_argument("--blend", default=os.path.join(ROOT, "project.blend"))
    ap.add_argument("--tag", default="")
    return ap.parse_args(argv)


def ensure_open(path):
    if not bpy.data.filepath or os.path.abspath(bpy.data.filepath) != os.path.abspath(path):
        bpy.ops.wm.open_mainfile(filepath=path)


def configure(a):
    sc = bpy.context.scene
    cw_presets.apply_preset(sc, a.preset, a.engine, a.percent)
    if a.engine.upper() == 'CYCLES':
        dev = cw_presets.enable_best_device(sc)
        print(f"[render] Cycles device: {dev}")
    if a.vstep:
        sc.cycles.volume_step_rate = a.vstep
    if a.samples:
        sc.cycles.samples = a.samples
        sc.eevee.taa_render_samples = a.samples
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_depth = '16' if a.preset.upper() in ('HIGH', 'ULTRA') else '8'
    sc.render.image_settings.color_mode = 'RGB'
    return sc


def render_still(sc, frame, path):
    sc.frame_set(frame)
    # make sure the right camera is active for this frame (marker-bound cuts)
    cam = None
    for m in sorted(sc.timeline_markers, key=lambda m: m.frame):
        if m.frame <= frame and m.camera:
            cam = m.camera
    if cam:
        sc.camera = cam
    sc.render.filepath = path
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"[render] still frame {frame} -> {path}  ({time.time() - t:.1f}s)")


def render_frames(sc, a, folder):
    os.makedirs(folder, exist_ok=True)
    start = a.start or sc.frame_start
    end = a.end or sc.frame_end
    total = len(range(start, end + 1, a.step))
    done = 0
    t0 = time.time()
    for f in range(start, end + 1, a.step):
        path = os.path.join(folder, f"frame_{f:04d}.png")
        done += 1
        if os.path.exists(path) and os.path.getsize(path) > 0:
            continue
        render_still(sc, f, path)
        el = time.time() - t0
        print(f"[render] {done}/{total} done, elapsed {el / 60:.1f} min")


def encode_video(a, folder, out_path):
    """Assemble PNG frames + the soundtrack into an H.264 MP4 using Blender's own FFmpeg."""
    frames = sorted(glob.glob(os.path.join(folder, "frame_*.png")))
    if not frames:
        print("[encode] no frames found in", folder)
        return
    src = bpy.context.scene
    fps = src.render.fps
    step = a.step
    vs = bpy.data.scenes.new("CW_Encode")
    vs.render.fps = max(1, fps // step) if step > 1 else fps
    se = vs.sequence_editor_create()
    strips = se.strips if hasattr(se, 'strips') else se.sequences
    first = os.path.basename(frames[0])
    im = strips.new_image("frames", frames[0], 1, 1)
    for f in frames[1:]:
        im.elements.append(os.path.basename(f))
    n = len(frames)
    vs.frame_start = 1
    vs.frame_end = n
    audio_dir = os.path.join(ROOT, "audio")
    first_frame = int(first.split('_')[1].split('.')[0])
    for name, ch in (("music.wav", 2), ("ambience.wav", 3), ("sfx.wav", 4)):
        p = os.path.join(audio_dir, name)
        if os.path.exists(p) and step == 1:
            s = strips.new_sound(name, p, ch, 1 - (first_frame - 1))
            vol = {"music.wav": 0.55, "ambience.wav": 0.7, "sfx.wav": 0.9}[name]
            for st in (getattr(src.sequence_editor, 'strips', None) or []):
                if st.type == 'SOUND' and st.name.startswith(name.split('.')[0]):
                    vol = st.volume
            s.volume = vol
    r = vs.render
    im0 = bpy.data.images.load(frames[0])
    r.resolution_x, r.resolution_y = im0.size
    r.resolution_percentage = 100
    bpy.data.images.remove(im0)
    if hasattr(r.image_settings, 'media_type'):
        r.image_settings.media_type = 'VIDEO'   # Blender 5.x
    r.image_settings.file_format = 'FFMPEG'
    r.ffmpeg.format = 'MPEG4'
    r.ffmpeg.codec = 'H264'
    r.ffmpeg.constant_rate_factor = 'HIGH'
    r.ffmpeg.ffmpeg_preset = 'GOOD'
    r.ffmpeg.audio_codec = 'AAC'
    r.ffmpeg.audio_bitrate = 256
    r.ffmpeg.audio_mixrate = 48000
    vs.view_settings.view_transform = 'Standard'
    r.use_sequencer = True
    r.use_compositing = False
    r.filepath = out_path
    with bpy.context.temp_override(scene=vs):
        bpy.ops.render.render(animation=True, scene=vs.name)
    print("[encode] video written:", out_path)


def main():
    a = parse()
    ensure_open(a.blend)
    sc = configure(a)
    tag = a.tag or f"{a.preset.lower()}_{a.engine.lower()}"
    if a.still is not None:
        render_still(sc, a.still, os.path.join(a.out, "stills", f"still_{tag}_{a.still:04d}.png"))
        return
    if a.stills:
        for m in sorted(sc.timeline_markers, key=lambda m: m.frame):
            cam = m.camera
            if not cam:
                continue
            mid = (int(cam.get("cw_start", m.frame)) + int(cam.get("cw_end", m.frame))) // 2
            render_still(sc, mid, os.path.join(a.out, "stills", f"{tag}_{m.frame:04d}_{m.name}.png"))
        return
    folder = os.path.join(a.out, "frames", tag)
    if not a.encode_only:
        render_frames(sc, a, folder)
    if a.encode or a.encode_only:
        encode_video(a, folder, os.path.join(a.out, f"ClockmakersWorkshop_{tag}.mp4"))


if __name__ == "__main__":
    main()
