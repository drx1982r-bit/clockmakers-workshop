"""
cw_models.py - all geometry for "The Clockmaker's Workshop at Dusk".

World layout (metres, Z up):
    room interior   X -3.5..3.5   Y -3..3   Z 0..3.4
    windows         left wall (X=-3.5), centred at Y=-0.6 and Y=1.5
    grand clock     against back wall, root at (0.6, 2.55, 0), dial faces -Y
    workbench       centre-left, root at (-0.7, 0.55, 0)
Repeated objects share mesh data (linked duplicates) to save memory.
"""
import math
import random
import bmesh
import bpy
from mathutils import Vector, Matrix
from cw_util import (collection, obj_from_mesh, empty, bevel, box, box_mesh, cylinder,
                     cylinder_mesh, sphere, sphere_mesh, torus, torus_mesh, lathe, lathe_mesh,
                     extrude_shape_mesh, ring_mesh, panel_with_hole_mesh, gear_mesh, text_mesh,
                     TAU)

ROT_FRONT = Matrix.Rotation(math.pi / 2, 4, 'X')   # XY-built mesh -> faces -Y (front)

R = {}            # registry of objects needed by animation / cameras
GEARS = []        # (object, ratio, phase) for the clock train


def _front(me):
    """Re-orient a mesh built in XY (extruded +Z) so it lies in XZ facing -Y."""
    me.transform(ROT_FRONT)
    return me

# ============================================================== ARCHITECTURE

def build_room(M):
    col = collection("Architecture")
    W0, W1, D0, D1, H = -3.5, 3.5, -3.0, 3.0, 3.4
    T = 0.25
    floor = box("Floor", col, (7.0, 6.0, 0.1), (0, 0, -0.05), M['FloorPlanks'], bev=0,
                info="Oak floorboards - worn paths, gaps and old varnish, all procedural.")
    box("Ceiling", col, (7.6, 6.6, 0.1), (0, 0, H + 0.05), M['Plaster'], bev=0)
    box("BackWall", col, (7.6, T, H), (0, D1 + T / 2, H / 2), M['Plaster'], bev=0)
    box("FrontWall", col, (7.6, T, H), (0, D0 - T / 2, H / 2), M['Plaster'], bev=0)
    box("RightWall", col, (T, 6.0, H), (W1 + T / 2, 0, H / 2), M['Plaster'], bev=0)
    # left wall with two window openings
    wins = [(-0.6, 1.1), (1.5, 1.1)]
    sill, top = 0.85, 2.75
    x = W0 - T / 2
    ys = [D0]
    for (cy, w) in wins:
        ys += [cy - w / 2, cy + w / 2]
    ys.append(D1)
    for i in range(0, len(ys), 2):
        a, b = ys[i], ys[i + 1]
        box(f"LeftWall_{i}", col, (T, b - a, H), (x, (a + b) / 2, H / 2), M['Plaster'], bev=0)
    for k, (cy, w) in enumerate(wins):
        box(f"LeftWall_Below{k}", col, (T, w, sill), (x, cy, sill / 2), M['Plaster'], bev=0)
        box(f"LeftWall_Above{k}", col, (T, w, H - top), (x, cy, (H + top) / 2), M['Plaster'], bev=0)
        build_window(col, M, cy, w, sill, top, W0, T, k)
    # ceiling beams
    for i, bx in enumerate([-2.9, -1.45, 0.0, 1.45, 2.9]):
        box(f"Beam_{i}", col, (0.18, 6.0, 0.24), (bx, 0, H - 0.12), M['OldTimber'], bev=0.012,
            info="Old timber ceiling beam.")
    box("BeamCross", col, (7.0, 0.16, 0.16), (0, 1.0, H - 0.3), M['OldTimber'], bev=0.01)
    # wainscot panelling + skirting along walls
    wh = 0.95
    box("Wainscot_Back", col, (7.0, 0.03, wh), (0, D1 - 0.015, wh / 2), M['PaintGreen'], bev=0.003)
    box("Wainscot_Right", col, (0.03, 6.0, wh), (W1 - 0.015, 0, wh / 2), M['PaintGreen'], bev=0.003)
    box("Wainscot_Front", col, (7.0, 0.03, wh), (0, D0 + 0.015, wh / 2), M['PaintGreen'], bev=0.003)
    box("Wainscot_Left", col, (0.03, 6.0, sill - 0.05), (W0 + 0.015, 0, (sill - 0.05) / 2),
        M['PaintGreen'], bev=0.003)
    # panel moulding strips (vertical stiles) for depth
    for i in range(15):
        y = D0 + 0.2 + i * 0.4
        box(f"Stile_R{i}", col, (0.02, 0.04, wh - 0.1), (W1 - 0.04, y, wh / 2), M['PaintGreen'], bev=0.004)
        bx = W0 + 0.2 + i * 0.47
        box(f"Stile_B{i}", col, (0.04, 0.02, wh - 0.1), (bx, D1 - 0.04, wh / 2), M['PaintGreen'], bev=0.004)
    box("CapRail_Back", col, (7.0, 0.06, 0.04), (0, D1 - 0.03, wh), M['Oak'], bev=0.006)
    box("CapRail_Right", col, (0.06, 6.0, 0.04), (W1 - 0.03, 0, wh), M['Oak'], bev=0.006)
    box("Skirt_Back", col, (7.0, 0.05, 0.12), (0, D1 - 0.045, 0.06), M['OldTimber'], bev=0.005)
    box("Skirt_Right", col, (0.05, 6.0, 0.12), (W1 - 0.045, 0, 0.06), M['OldTimber'], bev=0.005)
    box("Skirt_Left", col, (0.05, 6.0, 0.12), (W0 + 0.045, 0, 0.06), M['OldTimber'], bev=0.005)
    box("Rug", col, (2.8, 1.9, 0.012), (-0.65, 0.35, 0.006), M['Rug'], bev=0.004,
        info="Hand-knotted wool rug (procedural medallion pattern with sheen).")


def build_window(col, M, cy, w, sill, top, W0, T, k):
    x_in = W0
    h = top - sill
    fw = 0.06
    # frame
    box(f"WinFrameL{k}", col, (0.12, fw, h), (x_in - 0.08, cy - w / 2 + fw / 2, sill + h / 2), M['PaintCream'])
    box(f"WinFrameR{k}", col, (0.12, fw, h), (x_in - 0.08, cy + w / 2 - fw / 2, sill + h / 2), M['PaintCream'])
    box(f"WinFrameT{k}", col, (0.12, w, fw), (x_in - 0.08, cy, top - fw / 2), M['PaintCream'])
    box(f"WinSill{k}", col, (0.34, w + 0.16, 0.05), (x_in - 0.05, cy, sill - 0.025), M['PaintCream'],
        info="Window sill, paint chipped by decades of sunlight.")
    # mullions: 2 vertical, 3 horizontal
    for i in range(1, 3):
        yy = cy - w / 2 + w * i / 3
        box(f"WinMullV{k}_{i}", col, (0.05, 0.025, h), (x_in - 0.12, yy, sill + h / 2), M['PaintCream'], bev=0.003)
    for i in range(1, 4):
        zz = sill + h * i / 4
        box(f"WinMullH{k}_{i}", col, (0.05, w, 0.025), (x_in - 0.12, cy, zz), M['PaintCream'], bev=0.003)
    box(f"WinGlass{k}", col, (0.006, w - 0.02, h - 0.02), (x_in - 0.125, cy, sill + h / 2),
        M['WindowGlass'], bev=0, info="Old window glass with dust and smudges (rough transmission).")


def build_exterior(M, sun_dir):
    col = collection("Exterior")
    # painted dusk sky - large emissive backdrop far outside the windows
    sky = box("DuskSky", col, (0.1, 60.0, 30.0), (-22.0, 0.0, 6.0), M['DuskSky'], bev=0,
              info="Dusk sky backdrop seen through the windows.")
    # sun disc on the backdrop in the direction the sunlight comes from
    p = Vector((0, 0.5, 1.5))
    d = Vector(sun_dir).normalized()
    t = (p.x - (-21.9)) / d.x
    sp = p - d * t
    sun = cylinder("SunDisc", col, 0.9, 0.05, (-21.9, sp.y, sp.z), M['SunDiscGlow'], seg=48,
                   rot=(0, math.pi / 2, 0), bev=0)
    rnd = random.Random(3)
    # neighbouring rooftops (silhouettes with lit windows)
    for i in range(14):
        y = -14 + i * 2.2 + rnd.uniform(-0.4, 0.4)
        xd = -9 - rnd.uniform(0, 5)
        h = rnd.uniform(4.0, 7.5)
        w = rnd.uniform(1.6, 2.4)
        box(f"House_{i}", col, (2.0, w, h), (xd, y, -4 + h / 2), M['RooftopSilhouette'], bev=0)
        roof = extrude_shape_mesh(f"Roof_{i}", [(-1.1, 0), (1.1, 0), (0, rnd.uniform(0.8, 1.5))], w)
        ob = obj_from_mesh(f"Roof_{i}", roof, col, loc=(xd, y - w / 2, -4 + h),
                           rot=(-math.pi / 2, 0, 0), mat=M['RooftopSilhouette'], smooth=False)
        if rnd.random() < 0.6:
            box(f"Chimney_{i}", col, (0.35, 0.35, 1.0), (xd + rnd.uniform(-0.5, 0.5), y, -4 + h + 0.9),
                M['RooftopSilhouette'], bev=0)

