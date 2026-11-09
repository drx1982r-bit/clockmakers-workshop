bl_info = {
    "name": "Clockmaker's Workshop - Director",
    "author": "Clockmaker's Workshop project",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),
    "location": "3D Viewport > Sidebar (N) > Director",
    "description": "Play, pause, cameras, inspection, quality presets, atmosphere and audio for the "
                   "Clockmaker's Workshop cinematic experience",
    "category": "Interface",
}
"""
Director panel for "The Clockmaker's Workshop at Dusk".

Open the 3D Viewport sidebar (press N) and click the "Director" tab.
Everything a viewer needs is one click away:
  Playback   play / pause / restart, speed, loop, jump to a sequence
  Cameras    every cinematic shot, cinematic auto-cuts, free explore camera
  Inspect    click any object to read about it, focus on it, rack focus to it
  Quality    Low / Medium / High / Ultra presets, Cycles or EEVEE, render buttons
  Atmosphere haze density, dust, colour-grade strength
  Audio      master / music / ambience / effects volume, mute
"""
import os
import bpy
from bpy.props import (BoolProperty, EnumProperty, FloatProperty, PointerProperty, StringProperty)

# ---- inlined from cw_presets.py ----
"""
cw_presets.py - quality presets (Low / Medium / High / Ultra) for Cycles and EEVEE.

Self-contained (only needs bpy) so it can be used by build_scene.py, the
Director panel inside Blender and the command-line render script.

Tuned for the target PC (AMD Ryzen 7 PRO 4750G, 8 cores / 16 threads,
integrated Radeon Vega graphics):
  * Cycles runs on the CPU (Vega iGPUs are not supported by Cycles HIP).
    If a supported GPU is ever installed, enable_best_device() uses it automatically.
  * EEVEE runs on the integrated Radeon via OpenGL and is many times faster.
"""

PRESETS = {
    #            resolution     cycles  noise   bounces vol-step dust  eevee  shadows  mblur
    'LOW':    dict(res=(1920, 1080), spp=64,   thr=0.06,  bounces=4,  vstep=4.0, dust=500,  ee=16,  shadow=0.5,  mblur=False, vol_tile='16', vol_samples=32),
    'MEDIUM': dict(res=(2560, 1440), spp=256,  thr=0.025, bounces=6,  vstep=2.0, dust=1200, ee=64,  shadow=1.0,  mblur=True,  vol_tile='8',  vol_samples=64),
    'HIGH':   dict(res=(3840, 2160), spp=1024, thr=0.012, bounces=8,  vstep=1.0, dust=1800, ee=128, shadow=1.0,  mblur=True,  vol_tile='4',  vol_samples=96),
    'ULTRA':  dict(res=(7680, 4320), spp=2048, thr=0.006, bounces=12, vstep=0.5, dust=3000, ee=256, shadow=1.0,  mblur=True,  vol_tile='2',  vol_samples=128),
}

DESCRIPTIONS = {
    'LOW': "1080p - fast previews",
    'MEDIUM': "1440p - good quality, reasonable time",
    'HIGH': "4K UHD - cinematic final quality",
    'ULTRA': "8K - maximum detail (best for still images)",
}


def enable_best_device(scene):
    """Use a supported GPU for Cycles if one exists, otherwise all CPU threads."""
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
    except KeyError:
        return 'CPU'
    for backend in ('OPTIX', 'CUDA', 'HIP', 'ONEAPI', 'METAL'):
        try:
            prefs.compute_device_type = backend
        except TypeError:
            continue
        prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type == backend]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == backend
            scene.cycles.device = 'GPU'
            return backend
    try:
        prefs.compute_device_type = 'NONE'
    except TypeError:
        pass
    scene.cycles.device = 'CPU'
    return 'CPU'


