"""
cw_animation.py - the 60-second film: animation, cinematic cameras and timeline events.

Story (24 fps, 1440 frames):
  1  Dusk         (1-288)     wide establishing shots, god-rays, drifting dust
  2  The Bench    (289-576)   tracking along the workbench, macro of a ticking balance wheel
  3  Awakening    (577-912)   the key winds itself, the train starts ticking, pendulum swings
  4  The Heavens  (913-1200)  the orrery comes alive, the pendant lamp flickers on
  5  The Hour     (1201-1440) hands reach XII, the bell strikes, the camera pulls back, fade out

All event timings live in timeline_events() so the audio and the browser
version stay perfectly in sync with the Blender animation.
"""
import math
import os
import bpy
from mathutils import Vector
from cw_util import (collection, empty, key, keys, fcurve, finish_fcurves, ease_io, smoothstep, TAU)

FPS = 24
FRAME_END = 1440
SEQUENCES = [("Dusk", 1), ("The Bench", 289), ("Awakening", 577), ("The Heavens", 913), ("The Hour", 1201)]
KEY_START, KEY_END = 600, 690          # key turns (three turns)
TICK_START = 700                       # clock starts ticking
BEAT = 12                              # frames per beat (2 beats per second)
ORRERY_START = 780
SUN_GLOW = (880, 960)
LAMP_ON = 1000
HANDS_ARRIVE = 1296
CHIMES = [1300, 1328, 1356, 1384]
FADE_IN = (1, 48)
FADE_OUT = (1392, 1440)


def timeline_events():
    """Pure-python event list (used by the audio generator and the web viewer)."""
    beats = []
    f = TICK_START
    k = 0
    while f <= FRAME_END:
        beats.append(f)
        # first few beats are slower - the clock 'catching' its rhythm
        gap = BEAT + max(0, 6 - k) * 2
        f += gap
        k += 1
    key_clicks = []
    for t in range(3):
        a = KEY_START + t * 30
        key_clicks += [a + i * 4 for i in range(7)]
    balance = list(range(1, FRAME_END + 1, 12))
    wall = list(range(1, FRAME_END + 1, 24))
    return dict(fps=FPS, frame_end=FRAME_END, sequences=SEQUENCES, beats=beats, key_clicks=key_clicks,
                key_turns=(KEY_START, KEY_END), tick_start=TICK_START, orrery_start=ORRERY_START,
                sun_glow=SUN_GLOW, lamp_on=LAMP_ON, chimes=CHIMES, balance_ticks=balance,
                wall_ticks=wall, hands_arrive=HANDS_ARRIVE, fade_in=FADE_IN, fade_out=FADE_OUT)


EV = timeline_events()

# ------------------------------------------------------------------ helpers

def noise_mod(fc, strength, scale, phase=0.0):
    m = fc.modifiers.new('NOISE')
    m.strength = strength
    m.scale = scale
    m.phase = phase
    m.blend_type = 'ADD'
    return m


def node_input_path(node, socket_name):
    idx = [i for i, s in enumerate(node.inputs) if s.name == socket_name][0]
    return f'nodes["{node.name}"].inputs[{idx}].default_value'


def escape_angle_keys():
    """Escape wheel angle: holds, then quick steps on every beat (ticking motion)."""
    pts = [(1, 0.0), (TICK_START - 1, 0.0)]
    step = TAU / 60.0           # half a tooth of a 30-tooth escape wheel per beat
    e = 0.0
    for b in EV['beats']:
        pts.append((b, e))
        e += step
        pts.append((b + 3, e))
    return pts

# ------------------------------------------------------------------ clock