# ============================================================== THE GRAND CLOCK

def _gear_obj(name, col, M, teeth, module, thick, cx, cz, y, parent, spokes=5, style='spur', mat=None):
    me = _front(gear_mesh(name, teeth, module, thick, spokes=spokes, style=style))
    ob = obj_from_mesh(name, me, col, loc=(cx, y, cz), mat=mat or M['BrassGear'], parent=parent,
                       info=f"Brass {'escape wheel' if style == 'escape' else 'wheel'}, {teeth} teeth.")
    bevel(ob, module * 0.12, 2, angle=40)
    return ob


def build_clock(M):
    col = collection("GrandClock")
    root = empty("Clock_Root", col, (0.6, 2.55, 0.0), size=0.3)
    R['clock_root'] = root
    W = M['Walnut']; WH = M['WalnutH']
    info_case = "Long-case astronomical clock - French-polished walnut case."
    # --- plinth & trunk
    box("Clock_Plinth", col, (1.0, 0.56, 0.22), (0, 0, 0.11), WH, bev=0.008, parent=root, info=info_case)
    box("Clock_PlinthMould", col, (1.05, 0.6, 0.04), (0, 0, 0.24), WH, bev=0.012, parent=root)
    box("Clock_TrunkL", col, (0.05, 0.44, 1.04), (-0.365, 0, 0.78), W, bev=0.006, parent=root, info=info_case)
    box("Clock_TrunkR", col, (0.05, 0.44, 1.04), (0.365, 0, 0.78), W, bev=0.006, parent=root, info=info_case)
    box("Clock_TrunkBack", col, (0.78, 0.03, 1.04), (0, 0.205, 0.78), W, bev=0.004, parent=root)
    box("Clock_Velvet", col, (0.68, 0.01, 0.98), (0, 0.185, 0.78), M['Velvet'], bev=0, parent=root,
        info="Burgundy velvet backing - makes the brass pendulum glow.")
    box("Clock_TrunkBottom", col, (0.78, 0.44, 0.03), (0, 0, 0.275), W, bev=0.003, parent=root)
    box("Clock_TrunkTop", col, (0.78, 0.44, 0.03), (0, 0, 1.285), W, bev=0.003, parent=root)
    # door frame (front, y = -0.21)
    yf = -0.215
    box("Clock_DoorStileL", col, (0.09, 0.035, 1.0), (-0.3, yf, 0.78), W, bev=0.006, parent=root)
    box("Clock_DoorStileR", col, (0.09, 0.035, 1.0), (0.3, yf, 0.78), W, bev=0.006, parent=root)
    box("Clock_DoorRailT", col, (0.6, 0.035, 0.1), (0, yf, 1.23), WH, bev=0.006, parent=root)
    box("Clock_DoorRailB", col, (0.6, 0.035, 0.1), (0, yf, 0.33), WH, bev=0.006, parent=root)
    box("Clock_DoorGlass", col, (0.52, 0.005, 0.81), (0, yf, 0.78), M['Glass'], bev=0, parent=root,
        info="Bevelled glass door - watch the pendulum through it.")
    esc = lathe("Clock_Keyhole", col, [(0.0, 0), (0.018, 0), (0.02, 0.004), (0.0, 0.006)], (0.3, yf - 0.018, 0.92),
                M['BrassPolished'], seg=32, rot=(math.pi / 2, 0, 0), parent=root)
    # waist mouldings
    box("Clock_Waist1", col, (0.88, 0.5, 0.05), (0, 0, 1.325), WH, bev=0.012, parent=root)
    box("Clock_Waist2", col, (0.95, 0.55, 0.04), (0, 0, 1.37), WH, bev=0.012, parent=root)
    # --- hood
    zc = 1.85   # dial centre height (local)
    box("Clock_HoodL", col, (0.05, 0.5, 0.92), (-0.475, 0, 1.85), W, bev=0.006, parent=root, info=info_case)
    box("Clock_HoodR", col, (0.05, 0.5, 0.92), (0.475, 0, 1.85), W, bev=0.006, parent=root, info=info_case)
    box("Clock_HoodBack", col, (0.95, 0.03, 0.92), (0, 0.235, 1.85), W, bev=0.004, parent=root)
    front = _front(panel_with_hole_mesh("Clock_HoodFront", 0.95, 0.92, 0.272, 0.03))
    fo = obj_from_mesh("Clock_HoodFront", front, col, loc=(0, -0.22, zc), mat=W, parent=root, info=info_case)
    bevel(fo, 0.004, 2)
    # columns with brass capitals
    for sx in (-1, 1):
        cylinder(f"Clock_Column{sx}", col, 0.024, 0.78, (sx * 0.445, -0.272, 1.85), W, seg=32, parent=root, bev=0)
        for zz, flip in ((1.45, 1), (2.25, -1)):
            prof = [(0.0, 0), (0.034, 0), (0.034, 0.012), (0.028, 0.02), (0.03, 0.03), (0.024, 0.04), (0, 0.04)]
            if flip < 0:
                prof = [(r, 0.04 - z) for (r, z) in reversed(prof)]
            lathe(f"Clock_Capital{sx}_{zz}", col, prof, (sx * 0.445, -0.272, zz - 0.02), M['BrassPolished'],
                  seg=32, parent=root)
    # cornice & orrery platform
    box("Clock_Cornice1", col, (1.02, 0.56, 0.04), (0, 0, 2.33), WH, bev=0.012, parent=root)
    box("Clock_Cornice2", col, (1.08, 0.6, 0.035), (0, 0, 2.367), WH, bev=0.012, parent=root)
    box("Clock_Cornice3", col, (0.98, 0.52, 0.025), (0, 0, 2.397), WH, bev=0.006, parent=root)
    for sx in (-1, 1):
        prof = [(0.0, 0), (0.035, 0), (0.035, 0.01), (0.02, 0.02), (0.038, 0.06), (0.03, 0.09), (0.012, 0.1),
                (0.016, 0.12), (0.004, 0.17), (0.0, 0.18)]
        lathe(f"Clock_Finial{sx}", col, prof, (sx * 0.46, -0.22, 2.41), M['BrassPolished'], seg=32, parent=root,
              info="Gilt brass finial.")
    # --- dial
    ring = _front(ring_mesh("Clock_ChapterRing", 0.362, 0.272, 0.004, seg=128))
    ro = obj_from_mesh("Clock_ChapterRing", ring, col, loc=(0, -0.236, zc), mat=M['Silver'], parent=root,
                       info="Silvered chapter ring with engraved Roman numerals.")
    torus("Clock_BezelOuter", col, 0.364, 0.007, (0, -0.242, zc), M['BrassPolished'], rot=(math.pi / 2, 0, 0),
          seg=128, ring=12, parent=root)
    torus("Clock_BezelInner", col, 0.272, 0.004, (0, -0.241, zc), M['BrassPolished'], rot=(math.pi / 2, 0, 0),
          seg=128, ring=10, parent=root)
    numerals = ["XII", "I", "II", "III", "IIII", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
    for i, n in enumerate(numerals):
        a = TAU * i / 12
        me = text_mesh(f"Numeral_{n}", n, 0.052, 0.0015)
        # rotate numeral so its base points to dial centre, then lay it into the XZ plane
        me.transform(Matrix.Rotation(-a, 4, 'Z'))
        _front(me)
        r = 0.317
        obj_from_mesh(f"Clock_Numeral_{i}", me, col, loc=(math.sin(a) * r, -0.2395, zc + math.cos(a) * r),
                      mat=M['PaintBlack'], parent=root, smooth=False)
    tick = box_mesh("TickMesh", 0.0025, 0.0012, 0.012)
    tick5 = box_mesh("Tick5Mesh", 0.004, 0.0012, 0.018)
    for i in range(60):
        a = TAU * i / 60
        r = 0.352 if i % 5 else 0.349
        obj_from_mesh(f"Clock_Tick_{i}", tick5 if i % 5 == 0 else tick, col,
                      loc=(math.sin(a) * r, -0.2395, zc + math.cos(a) * r), rot=(0, a, 0),
                      mat=M['PaintBlack'] if i == 0 else None, parent=root, smooth=False)
    for ob in col.objects:
        if ob.name.startswith("Clock_Tick") and not ob.data.materials:
            ob.data.materials.append(M['PaintBlack'])
    # brass spandrels in the four corners
    spandrel = [(0, 0), (0.12, 0), (0.1, 0.02), (0.06, 0.03), (0.035, 0.06), (0.02, 0.1), (0, 0.12)]
    for k, (sx, sz) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1))):
        me = extrude_shape_mesh(f"Spandrel{k}", [(x * sx, y * sz) for (x, y) in spandrel][::(1 if sx * sz > 0 else -1)], 0.006)
        _front(me)
        ob = obj_from_mesh(f"Clock_Spandrel{k}", me, col, loc=(sx * 0.46, -0.236, zc + sz * 0.445),
                           mat=M['BrassAged'], parent=root)
        bevel(ob, 0.002, 2)
    # glass over the dial
    lathe("Clock_DialGlass", col, [(0.0, 0.012), (0.2, 0.009), (0.33, 0.004), (0.36, 0.0)],
          (0, -0.244, zc), M['Glass'], seg=96, rot=(math.pi / 2, 0, 0), parent=root, close_bottom=False,
          info="Domed crystal over the dial.")
    # --- movement visible through the skeleton dial
    lathe("Clock_BackPlate", col, [(0.0, 0), (0.30, 0), (0.30, 0.006), (0.0, 0.006)], (0, -0.12, zc),
          M['PerlageBrass'], seg=96, rot=(math.pi / 2, 0, 0), parent=root,
          info="Back plate with hand-applied perlage (circular graining).")
    train = empty("Clock_Train", col, (0, 0, zc), parent=root)
    build_gear_train(col, M, train)
    # hands (pivot at dial centre)
    R['hour_hand'] = build_hand(col, M, "Clock_HourHand", 0.19, 0.022, (0, -0.258, zc), root, kind='hour')
    R['minute_hand'] = build_hand(col, M, "Clock_MinuteHand", 0.29, 0.016, (0, -0.262, zc), root, kind='minute')
    lathe("Clock_HandNut", col, [(0.0, 0), (0.012, 0), (0.012, 0.004), (0.006, 0.008), (0.0, 0.009)],
          (0, -0.266, zc), M['BrassPolished'], seg=32, rot=(math.pi / 2, 0, 0), parent=root)
    # winding key (turns by itself when the clock awakens)
    key = empty("Clock_KeyPivot", col, (0.125, -0.27, zc - 0.13), parent=root)
    cylinder("Clock_KeyShank", col, 0.0045, 0.05, (0, 0.012, 0), M['BrassPolished'], seg=24,
             rot=(math.pi / 2, 0, 0), parent=key, bev=0)
    bow = [(-0.035, 0.0), (-0.03, 0.025), (-0.012, 0.035), (0.012, 0.035), (0.03, 0.025), (0.035, 0.0),
           (0.008, -0.01), (-0.008, -0.01)]
    me = extrude_shape_mesh("KeyBow", bow, 0.004, holes=[(-0.016, 0.017, 0.007), (0.016, 0.017, 0.007)])
    me.transform(Matrix.Translation((0, 0.012, -0.002)))
    _front(me)
    kb = obj_from_mesh("Clock_KeyBow", me, col, loc=(0, -0.012, 0), mat=M['BrassPolished'], parent=key,
                       info="Winding key - it turns itself as the clock awakens.")
    bevel(kb, 0.001, 2)
    R['key'] = key
    # --- pendulum & weights
    pend = empty("Clock_PendulumPivot", col, (0, 0.04, 1.27), parent=root)
    cylinder("Clock_PendulumRod", col, 0.0035, 0.66, (0, 0, -0.33), M['Steel'], seg=16, parent=pend, bev=0)
    sphere("Clock_PendulumBob", col, 0.1, (0, 0, -0.68), M['BrassPolished'], scale=(1, 0.22, 1), parent=pend,
           info="Lenticular brass pendulum bob - one swing per second.")
    box("Clock_Suspension", col, (0.03, 0.004, 0.04), (0, 0, 0.0), M['SteelDark'], parent=pend, bev=0.001)
    R['pendulum'] = pend
    link_mesh = torus_mesh("ChainLink", 0.0065, 0.0016, seg=16, ring=8)
    link_mesh.transform(Matrix.Diagonal((0.65, 1.0, 1.0, 1.0)))
    for k, sx in enumerate((-0.2, 0.2)):
        wt = empty(f"Clock_Weight{k}", col, (sx, -0.06, 0.95), parent=root)
        lathe(f"Clock_WeightBody{k}", col, [(0.0, -0.13), (0.032, -0.13), (0.036, -0.12), (0.036, 0.08),
                                           (0.03, 0.09), (0.006, 0.1), (0.0, 0.1)],
              (0, 0, 0), M['BrassAged'], seg=48, parent=wt, info="Brass-cased driving weight.")
        torus(f"Clock_WeightHook{k}", col, 0.009, 0.0018, (0, 0, 0.11), M['Steel'], rot=(math.pi / 2, 0, 0),
              seg=16, ring=8, parent=wt)
        for i in range(48):
            obj_from_mesh(f"Clock_Chain{k}_{i}", link_mesh, col, loc=(0, 0, 0.12 + i * 0.0105),
                          rot=(math.pi / 2, 0, (math.pi / 2) * (i % 2)), mat=M['Steel'] if (k == 0 and i == 0) else None,
                          parent=wt)
        R[f'weight{k}'] = wt
    # --- bell & hammer on the hood top
    lathe("Clock_Bell", col, [(0.0, 0.07), (0.012, 0.07), (0.03, 0.062), (0.042, 0.04), (0.05, 0.012),
                              (0.058, 0.0), (0.054, 0.0), (0.046, 0.012), (0.038, 0.04), (0.026, 0.058),
                              (0.0, 0.064)], (0.3, 0.08, 2.43), M['BrassPolished'], seg=48, parent=root,
          close_top=False, close_bottom=False, info="Bronze hour bell.")
    cylinder("Clock_BellPost", col, 0.004, 0.08, (0.3, 0.08, 2.45), M['SteelDark'], seg=12, parent=root, bev=0)
    ham = empty("Clock_HammerPivot", col, (0.17, 0.08, 2.43), parent=root)
    cylinder("Clock_HammerArm", col, 0.0028, 0.075, (0.0, 0, 0.037), M['Steel'], seg=12, parent=ham, bev=0)
    sphere("Clock_HammerHead", col, 0.011, (0.0, 0, 0.078), M['SteelDark'], parent=ham)
    ham.rotation_euler = (0, 0.55, 0)
    R['hammer'] = ham
    build_orrery(col, M, root)
    return root