def apply_preset(scene, name='HIGH', engine=None, percentage=100):
    p = PRESETS[name.upper()]
    r = scene.render
    if engine:
        r.engine = 'CYCLES' if engine.upper() == 'CYCLES' else 'BLENDER_EEVEE'
    r.resolution_x, r.resolution_y = p['res']
    r.resolution_percentage = percentage
    r.use_motion_blur = p['mblur']
    r.motion_blur_shutter = 0.5
    scene['cw_quality'] = name.upper()

    # ---------------- Cycles
    c = scene.cycles
    c.samples = p['spp']
    c.use_adaptive_sampling = True
    c.adaptive_threshold = p['thr']
    c.adaptive_min_samples = 0
    c.use_denoising = True
    c.denoiser = 'OPENIMAGEDENOISE'
    c.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
    try:
        c.denoising_prefilter = 'ACCURATE'
        c.denoising_quality = 'HIGH'
    except (AttributeError, TypeError):
        pass
    c.preview_samples = 32
    c.use_preview_denoising = True
    c.max_bounces = p['bounces']
    c.diffuse_bounces = min(4, p['bounces'])
    c.glossy_bounces = min(6, p['bounces'])
    c.transmission_bounces = max(8, p['bounces'])
    c.volume_bounces = 1 if p['bounces'] < 8 else 2
    c.transparent_max_bounces = 16
    c.sample_clamp_direct = 0.0
    c.sample_clamp_indirect = 8.0
    c.blur_glossy = 0.6
    c.caustics_reflective = False
    c.caustics_refractive = p['bounces'] >= 12
    c.volume_step_rate = p['vstep']
    c.volume_preview_step_rate = 4.0
    c.volume_max_steps = 512
    c.use_light_tree = True
    c.film_exposure = 1.0
    r.use_persistent_data = True
    try:
        c.use_auto_tile = True
        c.tile_size = 2048
    except AttributeError:
        pass

    # ---------------- EEVEE
    e = scene.eevee
    e.taa_render_samples = p['ee']
    e.taa_samples = 16
    e.use_raytracing = True
    e.ray_tracing_method = 'SCREEN'
    e.use_fast_gi = True
    e.fast_gi_method = 'GLOBAL_ILLUMINATION'
    e.use_shadows = True
    e.shadow_ray_count = 2 if name.upper() in ('HIGH', 'ULTRA') else 1
    e.shadow_step_count = 6
    e.shadow_resolution_scale = p['shadow']
    e.use_volumetric_shadows = True
    e.volumetric_tile_size = p['vol_tile']
    e.volumetric_samples = p['vol_samples']
    e.volumetric_shadow_samples = 32
    e.volumetric_ray_depth = 8
    e.motion_blur_steps = 2 if p['mblur'] else 1
    try:
        e.ray_tracing_options.resolution_scale = '1' if name.upper() in ('HIGH', 'ULTRA') else '2'
        e.ray_tracing_options.use_denoise = True
    except (AttributeError, TypeError):
        pass

    # ---------------- scene content that scales with quality
    dust = bpy.data.objects.get('DustEmitter')
    if dust and dust.particle_systems:
        dust.particle_systems[0].settings.count = p['dust']
    return p

# ---- end presets ----

try:
    PRESETS  # noqa: F821  (defined when inlined)
except NameError:
    import sys
    _d = os.path.join(os.path.dirname(bpy.data.filepath), "scripts")
    if _d not in sys.path:
        sys.path.insert(0, _d)
    from cw_presets import PRESETS, DESCRIPTIONS, apply_preset, enable_best_device  # noqa: E402

SEQUENCES = [("Dusk", 1), ("The Bench", 289), ("Awakening", 577), ("The Heavens", 913), ("The Hour", 1201)]


def shot_cameras():
    cams = [o for o in bpy.data.objects if o.type == 'CAMERA' and o.name.startswith("Cam_")]
    return sorted(cams, key=lambda c: c.get("cw_start", 99999))


def find_info(ob):
    while ob is not None:
        if "cw_info" in ob:
            return ob["cw_info"]
        ob = ob.parent
    return ""


def view3d_areas(context):
    scr = context.window.screen if context.window else None
    return [a for a in (scr.areas if scr else []) if a.type == 'VIEW_3D']


def set_view(context, camera_view=True, shading=None):
    for area in view3d_areas(context):
        sp = area.spaces.active
        if shading:
            sp.shading.type = shading
        rv = sp.region_3d
        if camera_view and rv.view_perspective != 'CAMERA':
            rv.view_perspective = 'CAMERA'
        elif not camera_view:
            rv.view_perspective = 'PERSP'

