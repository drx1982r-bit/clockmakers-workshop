"""
export_web.py - exports the scene for the browser version (web_viewer/).

Writes:
  web_viewer/data/scene.glb      geometry + all object animation (sampled, 24 fps)
  web_viewer/data/cameras.json   every frame of every cinematic camera (position, rotation, lens, focus)
  web_viewer/data/events.json    timeline events (shared with the audio)

Run:  python scripts/export_web.py     (or: blender -b project.blend -P scripts/export_web.py)
"""
import json
import math
import os
import sys

import bpy
import addon_utils
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "web_viewer", "data")
sys.path.insert(0, HERE)

C = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))  # Blender Z-up -> glTF Y-up


def main():
    if not bpy.data.filepath:
        bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, "project.blend"))
    addon_utils.enable('io_scene_gltf2')
    os.makedirs(OUT, exist_ok=True)
    sc = bpy.context.scene

    # ---------------- cameras (sampled every frame, following the marker-based edit)
    markers = sorted([m for m in sc.timeline_markers if m.camera], key=lambda m: m.frame)
    shots = []
    for i, m in enumerate(markers):
        cam = m.camera
        end = markers[i + 1].frame - 1 if i + 1 < len(markers) else sc.frame_end
        shots.append(dict(name=cam.name, label=cam.get("cw_label", cam.name), kind=cam.get("cw_kind", ""),
                          start=m.frame, end=end, fstop=cam.data.dof.aperture_fstop, frames=[]))
    for f in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(f)
        for s in shots:
            cam = bpy.data.objects[s['name']]
            mw = C @ cam.matrix_world
            loc, rot, _ = mw.decompose()
            foc = cam.data.dof.focus_object
            fd = (cam.matrix_world.translation - foc.matrix_world.translation).length if foc else 3.0
            s['frames'].append([round(loc.x, 4), round(loc.y, 4), round(loc.z, 4),
                                round(rot.x, 5), round(rot.y, 5), round(rot.z, 5), round(rot.w, 5),
                                round(cam.data.lens, 2), round(fd, 3)])
    json.dump(dict(fps=sc.render.fps, frame_start=sc.frame_start, frame_end=sc.frame_end,
                   sensor=36.0, shots=shots), open(os.path.join(OUT, "cameras.json"), "w"), separators=(',', ':'))
    print(f"[web] cameras.json: {len(shots)} shots x {sc.frame_end} frames")

    # ---------------- strip things the browser recreates itself (fog volume, particles, cameras, lights)
    for name in ("RoomFog", "DustEmitter", "DustMote", "DustTurbulence"):
        ob = bpy.data.objects.get(name)
        if ob:
            bpy.data.objects.remove(ob)
    for ob in [o for o in bpy.data.objects if o.type in ('CAMERA', 'LIGHT')]:
        bpy.data.objects.remove(ob)
    # bevel modifiers: keep (they shape the highlights) but use 1 segment to save polygons
    for ob in bpy.data.objects:
        for md in ob.modifiers:
            if md.type == 'BEVEL':
                md.segments = 1
    # box-projected UVs (1 unit = 1 m) so the browser can apply its generated textures
    import bmesh
    done = set()
    for ob in bpy.data.objects:
        if ob.type != 'MESH' or ob.data.name in done or ob.data.uv_layers:
            continue
        done.add(ob.data.name)
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        uv = bm.loops.layers.uv.new("UVMap")
        for f in bm.faces:
            n = f.normal
            ax = max(range(3), key=lambda i: abs(n[i]))
            a, b = [(1, 2), (0, 2), (0, 1)][ax]
            for l in f.loops:
                co = l.vert.co
                l[uv].uv = (co[a], co[b])
        bm.to_mesh(ob.data)
        bm.free()
    sc.frame_set(1)
    path = os.path.join(OUT, "scene.glb")
    bpy.ops.export_scene.gltf(
        filepath=path, export_format='GLB', export_apply=True, export_extras=True,
        export_cameras=False, export_lights=False, export_animations=True,
        export_animation_mode='SCENE', export_force_sampling=True, export_frame_range=True,
        export_optimize_animation_size=True, export_anim_single_armature=False,
        export_draco_mesh_compression_enable=False, export_materials='EXPORT',
        export_image_format='JPEG', export_jpeg_quality=85, export_yup=True)
    print(f"[web] scene.glb: {os.path.getsize(path) / 1e6:.1f} MB")
    ev = os.path.join(ROOT, "audio", "events.json")
    if os.path.exists(ev):
        open(os.path.join(OUT, "events.json"), "w").write(open(ev).read())
    pack()


def pack():
    """Bundle everything into data/scene_data.js so index.html works by double-click (file://)."""
    import base64
    glb = base64.b64encode(open(os.path.join(OUT, "scene.glb"), "rb").read()).decode()
    cams = open(os.path.join(OUT, "cameras.json")).read()
    ev = open(os.path.join(OUT, "events.json")).read()
    with open(os.path.join(OUT, "scene_data.js"), "w") as f:
        f.write("window.CW_DATA={cameras:" + cams + ",events:" + ev + ",glb:\"" + glb + "\"};\n")
    print(f"[web] scene_data.js: {os.path.getsize(os.path.join(OUT, 'scene_data.js')) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