def build_gear_train(col, M, train):
    """A real meshing gear train: each wheel's angle = ratio * drive + phase."""
    GEARS.clear()
    y0 = -0.205
    # (name, teeth, module, layer, spokes, style)
    defs = {}

    def place(name, teeth, module, cx, cz, layer, spokes=5, style='spur', thick=0.005):
        ob = _gear_obj(f"Clock_{name}", col, M, teeth, module, thick, cx, cz, y0 + layer * 0.014, train,
                       spokes=spokes, style=style)
        defs[name] = dict(ob=ob, teeth=teeth, c=(cx, cz))
        return ob

    def mesh_with(drv, name, teeth, module, angle_deg, layer, spokes=5, style='spur', thick=0.005):
        """Place a gear meshing with `drv` at the given direction (degrees, 0 = +X, CCW toward +Z)."""
        d = defs[drv]
        rp1 = module * d['teeth'] / 2 if 'mod' not in d else d['mod'] * d['teeth'] / 2
        dist = module * (d['teeth'] + teeth) / 2
        a = math.radians(angle_deg)
        cx, cz = d['c'][0] + dist * math.cos(a), d['c'][1] + dist * math.sin(a)
        ob = place(name, teeth, module, cx, cz, layer, spokes, style, thick)
        defs[name]['mesh'] = (drv, a)
        defs[name]['mod'] = module
        return ob

    def coaxial(base, name, teeth, module, layer, spokes=0, thick=0.008):
        c = defs[base]['c']
        ob = place(name, teeth, module, c[0], c[1], layer, spokes, 'spur', thick)
        defs[name]['coax'] = base
        defs[name]['mod'] = module
        return ob

    m1 = 0.0024
    place("GreatWheel", 96, m1, 0.0, 0.0, 0, spokes=6, thick=0.006)
    defs["GreatWheel"]['mod'] = m1
    mesh_with("GreatWheel", "Pinion2", 12, m1, -38, 0, spokes=0, thick=0.008)
    coaxial("Pinion2", "Wheel2", 80, 0.0019, 1, spokes=5)
    mesh_with("Wheel2", "Pinion3", 10, 0.0019, 70, 1, spokes=0, thick=0.008)
    coaxial("Pinion3", "Wheel3", 64, 0.0016, 2, spokes=5)
    mesh_with("Wheel3", "Pinion4", 10, 0.0016, 165, 2, spokes=0, thick=0.008)
    coaxial("Pinion4", "EscapeWheel", 30, 0.0026, 3, spokes=5, thick=0.004)
    defs["EscapeWheel"]['style'] = 'escape'
    # rebuild escape wheel with saw teeth
    ew = defs["EscapeWheel"]['ob']
    newme = _front(gear_mesh("Clock_EscapeWheel", 30, 0.0026, 0.004, spokes=5, style='escape'))
    old = ew.data
    ew.data = newme
    newme.materials.append(M['BrassPolished'])
    bpy.data.meshes.remove(old)
    for p in newme.polygons:
        p.use_smooth = True
    # second compound on the other side for visual richness
    mesh_with("GreatWheel", "Pinion5", 14, m1, 205, 0, spokes=0, thick=0.008)
    coaxial("Pinion5", "Wheel5", 72, 0.0017, 1, spokes=6)
    mesh_with("Wheel5", "Pinion6", 12, 0.0017, 120, 1, spokes=0, thick=0.008)
    coaxial("Pinion6", "Wheel6", 48, 0.0015, 2, spokes=4)

    # compute ratios and phases (drive = angle of GreatWheel, CCW-positive in XZ)
    pitch = lambda n: TAU / n
    c_off = 0.40
    info = {"GreatWheel": (1.0, 0.0)}
    order = ["Pinion2", "Wheel2", "Pinion3", "Wheel3", "Pinion4", "EscapeWheel", "Pinion5", "Wheel5",
             "Pinion6", "Wheel6"]
    for name in order:
        d = defs[name]
        if 'coax' in d:
            info[name] = info[d['coax']]
            continue
        drv, theta = d['mesh']
        r1, ph1 = info[drv]
        n1, n2 = defs[drv]['teeth'], d['teeth']
        # tooth units at contact (drive gear) when drive = 0
        s1 = (theta - ph1 - c_off * pitch(n1)) / pitch(n1)
        s2 = 0.5 - s1
        ph2 = theta + math.pi - c_off * pitch(n2) - s2 * pitch(n2)
        info[name] = (-r1 * n1 / n2, ph2)
    for name, d in defs.items():
        ratio, phase = info[name]
        GEARS.append((d['ob'], ratio, phase))
        d['ob'].rotation_euler = (0, -phase, 0)
        # arbor
        c = d['c']
        if 'coax' not in d:
            cylinder(f"Clock_Arbor_{name}", col, 0.0022, 0.11, (c[0], -0.165, c[1]), M['Steel'], seg=12,
                     rot=(math.pi / 2, 0, 0), parent=train, bev=0)
    # anchor (pallet) above escape wheel
    ec = defs["EscapeWheel"]['c']
    anc = empty("Clock_AnchorPivot", col, (ec[0], y0 + 3 * 0.014 - 0.006, ec[1] + 0.055), parent=train)
    pts = [(-0.05, -0.03), (-0.045, -0.034), (-0.012, 0.004), (0.012, 0.004), (0.045, -0.034), (0.05, -0.03),
           (0.016, 0.012), (-0.016, 0.012)]
    me = _front(extrude_shape_mesh("Anchor", pts, 0.004))
    ao = obj_from_mesh("Clock_Anchor", me, col, loc=(0, 0, 0), mat=M['BluedSteel'], parent=anc,
                       info="Anchor escapement - releases the train one tooth per swing.")
    bevel(ao, 0.0006, 1)
    R['anchor'] = anc
    # pillars between the plates
    for (px, pz) in ((0.2, 0.18), (-0.2, 0.18), (0.2, -0.18), (-0.2, -0.18)):
        lathe(f"Clock_Pillar_{px}_{pz}", col, [(0.0, 0), (0.008, 0), (0.008, 0.008), (0.005, 0.015),
                                             (0.006, 0.075), (0.008, 0.082), (0.008, 0.09), (0.0, 0.09)],
              (px, -0.12, pz), M['BrassPolished'], seg=24, rot=(math.pi / 2, 0, 0), parent=train)