# ------------------------------------------------------------------ property callbacks

def _upd_speed(self, context):
    sc = context.scene
    sc.render.fps_base = 1.0 / max(0.05, self.speed)


def _upd_audio(self, context):
    sc = context.scene
    sc.audio_volume = self.vol_master
    sc.use_audio = self.mute          # Blender: use_audio=True means "mute"
    se = sc.sequence_editor
    if not se:
        return
    strips = se.strips if hasattr(se, 'strips') else se.sequences
    for st in strips:
        if st.type == 'SOUND':
            g = st.get("cw_group", "")
            st.volume = {'music': self.vol_music, 'ambience': self.vol_ambience,
                         'effects': self.vol_effects}.get(g, st.volume)


def _upd_fog(self, context):
    m = bpy.data.materials.get("RoomFog")
    if m and m.node_tree:
        n = m.node_tree.nodes.get("FogDensity")
        if n:
            n.inputs[1].default_value = self.fog
    fog = bpy.data.objects.get("RoomFog")
    if fog:
        fog.hide_render = self.fog <= 0.0001
        fog.hide_viewport = self.fog <= 0.0001


def _upd_dust(self, context):
    em = bpy.data.objects.get("DustEmitter")
    if em:
        for md in em.modifiers:
            if md.type == 'PARTICLE_SYSTEM':
                md.show_render = self.dust
                md.show_viewport = self.dust


def _upd_grade(self, context):
    ng = context.scene.compositing_node_group
    if not ng:
        return
    g = ng.nodes.get("Grade")
    if g:
        for s in g.inputs:
            if s.name == 'Factor':
                s.default_value = self.grade
    v = ng.nodes.get("Vignette")
    if v:
        v.inputs[0].default_value = 0.38 * self.grade
    b = ng.nodes.get("Bloom")
    if b:
        for s in b.inputs:
            if s.name == 'Strength':
                s.default_value = 0.18 * self.grade


def _upd_cuts(self, context):
    sc = context.scene
    cams = {c.name.replace("Cam_", ""): c for c in shot_cameras()}
    for m in sc.timeline_markers:
        m.camera = cams.get(m.name) if self.auto_cuts else None


def _upd_quality(self, context):
    apply_preset(context.scene, self.quality, self.engine)
    if self.engine == 'CYCLES':
        enable_best_device(context.scene)


class CWDirectorProps(bpy.types.PropertyGroup):
    speed: FloatProperty(name="Speed", default=1.0, min=0.1, max=3.0, step=10, update=_upd_speed,
                         description="Playback speed in the viewport (renders always use real time)")
    loop: BoolProperty(name="Loop", default=True)
    auto_cuts: BoolProperty(name="Cinematic cuts", default=True, update=_upd_cuts,
                            description="Switch cameras automatically following the film's edit")
    quality: EnumProperty(name="Quality", default='HIGH', update=_upd_quality, items=[
        ('LOW', "Low", "1080p, fast"), ('MEDIUM', "Medium", "1440p"), ('HIGH', "High", "4K"),
        ('ULTRA', "Ultra", "8K")])
    engine: EnumProperty(name="Engine", default='CYCLES', update=_upd_quality, items=[
        ('CYCLES', "Cycles", "Path-traced, photorealistic (CPU on this PC)"),
        ('EEVEE', "EEVEE", "Real-time engine, uses your Radeon graphics, much faster")])
    fog: FloatProperty(name="Haze", default=0.075, min=0.0, max=0.4, update=_upd_fog,
                       description="Density of the dusty air that makes god-rays visible")
    dust: BoolProperty(name="Dust motes", default=True, update=_upd_dust)
    grade: FloatProperty(name="Grade", default=1.0, min=0.0, max=1.5, update=_upd_grade,
                         description="Strength of the colour grade, bloom and vignette")
    vol_master: FloatProperty(name="Master", default=1.0, min=0.0, max=2.0, update=_upd_audio)
    vol_music: FloatProperty(name="Music", default=0.55, min=0.0, max=1.5, update=_upd_audio)
    vol_ambience: FloatProperty(name="Ambience", default=0.7, min=0.0, max=1.5, update=_upd_audio)
    vol_effects: FloatProperty(name="Effects", default=0.9, min=0.0, max=1.5, update=_upd_audio)
    mute: BoolProperty(name="Mute", default=False, update=_upd_audio)