def animate_clock(R, L, M):
    from cw_models import GEARS
    # ratio of the escape wheel relative to the great wheel
    esc = [g for g in GEARS if g[0].name == "Clock_EscapeWheel"][0]
    r_esc = esc[1]
    pts = escape_angle_keys()
    for ob, ratio, phase in GEARS:
        k = ratio / r_esc
        vals = [(f, -(k * e + phase)) for (f, e) in pts]
        keys(ob, "rotation_euler", 1, vals)
    # pendulum + anchor: amplitude builds after the first beat
    pend, anc = R['pendulum'], R['anchor']
    pk, ak = [(1, 0.0), (TICK_START - 6, 0.0)], [(1, 0.0), (TICK_START - 6, 0.0)]
    sign = 1
    for i, b in enumerate(EV['beats']):
        amp = math.radians(4.2) * smoothstep(i / 8.0)
        pk.append((b, sign * amp))
        ak.append((b, sign * amp * 2.2))
        sign = -sign
    keys(pend, "rotation_euler", 1, pk)
    keys(anc, "rotation_euler", 1, ak)
    # winding key: three eased turns with a pause between each
    kv = [(KEY_START - 1, 0.0)]
    for t in range(3):
        a = KEY_START + t * 30
        kv += [(a, -t * TAU), (a + 25, -(t + 1) * TAU)]
    kv.append((KEY_END + 5, -3 * TAU))
    keys(R['key'], "rotation_euler", 1, kv)
    # weights rise a little with each turn, then descend imperceptibly
    for i in (0, 1):
        wt = R[f'weight{i}']
        z0 = wt.location.z
        wv = [(KEY_START - 1, z0)]
        for t in range(3):
            a = KEY_START + t * 30
            wv += [(a, z0 + t * 0.035), (a + 25, z0 + (t + 1) * 0.035)]
        wv += [(TICK_START, z0 + 0.105), (FRAME_END, z0 + 0.09)]
        keys(wt, "location", 2, wv)
    # hands: 11:52 -> 12:00 exactly as the bell strikes
    mins = [(1, 52.0), (TICK_START, 52.0), (HANDS_ARRIVE, 60.0), (FRAME_END, 60.6)]
    keys(R['minute_hand'], "rotation_euler", 1, [(f, TAU * m / 60.0) for f, m in mins])
    keys(R['hour_hand'], "rotation_euler", 1, [(f, TAU * (11 + m / 60.0) / 12.0) for f, m in mins])
    # bell hammer: anticipation, strike, recoil
    hv = [(1, 0.55)]
    for c in CHIMES:
        hv += [(c - 7, 0.55), (c - 3, 0.30), (c, 0.98), (c + 5, 0.50), (c + 9, 0.57)]
    keys(R['hammer'], "rotation_euler", 1, hv)


def animate_orrery(R, L, M):
    def integ(speed, f):
        # integral of an eased-in speed profile starting at ORRERY_START
        ramp = 120.0
        if f <= ORRERY_START:
            return 0.0
        t = f - ORRERY_START
        if t < ramp:
            return speed * (t ** 3 / (3 * ramp ** 2) if False else (t * t) / (2 * ramp))
        return speed * (ramp / 2 + (t - ramp))
    base = 0.010
    frames = list(range(ORRERY_START - 1, FRAME_END + 1, 8)) + [FRAME_END]
    for piv, sp in R['planets']:
        z0 = piv.rotation_euler.z
        keys(piv, "rotation_euler", 2, [(f, z0 + integ(base * sp, f)) for f in frames], handle='AUTO')
    keys(R['moon'], "rotation_euler", 2, [(f, integ(0.06, f)) for f in frames], handle='AUTO')
    keys(R['armillary0'], "rotation_euler", 2, [(f, integ(0.004, f)) for f in frames], handle='AUTO')
    keys(R['armillary1'], "rotation_euler", 2, [(f, -integ(0.006, f)) for f in frames], handle='AUTO')
    keys(R['orrery_crown'], "rotation_euler", 2, [(f, integ(0.012, f)) for f in frames], handle='AUTO')
    # the glass sun ignites
    sunmat = M['OrrerySun']
    node = sunmat.node_tree.nodes['SunEmit']
    p = node_input_path(node, 'Emission Strength')
    keys(sunmat.node_tree, p, 0, [(SUN_GLOW[0], 0.0), (SUN_GLOW[0] + 20, 1.5), (SUN_GLOW[0] + 26, 0.8),
                                  (SUN_GLOW[1], 7.0)])
    keys(L['orrery'].data, "energy", 0, [(SUN_GLOW[0], 0.0), (SUN_GLOW[0] + 20, 3.0), (SUN_GLOW[0] + 26, 1.5),
                                         (SUN_GLOW[1], 14.0)])