def build_hand(col, M, name, length, width, loc, parent, kind):
    piv = empty(name + "_Pivot", col, loc, parent=parent)
    pts = []
    if kind == 'hour':
        # spade hand: tail, boss, shaft, spade
        shape = [(-0.006, -0.05), (0.006, -0.05), (0.004, -0.012), (0.013, -0.006), (0.013, 0.006),
                 (0.0035, 0.012), (0.0035, length * 0.62), (width, length * 0.72), (width * 0.9, length * 0.82),
                 (0.004, length * 0.86), (0.0, length)]
    else:
        shape = [(-0.010, -0.075), (0.010, -0.075), (0.012, -0.06), (0.0025, -0.03), (0.011, -0.006),
                 (0.011, 0.006), (0.0025, 0.012), (0.0022, length * 0.8), (width * 0.55, length * 0.86),
                 (0.0018, length * 0.9), (0.0, length)]
    right = [p for p in shape if p[0] >= 0]
    left = [(-x, y) for (x, y) in reversed(shape) if x > 0]
    outline = right + left
    # tidy: remove duplicate first point
    me = extrude_shape_mesh(name, outline, 0.0018, holes=[(0, 0, 0.003)])
    _front(me)
    ob = obj_from_mesh(name, me, col, loc=(0, 0, 0), mat=M['BluedSteel'], parent=piv, smooth=False,
                       info=f"Heat-blued steel {kind} hand (real thin-film interference colour).")
    bevel(ob, 0.0004, 1)
    return piv


def build_orrery(col, M, root):
    base_z = 2.41
    o = empty("Orrery_Root", col, (0, 0, base_z), parent=root)
    R['orrery'] = o
    lathe("Orrery_Base", col, [(0.0, 0), (0.28, 0), (0.28, 0.012), (0.26, 0.02), (0.18, 0.026), (0.15, 0.036),
                               (0.0, 0.036)], (0, 0, 0), M['BrassAged'], seg=96, parent=o,
          info="Orrery - a mechanical model of the solar system.")
    # horizontal crown gear in the base
    g = gear_mesh("Orrery_Crown", 60, 0.0035, 0.006, spokes=6)
    go = obj_from_mesh("Orrery_Crown", g, col, loc=(0, 0, 0.036), mat=M['BrassGear'], parent=o)
    bevel(go, 0.0004, 2)
    R['orrery_crown'] = go
    lathe("Orrery_Column", col, [(0.0, 0), (0.03, 0), (0.03, 0.01), (0.014, 0.03), (0.011, 0.08),
                                 (0.016, 0.16), (0.02, 0.2), (0.0, 0.2)], (0, 0, 0.04), M['BrassPolished'],
          seg=48, parent=o)
    sun = sphere("Orrery_Sun", col, 0.062, (0, 0, 0.30), M['OrrerySun'], seg=64, rings=32, parent=o,
                 info="The orrery sun - glowing amber glass lit from within.")
    R['orrery_sun'] = sun
    # armillary rings around the sun
    for k, tilt in enumerate((0.45, -0.75)):
        piv = empty(f"Orrery_ArmPivot{k}", col, (0, 0, 0.30), parent=o)
        torus(f"Orrery_Armillary{k}", col, 0.10, 0.0025, (0, 0, 0), M['BrassPolished'], rot=(tilt, 0, k * 1.2),
              seg=96, ring=8, parent=piv)
        R[f'armillary{k}'] = piv
    planets = [  # name, arm R, sphere r, height, material, speed
        ("Mercury", 0.12, 0.011, 0.2, 'Silver', 4.15),
        ("Venus", 0.165, 0.017, 0.17, 'VenusEnamel', 1.62),
        ("Earth", 0.225, 0.019, 0.14, 'EarthEnamel', 1.0),
        ("Mars", 0.285, 0.014, 0.115, 'MarsEnamel', 0.53),
        ("Jupiter", 0.36, 0.036, 0.09, 'JupiterEnamel', 0.25),
        ("Saturn", 0.44, 0.028, 0.065, 'BrassPolished', 0.16),
    ]
    R['planets'] = []
    rnd = random.Random(11)
    for i, (n, ar, pr, hz, mat, speed) in enumerate(planets):
        piv = empty(f"Orrery_{n}Pivot", col, (0, 0, 0.04 + hz), parent=o)
        piv.rotation_euler = (0, 0, rnd.uniform(0, TAU))
        lathe(f"Orrery_{n}Collar", col, [(0.0, 0), (0.02, 0), (0.02, 0.008), (0.0, 0.008)], (0, 0, -0.004),
              M['BrassAged'], seg=32, parent=piv)
        cylinder(f"Orrery_{n}Arm", col, 0.0022, ar, (ar / 2, 0, 0), M['BrassPolished'], seg=12,
                 rot=(0, math.pi / 2, 0), parent=piv, bev=0)
        post_h = 0.30 - hz - 0.04 + 0.03 * (i % 2)
        cylinder(f"Orrery_{n}Post", col, 0.0018, post_h, (ar, 0, post_h / 2), M['BrassPolished'], seg=12,
                 parent=piv, bev=0)
        sphere(f"Orrery_{n}", col, pr, (ar, 0, post_h + pr * 0.9), M[mat], seg=48, rings=24, parent=piv,
               info=f"{n} - enamel and brass planet on its orbit arm.")
        if n == "Saturn":
            torus("Orrery_SaturnRing", col, pr * 1.7, pr * 0.35, (ar, 0, post_h + pr * 0.9), M['BrassPolished'],
                  rot=(0.45, 0, 0), seg=64, ring=8, parent=piv, scale=(1, 1, 0.12))
        if n == "Earth":
            mp = empty("Orrery_MoonPivot", col, (ar, 0, post_h + pr * 0.9), parent=piv)
            cylinder("Orrery_MoonArm", col, 0.001, 0.04, (0.02, 0, 0), M['BrassPolished'], seg=8,
                     rot=(0, math.pi / 2, 0), parent=mp, bev=0)
            sphere("Orrery_Moon", col, 0.0065, (0.04, 0, 0), M['IvoryBall'], seg=24, rings=12, parent=mp)
            R['moon'] = mp
        R['planets'].append((piv, speed))