# ------------------------------------------------------------------ operators

class CW_OT_play(bpy.types.Operator):
    bl_idname = "cw.play"
    bl_label = "Play / Pause"
    bl_description = "Play or pause the film (Space bar also works)"

    def execute(self, context):
        bpy.ops.screen.animation_play()
        return {'FINISHED'}


class CW_OT_restart(bpy.types.Operator):
    bl_idname = "cw.restart"
    bl_label = "Restart"
    bl_description = "Jump to the start and play from the beginning"

    def execute(self, context):
        sc = context.scene
        if context.screen.is_animation_playing:
            bpy.ops.screen.animation_cancel(restore_frame=False)
        sc.frame_set(sc.frame_start)
        bpy.ops.screen.animation_play()
        return {'FINISHED'}


class CW_OT_stop(bpy.types.Operator):
    bl_idname = "cw.stop"
    bl_label = "Stop"
    bl_description = "Stop and go back to the first frame"

    def execute(self, context):
        if context.screen.is_animation_playing:
            bpy.ops.screen.animation_cancel(restore_frame=False)
        context.scene.frame_set(context.scene.frame_start)
        return {'FINISHED'}


class CW_OT_jump(bpy.types.Operator):
    bl_idname = "cw.jump"
    bl_label = "Jump"
    bl_description = "Jump to this point of the film"
    frame: bpy.props.IntProperty()

    def execute(self, context):
        context.scene.frame_set(self.frame)
        return {'FINISHED'}


class CW_OT_view_camera(bpy.types.Operator):
    bl_idname = "cw.view_camera"
    bl_label = "View camera"
    bl_description = "Look through this camera and jump to its shot"
    name: StringProperty()

    def execute(self, context):
        sc = context.scene
        cam = bpy.data.objects.get(self.name)
        if not cam:
            return {'CANCELLED'}
        p = sc.cw_director
        if cam.name != "Cam_Explore" and p.auto_cuts:
            sc.frame_set(int(cam.get("cw_start", sc.frame_current)) + 1)
        else:
            p.auto_cuts = False
            if "cw_start" in cam:
                sc.frame_set(int(cam["cw_start"]) + 1)
        sc.camera = cam
        set_view(context, camera_view=True)
        return {'FINISHED'}


class CW_OT_explore(bpy.types.Operator):
    bl_idname = "cw.explore"
    bl_label = "Free explore"
    bl_description = ("Leave the cameras and fly around freely: middle-mouse drag = orbit, "
                      "scroll = zoom, Shift + middle-mouse = pan")

    def execute(self, context):
        set_view(context, camera_view=False)
        return {'FINISHED'}


class CW_OT_interactive(bpy.types.Operator):
    bl_idname = "cw.interactive"
    bl_label = "Cinematic preview"
    bl_description = "Real-time rendered preview through the film cameras (EEVEE on your graphics card)"

    def execute(self, context):
        p = context.scene.cw_director
        p.engine = 'EEVEE'
        set_view(context, camera_view=True, shading='RENDERED')
        return {'FINISHED'}


class CW_OT_solid(bpy.types.Operator):
    bl_idname = "cw.solid"
    bl_label = "Fast view"
    bl_description = "Switch the viewport back to fast solid shading"

    def execute(self, context):
        set_view(context, camera_view=False, shading='SOLID')
        return {'FINISHED'}


class CW_OT_focus(bpy.types.Operator):
    bl_idname = "cw.focus"
    bl_label = "Frame selected"
    bl_description = "Zoom the viewport onto the selected object"

    def execute(self, context):
        set_view(context, camera_view=False)
        for area in view3d_areas(context):
            region = [r for r in area.regions if r.type == 'WINDOW'][0]
            with context.temp_override(area=area, region=region):
                bpy.ops.view3d.view_selected(use_all_regions=False)
        return {'FINISHED'}