def animate_workbench(R, L, M):
    # balance wheel oscillation (+/- 150 deg, 1 Hz) and movement gears stepping
    bal = R['balance']
    pts = []
    sign = 1
    for f in EV['balance_ticks']:
        pts.append((f, sign * math.radians(150)))
        sign = -sign
    keys(bal, "rotation_euler", 2, pts)
    for i, g in enumerate(R['movement_gears']):
        ratio = (1, -1.33, 1.6)[i]
        v = []
        a = 0.0
        for f in EV['balance_ticks']:
            v += [(f, a), (f + 2, a + 0.06 * ratio)]
            a += 0.06 * ratio
        keys(g, "rotation_euler", 1, [(f, -x) for f, x in v])
    # wall clocks: second hands tick once per second
    for sh, k in R['wall_seconds']:
        a0 = TAU * (k * 0.31)
        fc = keys(sh, "rotation_euler", 1, [(f, a0 + TAU * i / 60.0) for i, f in enumerate(EV['wall_ticks'])],
                  interp='CONSTANT')
    # candle: flicker (light energy + flame shape), with noise modifiers
    cl = L['candle']
    fc = keys(cl.data, "energy", 0, [(1, 1.6), (FRAME_END, 1.6)])
    noise_mod(fc, 0.9, 2.5)
    flame = R['flame']
    for ax, (st, ph) in enumerate(((0.12, 1.0), (0.12, 7.0), (0.35, 3.0))):
        fc = keys(flame, "scale", ax, [(1, 1.0), (FRAME_END, 1.0)])
        noise_mod(fc, st, 3.0, ph)
    for ax, ph in ((0, 11.0), (1, 23.0)):
        fc = keys(flame, "rotation_euler", ax, [(1, 0.0), (FRAME_END, 0.0)])
        noise_mod(fc, 0.12, 6.0, ph)


def animate_light_story(sc, R, L, M):
    # the sun sinks: dimmer and redder through the film
    sun = L['sun']
    keys(sun.data, "energy", 0, [(1, 14.0), (600, 13.4), (1440, 8.0)])
    for i, (a, b) in enumerate(zip((1.0, 0.60, 0.33), (1.0, 0.40, 0.16))):
        keys(sun.data, "color", i, [(1, a), (600, a * 0.98 + b * 0.02), (1440, b)])
    for k in (0, 1):
        keys(L[f'skyfill{k}'].data, "energy", 0, [(1, 18.0), (1440, 11.0)])
    skym = M['DuskSky']
    node = skym.node_tree.nodes['SkyEmission']
    keys(skym.node_tree, node_input_path(node, 'Strength'), 0, [(1, 1.3), (1440, 0.8)])
    # pendant lamp switches on with a flicker
    bulbm = M['BulbFilament']
    bnode = bulbm.node_tree.nodes['BulbEmit']
    bp = node_input_path(bnode, 'Strength')
    seq = [(1, 0.0), (LAMP_ON - 1, 0.0), (LAMP_ON, 1.0), (LAMP_ON + 2, 0.0), (LAMP_ON + 5, 0.7),
           (LAMP_ON + 7, 0.15), (LAMP_ON + 11, 1.0)]
    keys(bulbm.node_tree, bp, 0, [(f, v * 45.0) for f, v in seq], interp='CONSTANT')
    keys(L['pendant'].data, "energy", 0, [(f, v * 45.0) for f, v in seq], interp='CONSTANT')
    keys(L['pendant_glow'].data, "energy", 0, [(f, v * 6.0) for f, v in seq], interp='CONSTANT')
    # fade in / fade out
    keys(sc, "view_settings.exposure", 0, [(FADE_IN[0], -7.0), (FADE_IN[1], 0.0), (FADE_OUT[0], 0.0),
                                          (FADE_OUT[1], -9.0)])

# ------------------------------------------------------------------ cameras

