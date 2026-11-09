"""
cw_util.py - shared helpers for building "The Clockmaker's Workshop at Dusk".

Everything in the scene is generated from code, so these helpers keep the
modelling / shading / animation scripts short and readable:

  * ShaderBuilder  - terse procedural node-graph construction
  * geometry       - lathe (spin a profile), extruded 2D shapes, panels with holes,
                     boxes, cylinders, gears
  * animation      - key() writes keyframes directly into Blender 5.x layered actions
"""
import math
import bmesh
import bpy
from mathutils import Vector, Matrix, Euler
from bpy_extras import anim_utils

TAU = math.tau

# --------------------------------------------------------------------------
# Collections / objects
# --------------------------------------------------------------------------

def collection(name, parent=None):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(col)
    return col


def obj_from_mesh(name, mesh, col, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1),
                  mat=None, smooth=True, info=None, parent=None):
    ob = bpy.data.objects.new(name, mesh)
    col.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = rot
    ob.scale = scale
    if mat is not None:
        mats = mat if isinstance(mat, (list, tuple)) else [mat]
        for m in mats:
            mesh.materials.append(m)
    if smooth and len(mesh.polygons):
        for p in mesh.polygons:
            p.use_smooth = True
        # 'smooth by angle': keep hard edges crisp (critical for boxes, glass panes, caps)
        mesh.set_sharp_from_angle(angle=math.radians(40))
    if info:
        ob["cw_info"] = info
    if parent is not None:
        ob.parent = parent
    return ob


def empty(name, col, loc=(0, 0, 0), rot=(0, 0, 0), parent=None, size=0.1, kind='PLAIN_AXES'):
    ob = bpy.data.objects.new(name, None)
    col.objects.link(ob)
    ob.empty_display_type = kind
    ob.empty_display_size = size
    ob.location = loc
    ob.rotation_euler = rot
    if parent is not None:
        ob.parent = parent
    return ob


def bevel(ob, width=0.002, segments=2, angle=35, harden=True):
    """Bevelled edges catch highlights - the single biggest realism win for hard surfaces."""
    m = ob.modifiers.new("Bevel", 'BEVEL')
    m.width = width
    m.segments = segments
    m.limit_method = 'ANGLE'
    m.angle_limit = math.radians(angle)
    m.harden_normals = harden
    m.miter_outer = 'MITER_ARC'
    return m


def mesh_from_bmesh(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me

# --------------------------------------------------------------------------
# Geometry primitives (built with bmesh - no operators, works headless)
# --------------------------------------------------------------------------

def box_mesh(name, sx, sy, sz, origin='center'):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    if origin == 'bottom':
        bmesh.ops.translate(bm, vec=(0, 0, sz / 2), verts=bm.verts)
    return mesh_from_bmesh(name, bm)


def box(name, col, size, loc, mat=None, bev=0.004, rot=(0, 0, 0), info=None, parent=None, seg=2):
    ob = obj_from_mesh(name, box_mesh(name, *size), col, loc=loc, rot=rot, mat=mat,
                       smooth=True, info=info, parent=parent)
    if bev:
        bevel(ob, bev, seg)
    return ob


def cylinder_mesh(name, r, depth, seg=48, r2=None, cap=True):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=seg,
                          radius1=r, radius2=r if r2 is None else r2, depth=depth)
    return mesh_from_bmesh(name, bm)


def cylinder(name, col, r, depth, loc, mat=None, seg=48, rot=(0, 0, 0), bev=0.0015, r2=None,
             info=None, parent=None):
    ob = obj_from_mesh(name, cylinder_mesh(name, r, depth, seg, r2), col, loc=loc, rot=rot,
                       mat=mat, info=info, parent=parent)
    if bev:
        bevel(ob, bev, 2)
    return ob


def sphere_mesh(name, r, seg=48, rings=24):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r)
    return mesh_from_bmesh(name, bm)


def sphere(name, col, r, loc, mat=None, seg=48, rings=24, scale=(1, 1, 1), info=None, parent=None):
    return obj_from_mesh(name, sphere_mesh(name, r, seg, rings), col, loc=loc, scale=scale,
                         mat=mat, info=info, parent=parent)


def torus_mesh(name, R, r, seg=64, ring=16):
    bm = bmesh.new()
    verts = []
    for i in range(seg):
        a = TAU * i / seg
        row = []
        for j in range(ring):
            b = TAU * j / ring
            x = (R + r * math.cos(b)) * math.cos(a)
            y = (R + r * math.cos(b)) * math.sin(a)
            z = r * math.sin(b)
            row.append(bm.verts.new((x, y, z)))
        verts.append(row)
    for i in range(seg):
        for j in range(ring):
            bm.faces.new((verts[i][j], verts[(i + 1) % seg][j],
                          verts[(i + 1) % seg][(j + 1) % ring], verts[i][(j + 1) % ring]))
    return mesh_from_bmesh(name, bm)