class CW_OT_rack_focus(bpy.types.Operator):
    bl_idname = "cw.rack_focus"
    bl_label = "Focus camera here"
    bl_description = "Make the active camera's depth of field focus on the selected object"

    def execute(self, context):
        cam = context.scene.camera
        ob = context.active_object
        if cam and ob and cam.type == 'CAMERA':
            cam.data.dof.use_dof = True
            cam.data.dof.focus_object = ob
            self.report({'INFO'}, f"{cam.name} now focuses on {ob.name}")
        return {'FINISHED'}


class CW_OT_render(bpy.types.Operator):
    bl_idname = "cw.render"
    bl_label = "Render"
    bl_description = "Render with the current quality preset"
    animation: BoolProperty(default=False)

    def execute(self, context):
        sc = context.scene
        sc.render.fps_base = 1.0
        if self.animation:
            base = os.path.join(os.path.dirname(bpy.data.filepath), "renders", "frames",
                                f"{sc.cw_director.quality.lower()}_{sc.cw_director.engine.lower()}", "frame_")
            sc.render.filepath = base
            sc.render.use_overwrite = False
            sc.render.use_placeholder = True
        bpy.ops.render.render('INVOKE_DEFAULT', animation=self.animation, write_still=not self.animation)
        return {'FINISHED'}


class CW_OT_reset_look(bpy.types.Operator):
    bl_idname = "cw.reset_look"
    bl_label = "Reset atmosphere"

    def execute(self, context):
        p = context.scene.cw_director
        p.fog, p.dust, p.grade = 0.075, True, 1.0
        return {'FINISHED'}

# ------------------------------------------------------------------ panels

class CW_PT_base:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Director"


class CW_PT_main(CW_PT_base, bpy.types.Panel):
    bl_label = "The Clockmaker's Workshop"

    def draw(self, context):
        sc = context.scene
        p = sc.cw_director
        L = self.layout
        playing = context.screen.is_animation_playing
        row = L.row(align=True)
        row.scale_y = 1.6
        row.operator("cw.play", text="Pause" if playing else "Play", icon='PAUSE' if playing else 'PLAY')
        row.operator("cw.restart", text="", icon='FILE_REFRESH')
        row.operator("cw.stop", text="", icon='SNAP_FACE')
        L.prop(sc, "frame_current", text="Frame")
        sec = (sc.frame_current - 1) / sc.render.fps
        cur = [s for s in SEQUENCES if s[1] <= sc.frame_current][-1][0]
        L.label(text=f"{int(sec // 60)}:{sec % 60:04.1f}  -  {cur}", icon='TIME')
        L.prop(p, "speed", slider=True)
        col = L.column(align=True)
        col.label(text="Sequences:")
        for name, f in SEQUENCES:
            col.operator("cw.jump", text=name, icon='TRIA_RIGHT').frame = f
        L.separator()
        row = L.row(align=True)
        row.operator("cw.interactive", icon='SHADING_RENDERED')
        row.operator("cw.solid", icon='SHADING_SOLID')


class CW_PT_cameras(CW_PT_base, bpy.types.Panel):
    bl_label = "Cameras"
    bl_parent_id = "CW_PT_main"

    def draw(self, context):
        sc = context.scene
        p = sc.cw_director
        L = self.layout
        L.prop(p, "auto_cuts", icon='SEQUENCE')
        col = L.column(align=True)
        for c in shot_cameras():
            label = c.get("cw_label", c.name)
            icon = 'VIEW_CAMERA' if sc.camera == c else 'CAMERA_DATA'
            col.operator("cw.view_camera", text=f"{c.data.lens:.0f}mm  {label}", icon=icon).name = c.name
        L.operator("cw.explore", icon='ORIENTATION_GIMBAL')
        box = L.box()
        box.label(text="Mouse controls:", icon='MOUSE_MMB')
        box.label(text="Orbit: middle-mouse drag")
        box.label(text="Zoom: scroll wheel")
        box.label(text="Pan: Shift + middle-mouse")
        box.label(text="Select object: left-click")