# ============================================================== WORKBENCH & PROPS

def build_bench(M):
    col = collection("Workbench")
    O = M['Oak']; OV = M['OakV']
    bx, by = -0.7, 0.55
    top_z = 0.97
    box("Bench_Top", col, (2.3, 0.86, 0.07), (bx, by, top_z - 0.035), O, bev=0.01,
        info="Watchmaker's oak workbench, a century of scratches and oil stains.")
    for sx in (-1, 1):
        for sy in (-1, 1):
            box(f"Bench_Leg{sx}{sy}", col, (0.09, 0.09, top_z - 0.07), (bx + sx * 1.05, by + sy * 0.36, (top_z - 0.07) / 2),
                OV, bev=0.008)
        box(f"Bench_Stretcher{sx}", col, (0.06, 0.72, 0.08), (bx + sx * 1.05, by, 0.18), O, bev=0.006)
    box("Bench_LongStretcher", col, (2.0, 0.06, 0.08), (bx, by + 0.36, 0.18), O, bev=0.006)
    box("Bench_Apron", col, (2.1, 0.03, 0.14), (bx, by - 0.4, top_z - 0.14), O, bev=0.005)
    knob = sphere_mesh("KnobMesh", 0.014, 24, 12)
    for i, dx in enumerate((-0.7, 0.0, 0.7)):
        box(f"Bench_Drawer{i}", col, (0.6, 0.02, 0.11), (bx + dx, by - 0.418, top_z - 0.135), O, bev=0.004)
        obj_from_mesh(f"Bench_DrawerKnob{i}", knob, col, loc=(bx + dx, by - 0.435, top_z - 0.135),
                      mat=M['BrassPolished'] if i == 0 else None)
    # back riser with small drawers
    box("Bench_Riser", col, (2.3, 0.22, 0.26), (bx, by + 0.33, top_z + 0.13), O, bev=0.006)
    for i in range(8):
        x = bx - 1.0 + i * 0.285
        box(f"Bench_RiserDrawer{i}", col, (0.25, 0.012, 0.09), (x, by + 0.215, top_z + 0.16), O, bev=0.003)
        obj_from_mesh(f"Bench_RiserKnob{i}", knob, col, loc=(x, by + 0.205, top_z + 0.16), scale=(0.6,) * 3)
    for ob in col.objects:
        if ob.data and ob.data.name == "KnobMesh" and not ob.data.materials:
            ob.data.materials.append(M['BrassPolished'])
    R['bench_top'] = top_z
    build_bench_movement(col, M, (-0.38, 0.42, top_z))
    build_pocket_watch(col, M, (-0.66, 0.30, top_z))
    build_props(col, M, top_z)