SHOTS = [
    # name, start, end, lens(s), fstop, cam keys, target keys, focus keys, shake
    dict(name="Cam_Establish", start=1, end=150, lens=(20, 20), fstop=5.6,
         cam=[(1, (2.95, -2.75, 1.2)), (150, (2.35, -2.05, 1.42))],
         tgt=[(1, (-0.9, 1.2, 1.25)), (150, (-0.7, 1.35, 1.38))],
         foc=[(1, (-0.6, 0.6, 1.0))], shake=0.004,
         label="Wide - establishing shot", kind="Wide"),
    dict(name="Cam_Beams", start=151, end=288, lens=(32, 32), fstop=2.0,
         cam=[(151, (-0.95, -2.05, 1.5)), (288, (-0.1, -1.85, 1.62))],
         tgt=[(151, (-2.6, 0.9, 1.55)), (288, (-2.1, 1.35, 1.5))],
         foc=[(151, (-1.75, -0.4, 1.55)), (288, (-1.4, 0.2, 1.5))], shake=0.004,
         label="Tracking - through the light beams", kind="Tracking"),
    dict(name="Cam_Bench", start=289, end=430, lens=(40, 40), fstop=4.0,
         cam=[(289, (-1.3, -0.2, 1.3)), (430, (-0.5, -0.17, 1.27))],
         tgt=[(289, (-1.08, 0.32, 0.97)), (430, (-0.4, 0.38, 1.0))],
         foc=[(289, (-1.08, 0.32, 0.97)), (360, (-0.7, 0.3, 0.98)), (430, (-0.4, 0.4, 1.02))], shake=0.002,
         label="Tracking - along the workbench (focus pull)", kind="Tracking"),
    dict(name="Cam_Macro", start=431, end=576, lens=(100, 100), fstop=4.0,
         cam=[(431, (-0.27, 0.16, 1.235)), (576, (-0.305, 0.215, 1.205))],
         tgt=[(431, (-0.38, 0.42, 1.125)), (576, (-0.38, 0.42, 1.128))],
         foc=[(431, (-0.38, 0.42, 1.13))], shake=0.0006,
         label="Extreme close-up - balance wheel", kind="Extreme close-up"),
    dict(name="Cam_Dial", start=577, end=700, lens=(85, 85), fstop=4.0,
         cam=[(577, (0.98, 1.32, 1.74)), (700, (0.86, 1.42, 1.79))],
         tgt=[(577, (0.73, 2.28, 1.72)), (700, (0.66, 2.3, 1.79))],
         foc=[(577, (0.725, 2.28, 1.72))], shake=0.0015,
         label="Close-up - the key winds itself", kind="Close-up"),
    dict(name="Cam_Gears", start=701, end=820, lens=(100, 100), fstop=5.6,
         cam=[(701, (0.56, 1.97, 1.85)), (820, (0.63, 1.98, 1.83))],
         tgt=[(701, (0.68, 2.35, 1.775)), (820, (0.70, 2.35, 1.78))],
         foc=[(701, (0.69, 2.345, 1.779))], shake=0.0008,
         label="Extreme close-up - the gear train starts", kind="Extreme close-up"),
    dict(name="Cam_Pendulum", start=821, end=912, lens=(50, 50), fstop=2.8,
         cam=[(821, (0.2, 1.72, 0.72)), (912, (0.3, 1.78, 0.76))],
         tgt=[(821, (0.6, 2.55, 0.66)), (912, (0.6, 2.55, 0.7))],
         foc=[(821, (0.6, 2.58, 0.6))], shake=0.002,
         label="Low angle - the pendulum", kind="Dynamic angle"),
    dict(name="Cam_Orbit", start=913, end=1200, lens=(35, 35), fstop=4.0, orbit=dict(
         centre=(0.6, 2.55, 2.68), radius=(0.95, 0.85), angle=(-68, 62), height=(0.34, 0.08)),
         foc=[(913, (0.6, 2.55, 2.71))], shake=0.002,
         label="Orbit - the orrery comes alive", kind="Orbit"),
    dict(name="Cam_Hands", start=1201, end=1300, lens=(70, 70), fstop=3.5,
         cam=[(1201, (0.33, 1.52, 1.97)), (1300, (0.42, 1.62, 1.9))],
         tgt=[(1201, (0.6, 2.3, 1.98)), (1300, (0.6, 2.3, 1.92))],
         foc=[(1201, (0.6, 2.25, 2.0)), (1290, (0.6, 2.25, 2.1))], shake=0.0015,
         label="Close-up - the hands reach twelve", kind="Close-up"),
    dict(name="Cam_Finale", start=1301, end=1440, lens=(40, 24), fstop=4.0,
         cam=[(1301, (0.6, 1.25, 1.95)), (1440, (1.95, -2.55, 1.95))],
         tgt=[(1301, (0.6, 2.3, 1.95)), (1440, (-0.3, 1.25, 1.35))],
         foc=[(1301, (0.6, 2.3, 1.9)), (1440, (0.0, 1.5, 1.3))], shake=0.003,
         label="Pull-back - the whole workshop", kind="Wide"),
]