class CW_PT_inspect(CW_PT_base, bpy.types.Panel):
    bl_label = "Inspect"
    bl_parent_id = "CW_PT_main"

    def draw(self, context):
        L = self.layout
        ob = context.active_object
        if not ob:
            L.label(text="Left-click any object to inspect it", icon='RESTRICT_SELECT_OFF')
            return
        L.label(text=ob.name.replace("_", " "), icon='OBJECT_DATA')
        info = find_info(ob)
        if info:
            col = L.column(align=True)
            words, line = info.split(), ""
            for w in words:
                if len(line) + len(w) > 34:
                    col.label(text=line)
                    line = ""
                line += w + " "
            col.label(text=line)
        if ob.active_material:
            L.label(text=f"Material: {ob.active_material.name}", icon='MATERIAL')
        row = L.row(align=True)
        row.operator("cw.focus", icon='ZOOM_SELECTED')
        row.operator("cw.rack_focus", icon='CAMERA_STEREO')


class CW_PT_quality(CW_PT_base, bpy.types.Panel):
    bl_label = "Quality & Render"
    bl_parent_id = "CW_PT_main"

    def draw(self, context):
        p = context.scene.cw_director
        L = self.layout
        L.prop(p, "engine", expand=True)
        L.prop(p, "quality", expand=True)
        L.label(text=DESCRIPTIONS.get(p.quality, ""), icon='INFO')
        r = context.scene.render
        L.label(text=f"{r.resolution_x} x {r.resolution_y} @ {r.resolution_percentage}%")
        L.prop(r, "resolution_percentage", text="Preview scale")
        row = L.row(align=True)
        row.scale_y = 1.3
        op = row.operator("cw.render", text="Render image", icon='RENDER_STILL')
        op.animation = False
        op = row.operator("cw.render", text="Render film", icon='RENDER_ANIMATION')
        op.animation = True
        L.label(text="Long renders: use the RENDER_*.bat files", icon='QUESTION')


class CW_PT_atmos(CW_PT_base, bpy.types.Panel):
    bl_label = "Atmosphere"
    bl_parent_id = "CW_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        p = context.scene.cw_director
        L = self.layout
        L.prop(p, "fog", slider=True)
        L.prop(p, "dust")
        L.prop(p, "grade", slider=True)
        L.operator("cw.reset_look", icon='LOOP_BACK')


class CW_PT_audio(CW_PT_base, bpy.types.Panel):
    bl_label = "Audio"
    bl_parent_id = "CW_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        p = context.scene.cw_director
        L = self.layout
        L.prop(p, "mute", icon='MUTE_IPO_ON' if p.mute else 'PLAY_SOUND')
        col = L.column(align=True)
        col.active = not p.mute
        for k in ("vol_master", "vol_music", "vol_ambience", "vol_effects"):
            col.prop(p, k, slider=True)

# ------------------------------------------------------------------ loop handling

def _frame_handler(scene, depsgraph=None):
    p = getattr(scene, "cw_director", None)
    if p and not p.loop and scene.frame_current >= scene.frame_end:
        try:
            bpy.ops.screen.animation_cancel(restore_frame=False)
        except RuntimeError:
            pass


CLASSES = (CWDirectorProps, CW_OT_play, CW_OT_restart, CW_OT_stop, CW_OT_jump, CW_OT_view_camera, CW_OT_explore,
           CW_OT_interactive, CW_OT_solid, CW_OT_focus, CW_OT_rack_focus, CW_OT_render, CW_OT_reset_look,
           CW_PT_main, CW_PT_cameras, CW_PT_inspect, CW_PT_quality, CW_PT_atmos, CW_PT_audio)


def register():
    for c in CLASSES:
        try:
            bpy.utils.unregister_class(getattr(bpy.types, c.__name__))
        except (AttributeError, RuntimeError):
            pass
        bpy.utils.register_class(c)
    bpy.types.Scene.cw_director = PointerProperty(type=CWDirectorProps)
    for h in list(bpy.app.handlers.frame_change_post):
        if getattr(h, "__name__", "") == "_frame_handler":
            bpy.app.handlers.frame_change_post.remove(h)
    bpy.app.handlers.frame_change_post.append(_frame_handler)


def unregister():
    for h in list(bpy.app.handlers.frame_change_post):
        if getattr(h, "__name__", "") == "_frame_handler":
            bpy.app.handlers.frame_change_post.remove(h)
    del bpy.types.Scene.cw_director
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass


if __name__ == "__main__":
    register()