def build_bench_movement(col, M, p):
    """A small skeleton movement under repair, with a ticking balance wheel."""
    x, y, z = p
    root = empty("Movement_Root", col, (x, y, z), size=0.05)
    root.rotation_euler = (0, 0, math.radians(-18))
    R['movement'] = root
    box("Movement_Base", col, (0.17, 0.10, 0.018), (0, 0, 0.009), M['Mahogany'], bev=0.003, parent=root,
        info="Carriage-clock movement on the bench, mid-repair.")
    for k, yy in enumerate((-0.028, 0.028)):
        pts = [(-0.065, 0), (0.065, 0), (0.065, 0.09), (0.04, 0.125), (-0.04, 0.125), (-0.065, 0.09)]
        holes = [(0.0, 0.06, 0.028)] if k == 0 else []
        me = _front(extrude_shape_mesh(f"MovementPlate{k}", pts, 0.004, holes=holes))
        ob = obj_from_mesh(f"Movement_Plate{k}", me, col, loc=(0, yy, 0.018), mat=M['PerlageBrass'], parent=root,
                           info="Movement plate with perlage finish.")
        bevel(ob, 0.0006, 2)
    for (px, pz) in ((-0.055, 0.03), (0.055, 0.03), (-0.035, 0.11), (0.035, 0.11)):
        cylinder(f"Movement_Pillar{px}{pz}", col, 0.0035, 0.052, (px, 0, 0.018 + pz), M['BrassPolished'],
                 seg=16, rot=(math.pi / 2, 0, 0), parent=root, bev=0.0005)
    gs = []
    for i, (n, m, gx, gz) in enumerate(((48, 0.0011, 0.0, 0.06), (36, 0.0009, 0.033, 0.083),
                                         (30, 0.0008, -0.028, 0.092))):
        me = _front(gear_mesh(f"MovementGear{i}", n, m, 0.0018, spokes=4))
        ob = obj_from_mesh(f"Movement_Gear{i}", me, col, loc=(gx, -0.004 + i * 0.006, 0.018 + gz),
                           mat=M['BrassGear'], parent=root)
        bevel(ob, 0.00012, 1)
        gs.append(ob)
    R['movement_gears'] = gs
    # balance cock + balance wheel on top (horizontal)
    box("Movement_Cock", col, (0.01, 0.07, 0.006), (0.0, 0.0, 0.146), M['BrassPolished'], bev=0.001, parent=root)
    bal = empty("Movement_Balance", col, (0.0, 0.0, 0.152), parent=root)
    me = ring_mesh("BalanceRim", 0.022, 0.019, 0.0022, seg=96)
    obj_from_mesh("Movement_BalanceRim", me, col, loc=(0, 0, 0), mat=M['BrassPolished'], parent=bal,
                  info="Balance wheel with timing screws - the heartbeat of the movement.")
    for k in range(3):
        a = TAU * k / 3
        box(f"Movement_BalanceSpoke{k}", col, (0.019, 0.0018, 0.0016), (math.cos(a) * 0.0095, math.sin(a) * 0.0095, 0.001),
            M['BrassPolished'], bev=0, rot=(0, 0, a), parent=bal)
    screw = sphere_mesh("TimingScrew", 0.0016, 12, 8)
    for k in range(12):
        a = TAU * k / 12
        obj_from_mesh(f"Movement_Screw{k}", screw, col, loc=(math.cos(a) * 0.0232, math.sin(a) * 0.0232, 0.0011),
                      mat=M['BluedSteel'] if k == 0 else None, parent=bal)
    # hairspring: flat Archimedean spiral (curve with round bevel)
    cu = bpy.data.curves.new("Hairspring", 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = 0.00018
    cu.bevel_resolution = 2
    sp = cu.splines.new('POLY')
    n = 400
    sp.points.add(n - 1)
    for i in range(n):
        t = i / (n - 1)
        a = t * TAU * 9
        r = 0.0025 + t * 0.011
        sp.points[i].co = (math.cos(a) * r, math.sin(a) * r, 0.0035, 1)
    hs = bpy.data.objects.new("Movement_Hairspring", cu)
    col.objects.link(hs)
    hs.parent = bal
    cu.materials.append(M['BluedSteel'])
    R['balance'] = bal


def build_pocket_watch(col, M, p):
    x, y, z = p
    root = empty("Watch_Root", col, (x, y, z), size=0.03)
    root.rotation_euler = (0, 0, math.radians(25))
    lathe("Watch_Case", col, [(0.0, 0), (0.022, 0), (0.026, 0.003), (0.027, 0.006), (0.025, 0.009),
                              (0.0, 0.009)], (0, 0, 0), M['Silver'], seg=64, parent=root,
          info="Silver pocket watch with an open hunter lid.")
    lathe("Watch_Dial", col, [(0.0, 0), (0.0225, 0), (0.0225, 0.0006), (0.0, 0.0006)], (0, 0, 0.0092),
          M['EnamelIvory'], seg=64, parent=root)
    hinge = empty("Watch_LidHinge", col, (0, 0.026, 0.008), parent=root)
    hinge.rotation_euler = (math.radians(-105), 0, 0)
    lathe("Watch_Lid", col, [(0.0, 0.004), (0.02, 0.003), (0.026, 0.0), (0.025, -0.001), (0.0, 0.002)],
          (0, -0.026, 0), M['Silver'], seg=64, parent=hinge)
    lathe("Watch_Crown", col, [(0.0, 0), (0.004, 0), (0.0042, 0.006), (0.0, 0.007)], (0, -0.027, 0.0045),
          M['Silver'], seg=24, rot=(math.pi / 2, 0, 0), parent=root)
    for i in range(12):
        a = TAU * i / 12
        box(f"Watch_Idx{i}", col, (0.0006, 0.003, 0.0003), (math.sin(a) * 0.0195, math.cos(a) * 0.0195, 0.0099),
            M['PaintBlack'], bev=0, rot=(0, 0, -a), parent=root)
    box("Watch_HandH", col, (0.0012, 0.012, 0.0004), (0.003, 0.004, 0.0102), M['BluedSteel'], bev=0,
        rot=(0, 0, -0.7), parent=root)
    box("Watch_HandM", col, (0.0008, 0.018, 0.0004), (-0.004, 0.007, 0.0106), M['BluedSteel'], bev=0,
        rot=(0, 0, 0.5), parent=root)
    # watch chain draped across the bench
    link = torus_mesh("WatchLink", 0.0028, 0.0007, seg=12, ring=6)
    link.transform(Matrix.Diagonal((1.0, 0.6, 1.0, 1.0)))
    pts = []
    for i in range(70):
        t = i / 69
        pts.append(Vector((0.0 + 0.02 + t * 0.16, -0.04 + math.sin(t * 5.0) * 0.035 - t * 0.02, 0.0012)))
    for i in range(len(pts) - 1):
        d = (pts[i + 1] - pts[i])
        a = math.atan2(d.y, d.x)
        obj_from_mesh(f"Watch_Chain{i}", link, col, loc=pts[i], rot=((math.pi / 2) * (i % 2), 0, a),
                      mat=M['Silver'] if i == 0 else None, parent=root)


def build_props(col, M, top_z):
    rnd = random.Random(42)
    z = top_z
    # loupe
    lathe("Prop_LoupeBody", col, [(0.012, 0), (0.019, 0), (0.019, 0.022), (0.016, 0.026), (0.012, 0.026),
                                  (0.012, 0.0)], (-0.15, 0.25, z + 0.0), M['BlackLacquer'], seg=48,
          rot=(0.15, 0, 0), close_top=False, close_bottom=False, info="Watchmaker's loupe - real refracting lens.")
    lathe("Prop_LoupeLens", col, [(0.0, 0.016), (0.008, 0.0155), (0.0125, 0.0145), (0.0125, 0.0125),
                                  (0.008, 0.0115), (0.0, 0.011)], (-0.15, 0.25, z), M['LensGlass'], seg=48,
          rot=(0.15, 0, 0))
    # tweezers
    for s in (-1, 1):
        box(f"Prop_Tweezer{s}", col, (0.12, 0.0035, 0.0015), (-0.48, 0.20 + s * 0.003, z + 0.002), M['Steel'],
            bev=0, rot=(0, 0, 0.22 + s * 0.025))
    # screwdrivers
    for i in range(5):
        h = 0.08 + i * 0.012
        sx = 0.02 + i * 0.03
        g = empty(f"Prop_Driver{i}", col, (sx, 0.28 + i * 0.012, z + 0.007))
        g.rotation_euler = (0, math.pi / 2, math.radians(78 + rnd.uniform(-5, 5)))
        lathe(f"Prop_DriverHandle{i}", col, [(0.0, 0), (0.006, 0), (0.0068, 0.01), (0.0068, h * 0.55),
                                             (0.0045, h * 0.6), (0.0, h * 0.6)], (0, 0, 0), M['Beech'], seg=6,
              parent=g, info="Watchmaker's screwdriver with a beech handle.")
        lathe(f"Prop_DriverFerrule{i}", col, [(0.0, 0), (0.0048, 0), (0.0048, 0.008), (0.0, 0.008)],
              (0, 0, h * 0.6), M['BrassPolished'], seg=24, parent=g)
        cylinder(f"Prop_DriverShaft{i}", col, 0.0012, h * 0.5, (0, 0, h * 0.6 + h * 0.25), M['Steel'], seg=12,
                 parent=g, bev=0)
    # scattered loose gears
    for i in range(9):
        n = rnd.choice((24, 30, 36, 40, 48, 60))
        m = rnd.uniform(0.0007, 0.0013)
        me = gear_mesh(f"LooseGear{i}", n, m, 0.0014, spokes=rnd.choice((0, 4, 5)))
        ob = obj_from_mesh(f"Prop_LooseGear{i}", me, col,
                           loc=(rnd.uniform(-0.3, 0.25), rnd.uniform(0.1, 0.3), z + 0.0001),
                           rot=(0, 0, rnd.uniform(0, TAU)), mat=M['BrassGear'], info="Spare brass wheel.")
        bevel(ob, 0.0001, 1)
    # candle in brass holder
    cx, cy = 0.28, 0.72
    lathe("Prop_CandleHolder", col, [(0.0, 0), (0.05, 0), (0.052, 0.004), (0.045, 0.01), (0.012, 0.014),
                                     (0.01, 0.04), (0.022, 0.05), (0.022, 0.055), (0.0, 0.055)], (cx, cy, z),
          M['BrassAged'], seg=64, info="Brass chamberstick.")
    lathe("Prop_Candle", col, [(0.0, 0), (0.017, 0), (0.017, 0.10), (0.0165, 0.106), (0.013, 0.108),
                               (0.004, 0.104), (0.0, 0.104)], (cx, cy, z + 0.055), M['CandleWax'], seg=48,
          info="Beeswax candle (subsurface scattering).")
    lathe("Prop_CandleDrip", col, [(0.0, 0), (0.0175, 0.0), (0.019, 0.004), (0.0, 0.004)], (cx, cy, z + 0.055),
          M['CandleWax'], seg=48)
    cylinder("Prop_Wick", col, 0.0008, 0.012, (cx, cy, z + 0.165), M['PaintBlack'], seg=8, bev=0)
    fl = lathe("Prop_Flame", col, [(0.0, 0), (0.004, 0.003), (0.0055, 0.01), (0.0045, 0.02), (0.002, 0.03),
                                   (0.0, 0.036)], (cx, cy, z + 0.166), M['Flame'], seg=24,
               info="Candle flame - flickers through the whole film.")
    R['flame'] = fl
    R['candle_pos'] = (cx, cy, z + 0.185)
    # copper oil can
    lathe("Prop_OilCan", col, [(0.0, 0), (0.035, 0), (0.037, 0.004), (0.037, 0.03), (0.02, 0.05), (0.008, 0.058),
                               (0.008, 0.066), (0.0, 0.066)], (0.48, 0.45, z), M['Copper'], seg=48,
          info="Copper oil can with verdigris patina.")
    cylinder("Prop_OilSpout", col, 0.0025, 0.12, (0.52, 0.45, z + 0.09), M['Copper'], seg=12, rot=(0, 0.9, 0),
             r2=0.0012, bev=0)
    # hourglass
    hx, hy = 0.58, 0.72
    for zz in (0.0, 0.17):
        cylinder(f"Prop_HourglassCap{zz}", col, 0.045, 0.012, (hx, hy, z + zz + 0.006), M['Mahogany'], seg=48,
                 bev=0.002)
    for k in range(3):
        a = TAU * k / 3
        cylinder(f"Prop_HourglassPost{k}", col, 0.004, 0.16, (hx + math.cos(a) * 0.036, hy + math.sin(a) * 0.036,
                                                                z + 0.091), M['Mahogany'], seg=12, bev=0)
    lathe("Prop_HourglassGlass", col, [(0.0, 0.012), (0.026, 0.014), (0.03, 0.035), (0.022, 0.07),
                                       (0.004, 0.091), (0.022, 0.112), (0.03, 0.147), (0.026, 0.168),
                                       (0.0, 0.17)], (hx, hy, z), M['Glass'], seg=48,
          info="Hourglass - glass refracts the sand.")
    lathe("Prop_HourglassSand", col, [(0.0, 0.014), (0.024, 0.016), (0.022, 0.03), (0.0, 0.045)], (hx, hy, z),
          M['Sand'], seg=32)
    # books
    for i, (w, d, h, mat) in enumerate(((0.24, 0.17, 0.04, 'BookRed'), (0.22, 0.16, 0.035, 'BookGreen'),
                                        (0.26, 0.19, 0.05, 'BookBrown'))):
        zz = z + sum(b[2] for b in ((0.24, 0.17, 0.04), (0.22, 0.16, 0.035), (0.26, 0.19, 0.05))[:i])
        box(f"Prop_Book{i}", col, (w, d, h), (-1.5, 0.62, zz + h / 2), M[mat], bev=0.004,
            rot=(0, 0, rnd.uniform(-0.2, 0.2)), info="Horological reference books.")
        box(f"Prop_BookPages{i}", col, (w - 0.01, d - 0.012, h - 0.008), (-1.5 + 0.003, 0.62, zz + h / 2),
            M['Paper'], bev=0, rot=(0, 0, rnd.uniform(-0.05, 0.05)))
    # blueprint sheet + roll
    bp = bpy.data.meshes.new("BlueprintSheet")
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in ((-0.21, -0.145, 0), (0.21, -0.145, 0), (0.21, 0.145, 0), (-0.21, 0.145, 0))]
    f = bm.faces.new(vs)
    uv = bm.loops.layers.uv.new()
    for l, c in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        l[uv].uv = c
    bm.to_mesh(bp)
    bm.free()
    obj_from_mesh("Prop_Blueprint", bp, col, loc=(-1.05, 0.30, z + 0.0008), rot=(0, 0, 0.12),
                  mat=M['Blueprint'], info="Design drawing for the astronomical clock's gear train.")
    cylinder("Prop_BlueprintRoll", col, 0.018, 0.42, (-1.1, 0.55, z + 0.018), M['Blueprint'], seg=32,
             rot=(0, math.pi / 2, 0.1), bev=0)
    # bench vice (left end)
    vx, vy = -1.72, 0.2
    box("Prop_ViceBody", col, (0.12, 0.10, 0.08), (vx, vy, z + 0.04), M['CastIron'], bev=0.006,
        info="Cast-iron bench vice.")
    box("Prop_ViceJawA", col, (0.13, 0.025, 0.05), (vx, vy - 0.06, z + 0.07), M['CastIron'], bev=0.004)
    box("Prop_ViceJawB", col, (0.13, 0.025, 0.05), (vx, vy - 0.10, z + 0.07), M['CastIron'], bev=0.004)
    cylinder("Prop_ViceScrew", col, 0.007, 0.16, (vx, vy - 0.16, z + 0.06), M['Steel'], seg=16,
             rot=(math.pi / 2, 0, 0), bev=0)
    cylinder("Prop_ViceHandle", col, 0.004, 0.14, (vx, vy - 0.235, z + 0.06), M['Steel'], seg=12, bev=0)
    # stool
    lathe("Prop_StoolSeat", col, [(0.0, 0), (0.17, 0), (0.18, 0.015), (0.175, 0.035), (0.0, 0.04)],
          (-0.45, -0.25, 0.62), M['Oak'], seg=64, info="Worn oak stool.")
    for k in range(3):
        a = TAU * k / 3 + 0.3
        lx, ly = -0.45 + math.cos(a) * 0.17, -0.25 + math.sin(a) * 0.17
        leg = cylinder(f"Prop_StoolLeg{k}", col, 0.018, 0.65, (lx, ly, 0.31), M['OakV'], seg=16, bev=0.002,
                       r2=0.014)
        leg.rotation_euler = (math.sin(a) * -0.12, math.cos(a) * 0.12, 0)
    torus("Prop_StoolRing", col, 0.19, 0.008, (-0.45, -0.25, 0.22), M['OakV'], seg=48, ring=8)