def make_camera(sc, col, s):
    cd = bpy.data.cameras.new(s['name'])
    cd.lens = s['lens'][0]
    cd.sensor_width = 36.0
    cd.sensor_fit = 'HORIZONTAL'
    cd.clip_start = 0.01
    cd.clip_end = 60.0
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = s['fstop']
    cd.dof.aperture_blades = 7
    cd.dof.aperture_rotation = math.radians(12)
    cam = bpy.data.objects.new(s['name'], cd)
    col.objects.link(cam)
    cam["cw_label"] = s['label']
    cam["cw_kind"] = s['kind']
    cam["cw_start"] = s['start']
    cam["cw_end"] = s['end']
    tgt = empty(s['name'] + "_Target", col, size=0.05)
    foc = empty(s['name'] + "_Focus", col, size=0.03)
    if 'orbit' in s:
        o = s['orbit']
        c = Vector(o['centre'])
        frames = list(range(s['start'], s['end'] + 1, 6))
        if frames[-1] != s['end']:
            frames.append(s['end'])
        pts = []
        for f in frames:
            t = ease_io((f - s['start']) / (s['end'] - s['start']))
            a = math.radians(o['angle'][0] + (o['angle'][1] - o['angle'][0]) * t)
            r = o['radius'][0] + (o['radius'][1] - o['radius'][0]) * t
            h = o['height'][0] + (o['height'][1] - o['height'][0]) * t
            pts.append((f, c + Vector((r * math.sin(a), -r * math.cos(a), h))))
        for ax in range(3):
            keys(cam, "location", ax, [(f, p[ax]) for f, p in pts], handle='AUTO')
            keys(tgt, "location", ax, [(s['start'], c[ax]), (s['end'], c[ax] + (0.02 if ax == 2 else 0))])
    else:
        for ax in range(3):
            keys(cam, "location", ax, [(f, p[ax]) for f, p in s['cam']])
            keys(tgt, "location", ax, [(f, p[ax]) for f, p in s['tgt']])
    for ax in range(3):
        fc = keys(foc, "location", ax, [(f, p[ax]) for f, p in s['foc']])
    # subtle hand-held float (organic, never robotic)
    if s.get('shake'):
        for ax in range(3):
            fc = fcurve(tgt, "location", ax)
            noise_mod(fc, s['shake'] * 2.0, 55.0 + ax * 9, phase=ax * 13.0 + s['start'] * 0.1)
    if s['lens'][0] != s['lens'][1]:
        keys(cd, "lens", 0, [(s['start'], s['lens'][0]), (s['end'], s['lens'][1])])
    con = cam.constraints.new('TRACK_TO')
    con.target = tgt
    con.track_axis = 'TRACK_NEGATIVE_Z'
    con.up_axis = 'UP_Y'
    cd.dof.focus_object = foc
    m = sc.timeline_markers.new(s['name'].replace("Cam_", ""), frame=s['start'])
    m.camera = cam
    return cam


def build(sc, R, L, M):
    animate_clock(R, L, M)
    animate_orrery(R, L, M)
    animate_workbench(R, L, M)
    animate_light_story(sc, R, L, M)
    col = collection("Cameras")
    cams = [make_camera(sc, col, s) for s in SHOTS]
    # a free 'explore' camera for interactive use (not part of the film edit)
    cd = bpy.data.cameras.new("Cam_Explore")
    cd.lens = 28
    cd.dof.use_dof = False
    ce = bpy.data.objects.new("Cam_Explore", cd)
    col.objects.link(ce)
    ce.location = (2.6, -2.4, 1.6)
    ce.rotation_euler = (math.radians(82), 0, math.radians(42))
    ce["cw_label"] = "Free camera - explore the workshop"
    ce["cw_kind"] = "Free"
    sc.camera = cams[0]
    for idb in list(bpy.data.objects) + list(bpy.data.lights) + list(bpy.data.materials) + list(bpy.data.cameras):
        if getattr(idb, 'animation_data', None):
            finish_fcurves(idb)
    sc["cw_sequences"] = [s[0] for s in SEQUENCES]
    sc["cw_sequence_frames"] = [s[1] for s in SEQUENCES]
    return cams

# ------------------------------------------------------------------ audio in the timeline

AUDIO_STRIPS = [  # file, channel, start frame, default volume, group
    ("music.wav", 1, 1, 0.55, 'music'),
    ("ambience.wav", 2, 1, 0.7, 'ambience'),
    ("sfx.wav", 3, 1, 0.9, 'effects'),
]


def add_audio(sc, audio_dir):
    se = sc.sequence_editor or sc.sequence_editor_create()
    strips = se.strips if hasattr(se, 'strips') else se.sequences
    for f, ch, start, vol, grp in AUDIO_STRIPS:
        p = os.path.join(audio_dir, f)
        if not os.path.exists(p):
            continue
        st = strips.new_sound(f.split('.')[0], p, ch, start)
        st.volume = vol
        st["cw_group"] = grp
        st["cw_default_volume"] = vol
    sc["cw_vol_master"] = 1.0
    sc.render.ffmpeg.audio_codec = 'AAC'
    sc.render.ffmpeg.audio_bitrate = 256