def torus(name, col, R, r, loc, mat=None, rot=(0, 0, 0), seg=64, ring=16, info=None, parent=None,
          scale=(1, 1, 1)):
    return obj_from_mesh(name, torus_mesh(name, R, r, seg, ring), col, loc=loc, rot=rot,
                         mat=mat, info=info, parent=parent, scale=scale)


def lathe_mesh(name, profile, seg=64, close_top=True, close_bottom=True):
    """Spin a 2D (radius, z) profile around Z.  Profile runs bottom -> top."""
    bm = bmesh.new()
    rings = []
    for (r, z) in profile:
        ring = []
        if r < 1e-6:
            v = bm.verts.new((0, 0, z))
            ring = [v] * seg
        else:
            for i in range(seg):
                a = TAU * i / seg
                ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z)))
        rings.append(ring)
    for k in range(len(rings) - 1):
        A, B = rings[k], rings[k + 1]
        for i in range(seg):
            i2 = (i + 1) % seg
            quad = [A[i], A[i2], B[i2], B[i]]
            uniq = []
            for v in quad:
                if v not in uniq:
                    uniq.append(v)
            if len(uniq) >= 3:
                try:
                    bm.faces.new(uniq)
                except ValueError:
                    pass
    if close_bottom and profile[0][0] > 1e-6:
        bm.faces.new(list(reversed(rings[0])))
    if close_top and profile[-1][0] > 1e-6:
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_from_bmesh(name, bm)


def lathe(name, col, profile, loc, mat=None, seg=64, rot=(0, 0, 0), scale=(1, 1, 1), info=None,
          parent=None, close_top=True, close_bottom=True):
    return obj_from_mesh(name, lathe_mesh(name, profile, seg, close_top, close_bottom), col,
                         loc=loc, rot=rot, scale=scale, mat=mat, info=info, parent=parent)