def build_lamp(M):
    col = collection("Lighting")
    x, y, zt = -0.6, 0.5, 2.05
    cylinder("Lamp_Cord", col, 0.004, 3.4 - zt - 0.15, (x, y, (3.4 + zt + 0.15) / 2), M['Rubber'], seg=12, bev=0)
    lathe("Lamp_Shade", col, [(0.03, 0.15), (0.05, 0.13), (0.09, 0.06), (0.17, 0.0), (0.172, 0.006),
                              (0.093, 0.064), (0.052, 0.134), (0.032, 0.155)], (x, y, zt), M['ShadeGreen'],
          seg=64, close_top=False, close_bottom=False, info="Enamelled green pendant lamp - switches on at dusk.")
    lathe("Lamp_ShadeInner", col, [(0.168, 0.002), (0.09, 0.063), (0.05, 0.133), (0.03, 0.15)], (x, y, zt - 0.001),
          M['ShadeInner'], seg=64, close_top=False, close_bottom=False)
    lathe("Lamp_Socket", col, [(0.0, 0.11), (0.022, 0.11), (0.022, 0.16), (0.0, 0.16)], (x, y, zt),
          M['BrassAged'], seg=32)
    bulb = lathe("Lamp_Bulb", col, [(0.0, 0.025), (0.02, 0.03), (0.03, 0.05), (0.028, 0.075), (0.016, 0.1),
                                    (0.015, 0.112), (0.0, 0.112)], (x, y, zt), M['BulbFilament'], seg=32)
    R['bulb'] = bulb
    R['lamp_pos'] = (x, y, zt + 0.05)

# ============================================================== SHELVES, CABINET, WALL CLOCKS

def build_shelves(M):
    col = collection("Props")
    rnd = random.Random(5)
    xw = 3.5
    for k, zz in enumerate((1.1, 1.55, 2.0)):
        box(f"Shelf_{k}", col, (0.3, 2.6, 0.03), (xw - 0.16, -0.4, zz), M['Oak'], bev=0.004,
            info="Oak wall shelf.")
        for yy in (-1.5, -0.4, 0.7):
            box(f"ShelfBracket_{k}_{yy}", col, (0.2, 0.02, 0.12), (xw - 0.11, yy, zz - 0.075), M['CastIron'], bev=0.003)
        y = -1.6
        while y < 0.8:
            kind = rnd.random()
            if kind < 0.45:  # books
                n = rnd.randint(3, 7)
                for b in range(n):
                    h = rnd.uniform(0.18, 0.3) if zz < 1.9 else rnd.uniform(0.15, 0.25)
                    t = rnd.uniform(0.025, 0.05)
                    mat = rnd.choice(('BookRed', 'BookGreen', 'BookBlue', 'BookBrown', 'BookOchre'))
                    tilt = rnd.uniform(-0.04, 0.04) if b < n - 1 else rnd.uniform(0.15, 0.3)
                    box(f"ShelfBook_{k}_{y:.2f}_{b}", col, (rnd.uniform(0.16, 0.22), t, h),
                        (xw - 0.17, y + t / 2, zz + 0.015 + h / 2), M[mat], bev=0.003, rot=(tilt, 0, 0))
                    y += t + 0.002
                y += 0.05
            elif kind < 0.7:  # glass jar with brass lid
                r = rnd.uniform(0.04, 0.06)
                h = rnd.uniform(0.1, 0.18)
                lathe(f"ShelfJar_{k}_{y:.2f}", col, [(0.0, 0), (r, 0), (r, h), (r * 0.8, h + 0.01), (r * 0.8, h + 0.02),
                                                     (0.0, h + 0.02)], (xw - 0.17, y + r, zz + 0.015),
                      M['JarGlass'], seg=48, info="Jar of spare screws and springs.")
                lathe(f"ShelfJarLid_{k}_{y:.2f}", col, [(0.0, 0), (r * 0.84, 0), (r * 0.84, 0.02), (0.0, 0.022)],
                      (xw - 0.17, y + r, zz + 0.015 + h + 0.012), M['BrassAged'], seg=48)
                lathe(f"ShelfJarFill_{k}_{y:.2f}", col, [(0.0, 0.002), (r * 0.92, 0.002), (r * 0.9, h * 0.4),
                                                         (0.0, h * 0.45)], (xw - 0.17, y + r, zz + 0.015),
                      M['BrassDark'], seg=32)
                y += 2 * r + 0.05
            elif kind < 0.88:  # small mantel clock
                w = rnd.uniform(0.14, 0.2)
                h = w * 1.2
                box(f"ShelfClock_{k}_{y:.2f}", col, (0.1, w, h), (xw - 0.17, y + w / 2, zz + 0.015 + h / 2),
                    M['Mahogany'], bev=0.008, info="Mantel clock awaiting repair.")
                lathe(f"ShelfClockDial_{k}_{y:.2f}", col, [(0.0, 0), (w * 0.36, 0), (w * 0.36, 0.004), (0.0, 0.004)],
                      (xw - 0.225, y + w / 2, zz + 0.015 + h * 0.58), M['Enamel'], seg=48, rot=(0, -math.pi / 2, 0))
                torus(f"ShelfClockBezel_{k}_{y:.2f}", col, w * 0.37, 0.004, (xw - 0.227, y + w / 2, zz + 0.015 + h * 0.58),
                      M['BrassPolished'], rot=(0, math.pi / 2, 0), seg=48, ring=8)
                y += w + 0.06
            else:  # brass globe on stand
                lathe(f"ShelfGlobeStand_{k}_{y:.2f}", col, [(0.0, 0), (0.05, 0), (0.05, 0.01), (0.008, 0.03),
                                                            (0.008, 0.08), (0.0, 0.08)], (xw - 0.17, y + 0.07, zz + 0.015),
                      M['BrassAged'], seg=32)
                sphere(f"ShelfGlobe_{k}_{y:.2f}", col, 0.065, (xw - 0.17, y + 0.07, zz + 0.16), M['EarthEnamel'],
                       info="Enamelled terrestrial globe.")
                torus(f"ShelfGlobeRing_{k}_{y:.2f}", col, 0.072, 0.003, (xw - 0.17, y + 0.07, zz + 0.16),
                      M['BrassAged'], rot=(0, 0.4, 0), seg=48, ring=8)
                y += 0.17


def build_cabinet(M):
    """Apothecary-style drawer cabinet against the back wall (many small brass-knobbed drawers)."""
    col = collection("Props")
    x0, x1, yb, h = 1.45, 2.95, 2.97, 1.9
    w = x1 - x0
    d = 0.45
    yc = yb - d / 2
    box("Cabinet_Body", col, (w, d, h), ((x0 + x1) / 2, yc, h / 2), M['Mahogany'], bev=0.01,
        info="Drawer cabinet holding thousands of tiny clock parts.")
    box("Cabinet_Top", col, (w + 0.06, d + 0.05, 0.04), ((x0 + x1) / 2, yc - 0.01, h + 0.02), M['Mahogany'], bev=0.012)
    knob = sphere_mesh("CabKnob", 0.011, 16, 8)
    knob.materials.append(M['BrassPolished'])
    plate = box_mesh("CabLabel", 0.05, 0.003, 0.022)
    plate.materials.append(M['BrassAged'])
    cols_, rows = 6, 9
    dw, dh = (w - 0.08) / cols_, (h - 0.2) / rows
    for i in range(cols_):
        for j in range(rows):
            cx = x0 + 0.04 + dw * (i + 0.5)
            cz = 0.12 + dh * (j + 0.5)
            box(f"Cabinet_Drawer_{i}_{j}", col, (dw - 0.012, 0.018, dh - 0.012), (cx, yc - d / 2 - 0.006, cz),
                M['Mahogany'], bev=0.003)
            obj_from_mesh(f"Cabinet_Knob_{i}_{j}", knob, col, loc=(cx, yc - d / 2 - 0.02, cz - dh * 0.12))
            obj_from_mesh(f"Cabinet_Label_{i}_{j}", plate, col, loc=(cx, yc - d / 2 - 0.016, cz + dh * 0.18),
                          smooth=False)
    # small items on the cabinet top
    lathe("Cabinet_Bottle", col, [(0.0, 0), (0.04, 0), (0.042, 0.12), (0.015, 0.16), (0.012, 0.2), (0.0, 0.2)],
          (2.6, yc, h + 0.04), M['BottleGlass'], seg=48, info="Amber bottle of clock oil.")
    box("Cabinet_BoxLid", col, (0.25, 0.18, 0.08), (1.9, yc, h + 0.08), M['Leather'], bev=0.006,
        info="Leather-covered tool case.")


