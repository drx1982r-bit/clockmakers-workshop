"""
cw_lighting.py - physically based dusk lighting.

  Sun        low warm sun through the left windows (crisp mullion shadows + god-rays)
  Sky fill   soft cool area lights in the window openings (skylight)
  Candle     tiny warm point light on the bench (flickers)
  Pendant    warm spot under the green lamp shade (switches on at dusk)
  Orrery     warm point light inside the glass sun of the orrery
  Bounce     very soft fill so shadows never go fully black
"""
import math
import bpy
from mathutils import Vector
from cw_util import collection

SUN_DIR = (1.0, -0.42, -0.40)   # direction the sunlight travels (into the room)


def blackbody(k):
    """Approximate linear-RGB colour of a blackbody at temperature k (Kelvin)."""
    t = k / 100.0
    if t <= 66:
        r = 1.0
        g = max(0.0, min(1.0, (99.4708025861 * math.log(t) - 161.1195681661) / 255))
        b = 0.0 if t <= 19 else max(0.0, min(1.0, (138.5177312231 * math.log(t - 10) - 305.0447927307) / 255))
    else:
        r = max(0.0, min(1.0, 329.698727446 * ((t - 60) ** -0.1332047592) / 255))
        g = max(0.0, min(1.0, 288.1221695283 * ((t - 60) ** -0.0755148492) / 255))
        b = 1.0
    return tuple(c ** 2.2 for c in (r, g, b))


def _light(name, kind, col, loc, energy, color, **kw):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    for k, v in kw.items():
        setattr(ld, k, v)
    ob = bpy.data.objects.new(name, ld)
    col.objects.link(ob)
    ob.location = loc
    return ob


def build(R):
    col = collection("Lighting")
    L = {}
    d = Vector(SUN_DIR).normalized()
    sun = _light("Sun", 'SUN', col, (-6, 0, 4), 14.0, (1.0, 0.60, 0.33), angle=math.radians(0.7))
    sun.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    sun["cw_info"] = "Setting sun - low, warm and directional."
    L['sun'] = sun
    for k, cy in enumerate((-0.6, 1.5)):
        a = _light(f"SkyFill{k}", 'AREA', col, (-3.55, cy, 1.8), 18.0, (0.62, 0.70, 1.0),
                   shape='RECTANGLE', size=1.0, size_y=1.85, spread=math.radians(100))
        a.rotation_euler = (0, math.radians(90), 0)   # face +X (into the room)
        a.visible_diffuse = True
        a.visible_camera = False
        L[f'skyfill{k}'] = a
    cx, cy, cz = R['candle_pos']
    L['candle'] = _light("CandleLight", 'POINT', col, (cx, cy, cz), 1.6, blackbody(1850),
                         shadow_soft_size=0.006)
    lx, ly, lz = R['lamp_pos']
    sp = _light("PendantSpot", 'SPOT', col, (lx, ly, lz), 0.0, blackbody(2700), spot_size=math.radians(115),
                spot_blend=0.65, shadow_soft_size=0.03)
    L['pendant'] = sp
    L['pendant_glow'] = _light("PendantGlow", 'POINT', col, (lx, ly, lz + 0.03), 0.0, blackbody(2700),
                               shadow_soft_size=0.03)
    root = R['clock_root']
    L['orrery'] = _light("OrreryLight", 'POINT', col, (root.location.x, root.location.y, 2.41 + 0.30), 0.0,
                         (1.0, 0.5, 0.18), shadow_soft_size=0.05)
    L['orrery'].visible_camera = False
    b = _light("BounceFill", 'AREA', col, (2.2, -2.2, 2.4), 22.0, (1.0, 0.82, 0.66), shape='DISK', size=2.5)
    b.rotation_euler = Vector((-1.0, 1.0, -0.6)).to_track_quat('-Z', 'Y').to_euler()
    b.visible_glossy = False
    b.visible_camera = False
    L['bounce'] = b
    # clock dial accent - a gentle grazing light so the dial reads in the dark hood
    acc = _light("DialAccent", 'AREA', col, (0.6, 1.0, 2.75), 11.0, blackbody(3000), shape='DISK', size=0.6)
    acc.rotation_euler = Vector((0.0, 1.0, -0.75)).to_track_quat('-Z', 'Y').to_euler()
    acc.visible_camera = False
    acc.visible_glossy = True
    L['accent'] = acc
    # warm bounce on the clock trunk (as if from the sunlit floor) - lights the pendulum
    tr = _light("TrunkBounce", 'AREA', col, (0.2, 1.55, 0.55), 10.0, blackbody(2600), shape='DISK', size=0.6)
    tr.rotation_euler = Vector((0.35, 1.0, 0.12)).to_track_quat('-Z', 'Y').to_euler()
    tr.visible_camera = False
    tr.visible_glossy = False          # Cycles: no mirror highlight from this fill
    tr.data.specular_factor = 0.0      # EEVEE: same
    L['trunk'] = tr
    # world: deep dusk ambience (mostly seen as soft fill from the windows)
    w = bpy.data.worlds.get("Dusk") or bpy.data.worlds.new("Dusk")
    bpy.context.scene.world = w
    nt = w.node_tree
    bg = nt.nodes.get("Background") or nt.nodes.new("ShaderNodeBackground")
    bg.inputs['Color'].default_value = (0.05, 0.045, 0.06, 1)
    bg.inputs['Strength'].default_value = 0.6
    out = nt.nodes.get("World Output") or nt.nodes.new("ShaderNodeOutputWorld")
    if not bg.outputs[0].links:
        nt.links.new(bg.outputs[0], out.inputs['Surface'])
    return L