def extrude_shape_mesh(name, outline, depth, holes=()):
    """Extrude a 2D polygon (XY) along +Z by depth.  Optional holes are circles (cx, cy, r)."""
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, 0)) for (x, y) in outline]
    edges = [bm.edges.new((vs[i], vs[(i + 1) % len(vs)])) for i in range(len(vs))]
    for (cx, cy, r) in holes:
        n = 32
        hv = [bm.verts.new((cx + r * math.cos(TAU * i / n), cy + r * math.sin(TAU * i / n), 0))
              for i in range(n)]
        edges += [bm.edges.new((hv[i], hv[(i + 1) % n])) for i in range(n)]
    bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=True, edges=edges)
    faces = list(bm.faces)
    ret = bmesh.ops.extrude_face_region(bm, geom=faces)
    ext_verts = [e for e in ret['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, 0, depth), verts=ext_verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_from_bmesh(name, bm)


def ring_mesh(name, r_out, r_in, depth, seg=96):
    """Flat annulus extruded along +Z."""
    bm = bmesh.new()
    outer = [bm.verts.new((r_out * math.cos(TAU * i / seg), r_out * math.sin(TAU * i / seg), 0)) for i in range(seg)]
    inner = [bm.verts.new((r_in * math.cos(TAU * i / seg), r_in * math.sin(TAU * i / seg), 0)) for i in range(seg)]
    for i in range(seg):
        i2 = (i + 1) % seg
        bm.faces.new((outer[i], outer[i2], inner[i2], inner[i]))
    ret = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    bmesh.ops.translate(bm, vec=(0, 0, depth),
                        verts=[e for e in ret['geom'] if isinstance(e, bmesh.types.BMVert)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_from_bmesh(name, bm)


def panel_with_hole_mesh(name, w, h, r, depth, cx=0.0, cy=0.0, seg_side=16):
    """Rectangular panel (XY, centred) with a circular hole, extruded along +Z."""
    bm = bmesh.new()
    n = seg_side * 4
    # perimeter points of the rectangle, parameterised by angle so they pair with the circle
    outer, inner = [], []
    for i in range(n):
        a = TAU * i / n + math.pi / 4 + math.pi  # start at a corner-ish
        dx, dy = math.cos(a), math.sin(a)
        # ray from (cx,cy) to rectangle border
        tx = ((w / 2 if dx > 0 else -w / 2) - cx) / dx if abs(dx) > 1e-9 else 1e9
        ty = ((h / 2 if dy > 0 else -h / 2) - cy) / dy if abs(dy) > 1e-9 else 1e9
        t = min(tx, ty)
        outer.append(bm.verts.new((cx + dx * t, cy + dy * t, 0)))
        inner.append(bm.verts.new((cx + r * dx, cy + r * dy, 0)))
    for i in range(n):
        i2 = (i + 1) % n
        bm.faces.new((outer[i], outer[i2], inner[i2], inner[i]))
    ret = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    bmesh.ops.translate(bm, vec=(0, 0, depth),
                        verts=[e for e in ret['geom'] if isinstance(e, bmesh.types.BMVert)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_from_bmesh(name, bm)


def gear_mesh(name, teeth, module, thickness, spokes=5, hub_r=None, bore=None, rim=None,
              style='spur'):
    """Clock-style spur gear in the XY plane, extruded +Z by thickness, centred on Z=0..t.

    style='spur'   - rounded clock teeth
    style='escape' - saw-tooth escape wheel
    Tooth centres sit at local angle 0.40 * pitch (used for phase calculations).
    """
    rp = module * teeth / 2.0
    ro = rp + module * (0.95 if style == 'spur' else 1.6)
    rr = rp - module * 1.25
    pitch = TAU / teeth
    if style == 'spur':
        prof = [(0.00, rr), (0.14, rr), (0.22, rp - 0.2 * module), (0.29, rp + 0.35 * module),
                (0.35, ro - 0.05 * module), (0.40, ro), (0.45, ro - 0.05 * module),
                (0.51, rp + 0.35 * module), (0.58, rp - 0.2 * module), (0.66, rr)]
    else:  # escape: steep face, long sloped back
        prof = [(0.00, rr), (0.08, rr), (0.40, ro), (0.44, ro - 0.1 * module), (0.47, rr + 0.3 * module),
                (0.60, rr)]
    pts = []
    for k in range(teeth):
        for f, r in prof:
            a = (k + f) * pitch
            pts.append((r * math.cos(a), r * math.sin(a)))
    bm = bmesh.new()
    if rim is None:
        rim = max(module * 2.2, rr * 0.16)
    r_in = rr - rim
    solid = spokes == 0 or r_in < module * 3
    outer = [bm.verts.new((x, y, 0)) for (x, y) in pts]
    if solid:
        bore_r = bore or max(rr * 0.12, module * 0.8)
        n = len(pts)
        inner = []
        for (x, y) in pts:
            a = math.atan2(y, x)
            inner.append(bm.verts.new((bore_r * math.cos(a), bore_r * math.sin(a), 0)))
        for i in range(n):
            i2 = (i + 1) % n
            bm.faces.new((outer[i], outer[i2], inner[i2], inner[i]))
    else:
        n = len(pts)
        inner = []
        for (x, y) in pts:
            a = math.atan2(y, x)
            inner.append(bm.verts.new((r_in * math.cos(a), r_in * math.sin(a), 0)))
        for i in range(n):
            i2 = (i + 1) % n
            bm.faces.new((outer[i], outer[i2], inner[i2], inner[i]))
    ret = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    bmesh.ops.translate(bm, vec=(0, 0, thickness),
                        verts=[e for e in ret['geom'] if isinstance(e, bmesh.types.BMVert)])
    if not solid:
        # hub ring
        hr = hub_r or max(r_in * 0.28, module * 3)
        br = bore or hr * 0.35
        hub = bmesh.new()
        seg = 48
        o = [hub.verts.new((hr * math.cos(TAU * i / seg), hr * math.sin(TAU * i / seg), 0)) for i in range(seg)]
        ii = [hub.verts.new((br * math.cos(TAU * i / seg), br * math.sin(TAU * i / seg), 0)) for i in range(seg)]
        for i in range(seg):
            i2 = (i + 1) % seg
            hub.faces.new((o[i], o[i2], ii[i2], ii[i]))
        r2 = bmesh.ops.extrude_face_region(hub, geom=list(hub.faces))
        bmesh.ops.translate(hub, vec=(0, 0, thickness * 1.15),
                            verts=[e for e in r2['geom'] if isinstance(e, bmesh.types.BMVert)])
        bmesh.ops.translate(hub, vec=(0, 0, -thickness * 0.075), verts=hub.verts)
        # spokes (tapered, slightly curved look via 4-point outline)
        for s in range(spokes):
            a = TAU * s / spokes + pitch * 0.4
            ca, sa = math.cos(a), math.sin(a)
            w0, w1 = hr * 0.45, hr * 0.28
            p0 = (hr * 0.8, -w0)
            p1 = (r_in + rim * 0.3, -w1)
            p2 = (r_in + rim * 0.3, w1)
            p3 = (hr * 0.8, w0)
            vs = [hub.verts.new((x * ca - y * sa, x * sa + y * ca, 0)) for (x, y) in (p0, p1, p2, p3)]
            f = hub.faces.new(vs)
            r3 = bmesh.ops.extrude_face_region(hub, geom=[f])
            bmesh.ops.translate(hub, vec=(0, 0, thickness * 0.85),
                                verts=[e for e in r3['geom'] if isinstance(e, bmesh.types.BMVert)])
            bmesh.ops.translate(hub, vec=(0, 0, thickness * 0.075), verts=vs)
        tmp = bpy.data.meshes.new("tmp")
        hub.to_mesh(tmp)
        hub.free()
        bm.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_from_bmesh(name, bm)


def text_mesh(name, body, size, depth, align='CENTER'):
    """Convert a text string to a mesh (centred)."""
    cu = bpy.data.curves.new(name + "_txt", 'FONT')
    cu.body = body
    cu.size = size
    cu.extrude = depth / 2
    cu.align_x = align
    cu.align_y = 'CENTER'
    cu.resolution_u = 4
    tmp = bpy.data.objects.new(name + "_tmp", cu)
    bpy.context.scene.collection.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    me.name = name
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    return me

# --------------------------------------------------------------------------
# Shader node building
# --------------------------------------------------------------------------

def _sock(sockets, name):
    """Find a socket by name (or index), preferring enabled sockets (Mix nodes have duplicates)."""
    if isinstance(name, int):
        return sockets[name]
    cands = [s for s in sockets if s.name == name or s.identifier == name]
    if not cands:
        raise KeyError(f"socket {name!r} not in {[s.name for s in sockets]}")
    for s in cands:
        if s.enabled:
            return s
    return cands[0]


class ShaderBuilder:
    def __init__(self, nt):
        self.nt = nt
        self.x = 0

    def node(self, type_, inputs=None, **props):
        n = self.nt.nodes.new(type_)
        n.location = (self.x, 0)
        self.x -= 220
        for k, v in props.items():
            setattr(n, k, v)
        for k, v in (inputs or {}).items():
            self.set(n, k, v)
        return n

    def set(self, n, key, v):
        s = _sock(n.inputs, key)
        if isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, s)
        elif isinstance(v, bpy.types.Node):
            self.nt.links.new(self.out(v), s)
        else:
            if isinstance(v, (tuple, list)) and len(v) == 3 and s.type == 'RGBA':
                v = (*v, 1.0)
            s.default_value = v

    def out(self, n, name=None):
        if name is None:
            for s in n.outputs:
                if s.enabled:
                    return s
            return n.outputs[0]
        return _sock(n.outputs, name)

    def link(self, a, b):
        self.nt.links.new(a, b)

    # convenience nodes ---------------------------------------------------
    def coord(self, kind='Object'):
        if not hasattr(self, '_tc'):
            self._tc = self.node('ShaderNodeTexCoord')
        return self._tc.outputs[kind]

    def mapping(self, vec, scale=(1, 1, 1), loc=(0, 0, 0), rot=(0, 0, 0)):
        return self.out(self.node('ShaderNodeMapping', {'Vector': vec, 'Scale': scale,
                                                        'Location': loc, 'Rotation': rot}))

    def noise(self, vec=None, scale=5, detail=4, rough=0.5, distort=0.0, dims='3D', out='Fac',
              ntype='FBM', lac=2.0):
        n = self.node('ShaderNodeTexNoise', {'Scale': scale, 'Detail': detail, 'Roughness': rough,
                                             'Distortion': distort, 'Lacunarity': lac},
                      noise_dimensions=dims, noise_type=ntype)
        if vec is not None:
            self.set(n, 'Vector', vec)
        return n.outputs[out]

    def voronoi(self, vec=None, scale=5, feature='F1', dist='EUCLIDEAN', out='Distance', rand=1.0):
        n = self.node('ShaderNodeTexVoronoi', {'Scale': scale, 'Randomness': rand},
                      feature=feature, distance=dist)
        if vec is not None:
            self.set(n, 'Vector', vec)
        return _sock(n.outputs, out)

    def wave(self, vec=None, scale=5, distort=4, detail=3, dscale=1, wtype='BANDS', direction='X',
             profile='SIN', out='Fac', phase=0.0):
        n = self.node('ShaderNodeTexWave', {'Scale': scale, 'Distortion': distort, 'Detail': detail,
                                            'Detail Scale': dscale, 'Phase Offset': phase},
                      wave_type=wtype, bands_direction=direction, wave_profile=profile)
        if vec is not None:
            self.set(n, 'Vector', vec)
        return n.outputs[out]

    def ramp(self, fac, stops, interp='LINEAR'):
        """stops: list of (pos, (r,g,b)) or (pos, value)."""
        n = self.node('ShaderNodeValToRGB')
        self.set(n, 'Fac', fac)
        cr = n.color_ramp
        cr.interpolation = interp
        while len(cr.elements) < len(stops):
            cr.elements.new(0.5)
        for el, (p, c) in zip(cr.elements, stops):
            el.position = p
            if isinstance(c, (int, float)):
                c = (c, c, c)
            el.color = (*c, 1.0)
        return n.outputs['Color']

    def mix(self, fac, a, b, blend='MIX', clamp=True):
        n = self.node('ShaderNodeMix', data_type='RGBA', blend_type=blend, clamp_result=clamp)
        self.set(n, 0, fac)
        self.set(n, 6, a)
        self.set(n, 7, b)
        return n.outputs[2]

    def mixf(self, fac, a, b):
        n = self.node('ShaderNodeMix', data_type='FLOAT')
        self.set(n, 0, fac)
        self.set(n, 2, a)
        self.set(n, 3, b)
        return n.outputs[0]

    def math(self, op, a, b=0.0, clamp=False):
        n = self.node('ShaderNodeMath', operation=op, use_clamp=clamp)
        self.set(n, 0, a)
        self.set(n, 1, b)
        return n.outputs[0]

    def bump(self, height, strength=0.2, distance=0.01, normal=None):
        n = self.node('ShaderNodeBump', {'Strength': strength, 'Distance': distance, 'Height': height})
        if normal is not None:
            self.set(n, 'Normal', normal)
        return n.outputs['Normal']

    def sep(self, vec):
        n = self.node('ShaderNodeSeparateXYZ', {'Vector': vec})
        return n.outputs

    def bsdf(self, **kw):
        """Principled BSDF; keyword names use underscores (base_color -> 'Base Color')."""
        n = self.nt.nodes.get('Principled BSDF') or self.nt.nodes.new('ShaderNodeBsdfPrincipled')
        n.location = (300, 0)
        for k, v in kw.items():
            name = k.replace('_', ' ').title().replace('Ior', 'IOR')
            self.set(n, name, v)
        return n

    def output(self):
        return self.nt.nodes.get('Material Output') or self.nt.nodes.new('ShaderNodeOutputMaterial')


def new_material(name):
    m = bpy.data.materials.get(name)
    if m:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new(name)
    m.use_nodes = True if hasattr(m, 'use_nodes') else None
    return m, ShaderBuilder(m.node_tree)

# --------------------------------------------------------------------------
# Animation (Blender 4.4+/5.x layered actions)
# --------------------------------------------------------------------------

def fcurve(idb, path, index=0):
    ad = idb.animation_data or idb.animation_data_create()
    if ad.action is None:
        ad.action = bpy.data.actions.new(f"{idb.name}_Action")
    act = ad.action
    if ad.action_slot is None:
        slot = act.slots.new(id_type=idb.id_type, name=idb.name)
        ad.action_slot = slot
    cb = anim_utils.action_ensure_channelbag_for_slot(act, ad.action_slot)
    fc = cb.fcurves.find(path, index=index)
    if fc is None:
        fc = cb.fcurves.new(path, index=index)
    return fc


def key(idb, path, index, frame, value, interp='BEZIER', handle='AUTO_CLAMPED', easing='AUTO'):
    fc = fcurve(idb, path, index)
    kp = fc.keyframe_points.insert(frame, value, options={'FAST'})
    kp.interpolation = interp
    kp.handle_left_type = handle
    kp.handle_right_type = handle
    kp.easing = easing
    return fc


def keys(idb, path, index, pairs, **kw):
    fc = None
    for f, v in pairs:
        fc = key(idb, path, index, f, v, **kw)
    fc.update()
    return fc


def finish_fcurves(idb):
    ad = idb.animation_data
    if ad and ad.action and ad.action_slot:
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        if cb:
            for fc in cb.fcurves:
                fc.update()


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def ease_io(t):
    """smootherstep - gentle cinematic ease-in/out."""
    t = max(0.0, min(1.0, t))
    return t * t * t * (t * (6 * t - 15) + 10)