def build_wall_clocks(M):
    col = collection("Props")
    R['wall_seconds'] = []
    for k, (x, z, r) in enumerate(((-2.65, 2.25, 0.2), (-1.85, 2.5, 0.14), (-1.25, 2.1, 0.17))):
        y = 2.985
        root = empty(f"WallClock{k}", col, (x, y, z))
        torus(f"WallClock{k}_Bezel", col, r, r * 0.12, (0, -r * 0.08, 0), M['Mahogany'] if k != 1 else M['BrassAged'],
              rot=(math.pi / 2, 0, 0), seg=96, ring=16, parent=root, info="Wall clock - its second hand really ticks.")
        lathe(f"WallClock{k}_Dial", col, [(0.0, 0), (r * 0.98, 0), (r * 0.98, 0.004), (0.0, 0.004)],
              (0, -0.01, 0), M['Enamel'] if k != 2 else M['EnamelIvory'], seg=96, rot=(math.pi / 2, 0, 0),
              parent=root)
        for i in range(12):
            a = TAU * i / 12
            box(f"WallClock{k}_Idx{i}", col, (r * 0.03, 0.002, r * 0.12),
                (math.sin(a) * r * 0.82, -0.016, math.cos(a) * r * 0.82), M['PaintBlack'], bev=0, rot=(0, a, 0),
                parent=root)
        hh = empty(f"WallClock{k}_H", col, (0, -0.018, 0), parent=root)
        hh.rotation_euler = (0, TAU * random.Random(k).random(), 0)
        box(f"WallClock{k}_HourHand", col, (r * 0.05, 0.002, r * 0.5), (0, 0, r * 0.22), M['PaintBlack'], bev=0,
            parent=hh)
        mh = empty(f"WallClock{k}_M", col, (0, -0.021, 0), parent=root)
        mh.rotation_euler = (0, TAU * random.Random(k + 7).random(), 0)
        box(f"WallClock{k}_MinHand", col, (r * 0.035, 0.002, r * 0.78), (0, 0, r * 0.35), M['PaintBlack'], bev=0,
            parent=mh)
        sh = empty(f"WallClock{k}_S", col, (0, -0.024, 0), parent=root)
        box(f"WallClock{k}_SecHand", col, (r * 0.012, 0.0015, r * 0.95), (0, 0, r * 0.3), M['MarsEnamel'], bev=0,
            parent=sh)
        R['wall_seconds'].append((sh, k))
        lathe(f"WallClock{k}_Glass", col, [(0.0, 0.01), (r * 0.7, 0.008), (r * 0.98, 0.0)], (0, -0.03, 0),
              M['Glass'], seg=64, rot=(math.pi / 2, 0, 0), parent=root, close_bottom=False)
    # framed blueprint on the wall
    bp = bpy.data.meshes.new("WallBlueprint")
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in ((-0.36, 0, -0.25), (0.36, 0, -0.25), (0.36, 0, 0.25), (-0.36, 0, 0.25))]
    f = bm.faces.new(vs)
    uv = bm.loops.layers.uv.new()
    for l, c in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        l[uv].uv = c
    bm.to_mesh(bp)
    bm.free()
    obj_from_mesh("Wall_Blueprint", bp, col, loc=(-2.0, 2.97, 1.45), mat=M['Blueprint'],
                  info="Framed design drawing.")
    for (sx, sz, w, hh_) in ((0, 0.27, 0.8, 0.04), (0, -0.27, 0.8, 0.04), (0.38, 0, 0.04, 0.58), (-0.38, 0, 0.04, 0.58)):
        box(f"Wall_BlueprintFrame{sx}{sz}", col, (w, 0.025, hh_), (-2.0 + sx, 2.965, 1.45 + sz), M['OldTimber'], bev=0.004)
    # crates in the back-left corner
    for k, (x, y, s, rz) in enumerate(((-3.0, 2.45, 0.55, 0.1), (-3.0, 2.45, 0.42, -0.15), (-2.45, 2.55, 0.4, 0.3))):
        zb = 0.0 if k != 1 else 0.55
        box(f"Crate{k}", col, (s, s, s), (x, y, zb + s / 2), M['OakV'], bev=0.01, rot=(0, 0, rz),
            info="Shipping crate of clock parts.")
    # telescope on the window sill (astronomy theme)
    tg = empty("Telescope", col, (-3.35, 1.5, 0.86))
    for k in range(3):
        a = TAU * k / 3
        leg = cylinder(f"Telescope_Leg{k}", col, 0.005, 0.22, (math.cos(a) * 0.04, math.sin(a) * 0.04, 0.1),
                       M['BrassAged'], seg=12, parent=tg, bev=0)
        leg.rotation_euler = (-math.sin(a) * 0.35, math.cos(a) * 0.35, 0)
    tube = empty("Telescope_Tube", col, (0, 0, 0.22), parent=tg)
    tube.rotation_euler = (0, math.radians(-75), math.radians(-10))
    lathe("Telescope_Body", col, [(0.0, -0.2), (0.016, -0.2), (0.018, -0.1), (0.022, 0.0), (0.026, 0.15),
                                  (0.03, 0.2), (0.03, 0.22), (0.0, 0.22)], (0, 0, 0), M['BrassPolished'], seg=48,
          parent=tube, info="Brass telescope pointed at the evening sky.")
    torus("Telescope_Ring", col, 0.0235, 0.003, (0, 0, 0.05), M['BrassDark'], seg=48, ring=8, parent=tube)

# ============================================================== FX: fog + dust

def build_fx(M, dust_count=1800):
    col = collection("FX")
    fog = box("RoomFog", col, (6.9, 5.9, 3.3), (0, 0, 1.68), M['RoomFog'], bev=0)
    fog["cw_info"] = "Volumetric haze - makes the window light visible as god-rays."
    fog.visible_shadow = False
    R['fog'] = fog
    # dust motes: particle system emitted from a hidden volume, instanced tiny spheres
    em = box("DustEmitter", col, (3.6, 3.4, 2.2), (-1.1, 0.6, 1.4), None, bev=0)
    em.hide_render = False
    em.show_instancer_for_render = False
    em.show_instancer_for_viewport = False
    em.display_type = 'WIRE'
    mote = sphere("DustMote", col, 0.0011, (0, 0, -5), M['DustMote'], seg=8, rings=4)
    mote.hide_render = True
    mote.hide_viewport = True
    ps_mod = em.modifiers.new("Dust", 'PARTICLE_SYSTEM')
    ps = ps_mod.particle_system
    st = ps.settings
    st.name = "DustSettings"
    st.count = dust_count
    st.frame_start = -60
    st.frame_end = -59
    st.lifetime = 3000
    st.emit_from = 'VOLUME'
    st.distribution = 'RAND'
    st.physics_type = 'NEWTON'
    st.normal_factor = 0.0
    st.factor_random = 0.01
    st.brownian_factor = 0.004
    st.drag_factor = 0.4
    st.damping = 0.2
    st.effector_weights.gravity = 0.0
    st.render_type = 'OBJECT'
    st.instance_object = mote
    st.particle_size = 1.0
    st.size_random = 0.7
    st.use_rotations = False
    st.timestep = 0.04
    ps.seed = 17
    # gentle air currents
    tf = bpy.data.objects.new("DustTurbulence", None)
    col.objects.link(tf)
    tf.location = (-1.0, 0.6, 1.5)
    bpy.context.view_layer.update()
    try:
        tf.field.type = 'TURBULENCE'
        tf.field.strength = 0.08
        tf.field.size = 0.8
        tf.field.flow = 0.5
    except Exception:
        pass
    R['dust'] = em
    return fog


def build_all(M, sun_dir, dust_count=1800):
    build_room(M)
    build_exterior(M, sun_dir)
    # the painted exterior must never block the sunlight entering the windows
    for ob in collection("Exterior").objects:
        ob.visible_shadow = False
    build_clock(M)
    build_bench(M)
    build_lamp(M)
    build_shelves(M)
    build_cabinet(M)
    build_wall_clocks(M)
    build_fx(M, dust_count)
    return R
