"""
build_scene.py - builds the complete project and saves ../project.blend

Run with Blender:
    blender -b -P scripts/build_scene.py
or with the bpy Python module:
    python scripts/build_scene.py
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import bpy  # noqa: E402

for mod in [m for m in list(sys.modules) if m.startswith('cw_')]:
    del sys.modules[mod]

import cw_textures  # noqa: E402
import cw_materials  # noqa: E402
import cw_models  # noqa: E402
import cw_lighting  # noqa: E402
import cw_presets  # noqa: E402
import cw_animation  # noqa: E402
import cw_compositor  # noqa: E402


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def setup_scene():
    sc = bpy.context.scene
    sc.name = "ClockmakersWorkshop"
    sc.render.fps = 24
    sc.frame_start = 1
    sc.frame_end = cw_animation.FRAME_END
    sc.unit_settings.system = 'METRIC'
    vs = sc.view_settings
    sc.display_settings.display_device = 'sRGB'
    vs.view_transform = 'AgX'
    vs.look = 'AgX - Medium High Contrast'
    vs.exposure = 0.0
    vs.gamma = 1.0
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_depth = '16'
    return sc


def main():
    t0 = time.time()
    reset()
    sc = setup_scene()
    tex_dir = os.path.join(ROOT, "materials", "textures")
    img = cw_textures.blueprint(os.path.join(tex_dir, "blueprint.png"))
    bp = cw_textures.save_with_bpy(img, os.path.join(tex_dir, "blueprint.png"), "Blueprint")
    M = cw_materials.build_all(bp)
    R = cw_models.build_all(M, cw_lighting.SUN_DIR)
    L = cw_lighting.build(R)
    sc.render.engine = 'CYCLES'
    cw_presets.enable_best_device(sc)
    cw_presets.apply_preset(sc, 'HIGH')
    cams = cw_animation.build(sc, R, L, M)
    cw_compositor.build(sc)
    audio_dir = os.path.join(ROOT, "audio")
    if os.path.isdir(audio_dir):
        cw_animation.add_audio(sc, audio_dir)
    # embed the Director panel so it is available as soon as the file is opened
    addon_path = os.path.join(HERE, "director_addon.py")
    if os.path.exists(addon_path):
        src = open(addon_path, encoding='utf-8').read()
        presets = open(os.path.join(HERE, "cw_presets.py"), encoding='utf-8').read()
        presets = presets.replace("import bpy\n", "", 1)
        src = src.replace("# @@PRESETS@@", "# ---- inlined from cw_presets.py ----\n" + presets + "\n# ---- end presets ----\n", 1)
        open(os.path.join(ROOT, "ClockmakersDirector_addon.py"), "w", encoding='utf-8').write(src)
        txt = bpy.data.texts.get("director_addon.py") or bpy.data.texts.new("director_addon.py")
        txt.from_string(src)
        txt.use_module = True
        # register now so the scene gets its Director settings saved in the file
        ns = {"__name__": "cw_director_build"}
        exec(compile(src, "director_addon.py", "exec"), ns)
        ns["register"]()
    sc.frame_set(1)
    out = os.path.join(ROOT, "project.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    bpy.ops.file.make_paths_relative()      # portable: audio/textures resolve next to the .blend
    bpy.ops.wm.save_mainfile(compress=True)
    n_obj = len(bpy.data.objects)
    n_poly = sum(len(o.data.polygons) for o in bpy.data.objects if o.type == 'MESH')
    print(f"[build] saved {out}: {n_obj} objects, {n_poly:,} base polygons, "
          f"{len(bpy.data.materials)} materials, {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
