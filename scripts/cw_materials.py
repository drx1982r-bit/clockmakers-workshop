"""
cw_materials.py - fully procedural PBR materials.

No image textures are required: every surface detail (wood grain, tarnish,
scratches, enamel crackle, plaster stains...) is computed by shader maths,
so materials stay sharp at any resolution, including 8K close-ups.
"""
import bpy
from cw_util import new_material

M = {}  # name -> material (filled by build_all)


def _reg(m):
    M[m.name] = m
    return m

# ---------------------------------------------------------------- metals

def brass(name, tarnish=0.35, polish=0.22, tint=(0.86, 0.62, 0.30), scale=1.0):
    m, s = new_material(name)
    co = s.coord('Object')
    big = s.noise(s.mapping(co, (scale,) * 3), scale=9, detail=8, rough=0.62)
    fine = s.noise(co, scale=140 * scale, detail=6, rough=0.7)
    ao = s.node('ShaderNodeAmbientOcclusion', {'Distance': 0.015}, samples=8)
    crevice = s.math('SUBTRACT', 1.0, ao.outputs['AO'])
    mask = s.ramp(big, [(0.5 - tarnish * 0.35, 0.0), (0.78 - tarnish * 0.2, 1.0)])
    mask = s.math('MAXIMUM', s.math('MULTIPLY', mask, tarnish * 1.4, clamp=True),
                  s.math('MULTIPLY', crevice, 1.6, clamp=True))
    # brushed micro-scratches: stretched noise
    scratch = s.noise(s.mapping(co, (600 * scale, 20 * scale, 20 * scale)), scale=1.0, detail=2)
    scratch = s.ramp(scratch, [(0.6, 0.0), (0.8, 1.0)])
    clean = tint
    dark = (tint[0] * 0.33, tint[1] * 0.30, tint[2] * 0.22)
    col = s.mix(mask, clean, dark)
    col = s.mix(s.math('MULTIPLY', fine, 0.25), col, (tint[0] * 1.05, tint[1] * 0.95, tint[2] * 0.8),
                'MULTIPLY')
    rough = s.mixf(mask, polish, 0.58)
    rough = s.math('ADD', rough, s.math('MULTIPLY', scratch, 0.05))
    nrm = s.bump(fine, 0.04, 0.002)
    s.bsdf(base_color=col, metallic=1.0, roughness=rough, normal=nrm,
           specular_tint=(1.0, 0.85, 0.6), anisotropic=0.25)
    return _reg(m)


def blued_steel(name='BluedSteel'):
    """Heat-blued steel uses real thin-film interference, like actual clock hands."""
    m, s = new_material(name)
    co = s.coord('Object')
    v = s.noise(co, scale=60, detail=4)
    rough = s.mixf(v, 0.12, 0.22)
    s.bsdf(base_color=(0.30, 0.33, 0.42), metallic=1.0, roughness=rough,
           thin_film_thickness=330.0, thin_film_ior=2.1)
    return _reg(m)


def steel(name='Steel', rough=0.28, col=(0.62, 0.62, 0.63)):
    m, s = new_material(name)
    co = s.coord('Object')
    br = s.noise(s.mapping(co, (800, 8, 8)), scale=1, detail=3)
    r = s.math('ADD', rough, s.math('MULTIPLY', br, 0.15))
    s.bsdf(base_color=col, metallic=1.0, roughness=r, anisotropic=0.6)
    return _reg(m)


def cast_iron(name='CastIron'):
    m, s = new_material(name)
    co = s.coord('Object')
    n = s.noise(co, scale=6, detail=10, rough=0.7)
    rust = s.ramp(n, [(0.58, 0.0), (0.68, 1.0)])
    pit = s.noise(co, scale=300, detail=4)
    col = s.mix(rust, (0.035, 0.035, 0.04), (0.22, 0.08, 0.03))
    s.bsdf(base_color=col, metallic=s.mixf(rust, 0.85, 0.0), roughness=s.mixf(rust, 0.55, 0.92),
           normal=s.bump(s.math('ADD', pit, rust), 0.35, 0.003))
    return _reg(m)


def copper(name='Copper'):
    m, s = new_material(name)
    co = s.coord('Object')
    n = s.noise(co, scale=12, detail=8)
    patina = s.ramp(n, [(0.62, 0.0), (0.72, 1.0)])
    col = s.mix(patina, (0.93, 0.52, 0.36), (0.25, 0.42, 0.33))
    s.bsdf(base_color=col, metallic=s.mixf(patina, 1.0, 0.0), roughness=s.mixf(patina, 0.25, 0.8))
    return _reg(m)


def silver(name='Silver'):
    m, s = new_material(name)
    s.bsdf(base_color=(0.92, 0.92, 0.90), metallic=1.0, roughness=0.12)
    return _reg(m)

# ---------------------------------------------------------------- woods

def wood(name, dark, mid, light, grain_scale=2.5, axis='Z', coat=0.0, rough=0.5, wear=0.2,
         stretch=12.0):
    m, s = new_material(name)
    co = s.coord('Object')
    sc = {'X': (1 / stretch, 1, 1), 'Y': (1, 1 / stretch, 1), 'Z': (1, 1, 1 / stretch)}[axis]
    v = s.mapping(co, sc)
    rings = s.wave(v, scale=grain_scale, distort=7, detail=4, dscale=1.5, wtype='RINGS',
                   profile='SAW')
    fib = s.noise(s.mapping(co, tuple(1 / c * 0.05 for c in sc)), scale=40, detail=6)
    g = s.math('ADD', s.math('MULTIPLY', rings, 0.75), s.math('MULTIPLY', fib, 0.25))
    col = s.ramp(g, [(0.0, dark), (0.45, mid), (1.0, light)])
    blot = s.noise(co, scale=3, detail=6)
    col = s.mix(s.math('MULTIPLY', s.ramp(blot, [(0.4, 0.0), (0.8, 1.0)]), wear),
                col, (0.02, 0.012, 0.006))
    scratches = s.noise(s.mapping(co, (300, 4, 300)), scale=1, detail=1)
    scratches = s.ramp(scratches, [(0.62, 0.0), (0.66, 1.0)])
    r = s.math('ADD', rough, s.math('MULTIPLY', scratches, 0.2))
    nrm = s.bump(s.math('ADD', g, scratches), 0.12, 0.002)
    kw = dict(base_color=col, roughness=r, normal=nrm)
    if coat:
        kw.update(coat_weight=coat, coat_roughness=0.06)
    s.bsdf(**kw)
    return _reg(m)


def floor_planks(name='FloorPlanks'):
    m, s = new_material(name)
    co = s.coord('Object')
    brick = s.node('ShaderNodeTexBrick', {'Vector': co, 'Scale': 1.0, 'Mortar Size': 0.004,
                                          'Mortar Smooth': 0.3, 'Bias': 0.0,
                                          'Brick Width': 1.6, 'Row Height': 0.19,
                                          'Color1': (0.29, 0.16, 0.08), 'Color2': (0.18, 0.09, 0.045),
                                          'Mortar': (0.01, 0.006, 0.004)},
                   offset=0.37, offset_frequency=1, squash=1.0, squash_frequency=1)
    grain = s.wave(s.mapping(co, (0.08, 1, 1)), scale=6, distort=6, detail=5, wtype='BANDS',
                   direction='Y', profile='SAW')
    col = s.mix(s.math('MULTIPLY', grain, 0.55), s.out(brick, 'Color'), (0.05, 0.025, 0.012),
                'MULTIPLY')
    wear = s.noise(co, scale=1.2, detail=8)
    path = s.ramp(wear, [(0.45, 0.0), (0.7, 1.0)])
    col = s.mix(s.math('MULTIPLY', path, 0.35), col, (0.42, 0.30, 0.20))
    dirt = s.noise(co, scale=25, detail=6)
    r = s.mixf(path, 0.32, 0.62)
    r = s.math('ADD', r, s.math('MULTIPLY', dirt, 0.15))
    h = s.math('ADD', s.math('MULTIPLY', s.out(brick, 'Fac'), -1.0), s.math('MULTIPLY', grain, 0.15))
    s.bsdf(base_color=col, roughness=r, normal=s.bump(h, 0.35, 0.004), coat_weight=0.15,
           coat_roughness=0.25)
    return _reg(m)

# ---------------------------------------------------------------- architecture

def plaster(name='Plaster'):
    m, s = new_material(name)
    co = s.coord('Object')
    pos = s.coord('Generated')
    big = s.noise(co, scale=0.8, detail=10, rough=0.65)
    stain = s.ramp(big, [(0.42, 0.0), (0.72, 1.0)])
    z = s.sep(pos)[2]
    low = s.ramp(z, [(0.0, 1.0), (0.35, 0.0)])
    base = s.mix(s.math('MULTIPLY', stain, 0.45), (0.64, 0.56, 0.44), (0.36, 0.29, 0.20))
    base = s.mix(s.math('MULTIPLY', low, 0.4), base, (0.25, 0.20, 0.14))
    fine = s.noise(co, scale=45, detail=8, rough=0.75)
    s.bsdf(base_color=base, roughness=0.88, normal=s.bump(s.math('ADD', fine, big), 0.07, 0.004))
    return _reg(m)


def paint(name, col, rough=0.42, chip=0.0):
    m, s = new_material(name)
    co = s.coord('Object')
    n = s.noise(co, scale=8, detail=10, rough=0.7)
    if chip:
        ch = s.ramp(n, [(0.68 - chip * 0.1, 0.0), (0.70 - chip * 0.1, 1.0)])
        c = s.mix(ch, col, (0.22, 0.14, 0.08))
        r = s.mixf(ch, rough, 0.8)
        nrm = s.bump(ch, 0.3, 0.002)
    else:
        c, r = col, s.math('ADD', rough, s.math('MULTIPLY', n, 0.1))
        nrm = s.bump(s.noise(co, scale=60, detail=4), 0.05, 0.002)
    s.bsdf(base_color=c, roughness=r, normal=nrm)
    return _reg(m)

# ---------------------------------------------------------------- glass / enamel / misc

def glass(name='Glass', rough=0.0, tint=(1.0, 1.0, 1.0), dirty=0.0, ior=1.52, shadow_pass=True):
    m, s = new_material(name)
    if dirty:
        co = s.coord('Object')
        n = s.noise(co, scale=6, detail=8)
        r = s.mixf(s.ramp(n, [(0.5, 0.0), (0.85, 1.0)]), rough, rough + dirty)
    else:
        r = rough
    b = s.bsdf(base_color=tint, roughness=r, transmission_weight=1.0, ior=ior)
    if shadow_pass:
        # light passes through (tinted) for shadow rays: sunlight streams through windows
        # without needing expensive caustics
        lp = s.node('ShaderNodeLightPath')
        tr = s.node('ShaderNodeBsdfTransparent', {'Color': tuple(min(1.0, c * 0.92) for c in tint)})
        mx = s.node('ShaderNodeMixShader')
        s.link(lp.outputs['Is Shadow Ray'], mx.inputs[0])
        s.link(b.outputs[0], mx.inputs[1])
        s.link(tr.outputs[0], mx.inputs[2])
        s.link(mx.outputs[0], s.output().inputs['Surface'])
    # EEVEE (real-time) settings: ray-traced refraction + transparent shadows
    for attr, val in (('use_raytrace_refraction', True), ('use_transparent_shadow', True),
                      ('surface_render_method', 'DITHERED'), ('use_thickness_from_shadow', False)):
        if hasattr(m, attr):
            setattr(m, attr, val)
    return _reg(m)


def enamel(name='Enamel', col=(0.86, 0.82, 0.72)):
    m, s = new_material(name)
    co = s.coord('Object')
    crack = s.voronoi(co, scale=55, feature='DISTANCE_TO_EDGE', out='Distance')
    lines = s.ramp(crack, [(0.0, 1.0), (0.025, 0.0)])
    age = s.noise(co, scale=4, detail=6)
    c = s.mix(s.math('MULTIPLY', lines, 0.35), col, (0.45, 0.36, 0.22))
    c = s.mix(s.math('MULTIPLY', s.ramp(age, [(0.5, 0.0), (0.9, 1.0)]), 0.3), c, (0.7, 0.6, 0.42))
    s.bsdf(base_color=c, roughness=0.25, coat_weight=1.0, coat_roughness=0.02,
           subsurface_weight=0.15, subsurface_radius=(0.01, 0.008, 0.006), subsurface_scale=0.01,
           normal=s.bump(lines, 0.05, 0.001))
    return _reg(m)


def simple(name, col, rough=0.5, metal=0.0, sheen=0.0, coat=0.0):
    m, s = new_material(name)
    kw = dict(base_color=col, roughness=rough, metallic=metal)
    if sheen:
        kw['sheen_weight'] = sheen
    if coat:
        kw['coat_weight'] = coat
    s.bsdf(**kw)
    return _reg(m)


def cloth(name, col, col2=None, pattern=False):
    m, s = new_material(name)
    co = s.coord('Object')
    weave = s.wave(s.mapping(co, (400, 400, 400)), scale=1, distort=0.5, detail=0, wtype='BANDS',
                   direction='DIAGONAL')
    fuzz = s.noise(co, scale=80, detail=6)
    c = col
    if pattern and col2 is not None:
        # simple persian-rug style medallions
        v = s.voronoi(s.mapping(co, (1.0, 1.0, 1.0)), scale=4, feature='F1', dist='CHEBYCHEV')
        w = s.wave(co, scale=9, distort=3, wtype='RINGS')
        p = s.math('MULTIPLY', v, w)
        c = s.ramp(p, [(0.0, col2), (0.25, col), (0.5, (0.75, 0.6, 0.35)), (0.7, col), (1.0, col2)])
    c = s.mix(s.math('MULTIPLY', fuzz, 0.3), c, (0.05, 0.04, 0.03), 'MULTIPLY')
    s.bsdf(base_color=c, roughness=0.92, sheen_weight=0.7, sheen_roughness=0.4,
           normal=s.bump(s.math('ADD', weave, fuzz), 0.25, 0.001))
    return _reg(m)


def leather(name='Leather', col=(0.18, 0.08, 0.035)):
    m, s = new_material(name)
    co = s.coord('Object')
    v = s.voronoi(co, scale=180, feature='SMOOTH_F1')
    n = s.noise(co, scale=5, detail=6)
    c = s.mix(s.math('MULTIPLY', n, 0.5), col, (col[0] * 1.8, col[1] * 1.6, col[2] * 1.4))
    s.bsdf(base_color=c, roughness=s.mixf(n, 0.35, 0.65), normal=s.bump(v, 0.25, 0.001),
           sheen_weight=0.2)
    return _reg(m)


def wax(name='CandleWax'):
    m, s = new_material(name)
    s.bsdf(base_color=(0.93, 0.86, 0.68), roughness=0.38, subsurface_weight=1.0,
           subsurface_radius=(1.0, 0.55, 0.25), subsurface_scale=0.012)
    return _reg(m)


def flame(name='Flame'):
    """Candle flame: blackbody colour graded from blue base to orange tip, soft edges."""
    m, s = new_material(name)
    gen = s.coord('Generated')
    z = s.sep(gen)[2]
    col = s.ramp(z, [(0.0, (0.25, 0.35, 1.0)), (0.12, (1.0, 0.55, 0.15)), (0.55, (1.0, 0.78, 0.38)),
                     (1.0, (1.0, 0.42, 0.08))])
    lw = s.node('ShaderNodeLayerWeight', {'Blend': 0.6})
    facing = s.math('POWER', s.math('SUBTRACT', 1.0, s.out(lw, 'Facing')), 2.5)
    em = s.node('ShaderNodeEmission', {'Color': col, 'Strength': 40.0}, name='FlameEmission')
    tr = s.node('ShaderNodeBsdfTransparent')
    mx = s.node('ShaderNodeMixShader')
    s.set(mx, 'Fac', facing)
    s.link(tr.outputs[0], mx.inputs[1])
    s.link(em.outputs[0], mx.inputs[2])
    bs = s.nt.nodes.get('Principled BSDF')
    s.nt.nodes.remove(bs)
    s.link(mx.outputs[0], s.output().inputs['Surface'])
    return _reg(m)


def emitter(name, col, strength, node_name='Emit'):
    m, s = new_material(name)
    bs = s.nt.nodes.get('Principled BSDF')
    s.nt.nodes.remove(bs)
    em = s.node('ShaderNodeEmission', {'Color': col, 'Strength': strength}, name=node_name)
    s.link(em.outputs[0], s.output().inputs['Surface'])
    return _reg(m)


def glow_glass(name, col, strength, node_name='Emit'):
    """Glass that also glows from within (orrery sun, light bulb)."""
    m, s = new_material(name)
    s.bsdf(base_color=col, roughness=0.1, transmission_weight=0.6, emission_color=col,
           emission_strength=strength)
    s.nt.nodes['Principled BSDF'].name = node_name
    return _reg(m)


def earth_enamel(name='EarthEnamel'):
    m, s = new_material(name)
    co = s.coord('Object')
    n = s.noise(co, scale=28, detail=8, rough=0.6)
    land = s.ramp(n, [(0.52, 0.0), (0.54, 1.0)])
    c = s.mix(land, (0.03, 0.12, 0.42), (0.18, 0.32, 0.10))
    s.bsdf(base_color=c, roughness=0.18, coat_weight=1.0, coat_roughness=0.02)
    return _reg(m)


def jupiter(name='JupiterEnamel'):
    m, s = new_material(name)
    co = s.coord('Object')
    w = s.wave(co, scale=40, distort=6, detail=4, wtype='BANDS', direction='Z')
    c = s.ramp(w, [(0.0, (0.55, 0.38, 0.22)), (0.5, (0.85, 0.72, 0.52)), (1.0, (0.45, 0.25, 0.14))])
    s.bsdf(base_color=c, roughness=0.2, coat_weight=1.0, coat_roughness=0.03)
    return _reg(m)


def paper(name, col=(0.82, 0.76, 0.62), image=None):
    m, s = new_material(name)
    co = s.coord('Object')
    fib = s.noise(co, scale=300, detail=6)
    if image is not None:
        tex = s.node('ShaderNodeTexImage', {'Vector': s.coord('UV')}, image=image)
        c = s.out(tex, 'Color')
    else:
        c = s.mix(s.math('MULTIPLY', fib, 0.2), col, (col[0] * 0.8, col[1] * 0.75, col[2] * 0.7))
    s.bsdf(base_color=c, roughness=0.85, normal=s.bump(fib, 0.08, 0.0005), sheen_weight=0.2)
    return _reg(m)


def dust_mote(name='DustMote'):
    m, s = new_material(name)
    bs = s.nt.nodes.get('Principled BSDF')
    s.nt.nodes.remove(bs)
    d = s.node('ShaderNodeBsdfDiffuse', {'Color': (0.9, 0.85, 0.75)})
    t = s.node('ShaderNodeBsdfTranslucent', {'Color': (1.0, 0.9, 0.75)})
    mx = s.node('ShaderNodeMixShader', {'Fac': 0.6})
    s.link(d.outputs[0], mx.inputs[1])
    s.link(t.outputs[0], mx.inputs[2])
    s.link(mx.outputs[0], s.output().inputs['Surface'])
    return _reg(m)


def room_fog(name='RoomFog', density=0.075):
    """Volumetric haze: makes the window light visible as god-rays."""
    m, s = new_material(name)
    bs = s.nt.nodes.get('Principled BSDF')
    s.nt.nodes.remove(bs)
    co = s.coord('Object')
    n = s.noise(co, scale=1.4, detail=3, rough=0.5)
    d = s.ramp(n, [(0.3, 0.45), (0.75, 1.5)])
    dens = s.node('ShaderNodeMath', operation='MULTIPLY', name='FogDensity')
    s.set(dens, 0, s.sep(d)[0] if False else d)
    s.set(dens, 1, density)
    vol = s.node('ShaderNodeVolumePrincipled', {'Color': (0.92, 0.88, 0.80), 'Anisotropy': 0.62,
                                                'Density': s.out(dens)})
    s.link(vol.outputs[0], s.output().inputs['Volume'])
    return _reg(m)


def sky_backdrop(name='DuskSky'):
    """Painted dusk sky seen through the windows (emissive gradient)."""
    m, s = new_material(name)
    bs = s.nt.nodes.get('Principled BSDF')
    s.nt.nodes.remove(bs)
    gen = s.coord('Generated')
    z = s.sep(gen)[2]
    clouds = s.noise(s.mapping(s.coord('Object'), (0.15, 0.6, 1.0)), scale=0.6, detail=8, rough=0.55)
    cl = s.ramp(clouds, [(0.5, 0.0), (0.72, 1.0)])
    col = s.ramp(z, [(0.0, (1.0, 0.36, 0.10)), (0.22, (1.0, 0.55, 0.22)), (0.42, (0.85, 0.48, 0.38)),
                     (0.65, (0.32, 0.26, 0.42)), (1.0, (0.08, 0.09, 0.22))])
    col = s.mix(s.math('MULTIPLY', cl, 0.55), col, (1.0, 0.45, 0.3), 'SCREEN')
    em = s.node('ShaderNodeEmission', {'Color': col, 'Strength': 3.0}, name='SkyEmission')
    s.link(em.outputs[0], s.output().inputs['Surface'])
    return _reg(m)


def silhouette(name='RooftopSilhouette'):
    """Distant rooftops with a few warmly lit windows."""
    m, s = new_material(name)
    co = s.coord('Object')
    brick = s.node('ShaderNodeTexBrick', {'Vector': co, 'Scale': 1.0, 'Mortar Size': 0.35,
                                          'Brick Width': 0.9, 'Row Height': 1.3,
                                          'Color1': (1, 1, 1), 'Color2': (0, 0, 0),
                                          'Mortar': (0, 0, 0)}, offset=0.0)
    rnd = s.noise(s.mapping(co, (0.7, 0.7, 0.7)), scale=2.0, detail=0)
    lit = s.math('MULTIPLY', s.out(brick, 'Color'), s.ramp(rnd, [(0.55, 0.0), (0.56, 1.0)]))
    bsdf = s.bsdf(base_color=(0.012, 0.01, 0.014), roughness=0.9, emission_color=(1.0, 0.62, 0.28),
                  emission_strength=s.math('MULTIPLY', s.sep(lit)[0] if False else lit, 6.0))
    return _reg(m)


def velvet(name='Velvet', col=(0.28, 0.02, 0.03)):
    m, s = new_material(name)
    s.bsdf(base_color=col, roughness=1.0, sheen_weight=1.0, sheen_roughness=0.3,
           sheen_tint=(1.0, 0.6, 0.6))
    return _reg(m)


def perlage(name='PerlageBrass'):
    """Circular-graining (perlage) finish used on fine clock movement plates."""
    m, s = new_material(name)
    co = s.coord('Object')
    v = s.voronoi(s.mapping(co, (1, 1, 1)), scale=90, feature='F1', out='Distance', rand=0.0)
    swirl = s.wave(s.mapping(co, (90, 90, 90)), scale=6, distort=0, wtype='RINGS')
    r = s.mixf(s.math('MULTIPLY', v, 2.0, clamp=True), 0.12, 0.35)
    s.bsdf(base_color=(0.88, 0.70, 0.40), metallic=1.0, roughness=r, anisotropic=0.7,
           anisotropic_rotation=swirl)
    return _reg(m)

# ---------------------------------------------------------------- build all

def build_all(blueprint_img=None):
    brass('BrassAged', tarnish=0.45, polish=0.25)
    brass('BrassPolished', tarnish=0.12, polish=0.12)
    brass('BrassGear', tarnish=0.25, polish=0.18, scale=3.0)
    brass('BrassDark', tarnish=0.8, polish=0.35, tint=(0.75, 0.52, 0.26))
    blued_steel()
    steel()
    steel('SteelDark', rough=0.35, col=(0.25, 0.25, 0.27))
    cast_iron()
    copper()
    silver()
    perlage()
    wood('Walnut', (0.045, 0.022, 0.012), (0.15, 0.075, 0.035), (0.30, 0.15, 0.07), grain_scale=3,
         axis='Z', coat=0.7, rough=0.42, wear=0.15)
    wood('WalnutH', (0.045, 0.022, 0.012), (0.15, 0.075, 0.035), (0.30, 0.15, 0.07), grain_scale=3,
         axis='X', coat=0.7, rough=0.42, wear=0.15)
    wood('Oak', (0.13, 0.075, 0.035), (0.30, 0.19, 0.10), (0.46, 0.31, 0.17), grain_scale=2,
         axis='X', coat=0.0, rough=0.55, wear=0.45)
    wood('OakV', (0.13, 0.075, 0.035), (0.30, 0.19, 0.10), (0.46, 0.31, 0.17), grain_scale=2,
         axis='Z', coat=0.0, rough=0.55, wear=0.35)
    wood('Beech', (0.35, 0.2, 0.1), (0.55, 0.36, 0.2), (0.7, 0.5, 0.3), axis='Z', coat=0.5,
         rough=0.4, wear=0.1)
    wood('OldTimber', (0.03, 0.018, 0.01), (0.08, 0.05, 0.028), (0.14, 0.09, 0.05), grain_scale=1.5,
         axis='X', rough=0.75, wear=0.5)
    wood('Mahogany', (0.06, 0.015, 0.008), (0.20, 0.06, 0.03), (0.32, 0.11, 0.05), axis='Z',
         coat=0.8, rough=0.35, wear=0.1)
    floor_planks()
    plaster()
    paint('PaintGreen', (0.035, 0.09, 0.065), rough=0.45, chip=0.6)
    paint('PaintCream', (0.62, 0.56, 0.44), rough=0.5, chip=0.8)
    paint('PaintBlack', (0.015, 0.015, 0.015), rough=0.3)
    paint('ShadeGreen', (0.02, 0.16, 0.08), rough=0.22)
    paint('ShadeInner', (0.85, 0.82, 0.74), rough=0.35)
    glass('Glass')
    glass('LensGlass', shadow_pass=False)
    glass('WindowGlass', rough=0.02, tint=(0.92, 0.97, 0.94), dirty=0.08)
    glass('BottleGlass', rough=0.05, tint=(0.55, 0.42, 0.18))
    glass('JarGlass', rough=0.02, tint=(0.85, 0.95, 0.92))
    enamel()
    enamel('EnamelIvory', (0.80, 0.72, 0.56))
    simple('Sand', (0.75, 0.6, 0.38), rough=0.95)
    simple('BlackLacquer', (0.01, 0.01, 0.01), rough=0.15, coat=1.0)
    simple('Rubber', (0.02, 0.02, 0.02), rough=0.8)
    cloth('Rug', (0.38, 0.05, 0.04), (0.04, 0.05, 0.16), pattern=True)
    cloth('BookRed', (0.30, 0.04, 0.03))
    cloth('BookGreen', (0.04, 0.16, 0.08))
    cloth('BookBlue', (0.04, 0.06, 0.20))
    cloth('BookBrown', (0.22, 0.12, 0.05))
    cloth('BookOchre', (0.45, 0.30, 0.08))
    leather()
    velvet()
    wax()
    flame()
    emitter('BulbFilament', (1.0, 0.55, 0.22), 60.0, 'BulbEmit')
    emitter('SunDiscGlow', (1.0, 0.62, 0.32), 30.0, 'SunDiscEmit')
    glow_glass('OrrerySun', (1.0, 0.45, 0.10), 0.0, 'SunEmit')
    earth_enamel()
    jupiter()
    simple('MarsEnamel', (0.45, 0.10, 0.04), rough=0.2, coat=1.0)
    simple('VenusEnamel', (0.85, 0.75, 0.50), rough=0.2, coat=1.0)
    simple('IvoryBall', (0.82, 0.78, 0.66), rough=0.25, coat=0.6)
    paper('Paper')
    paper('Blueprint', image=blueprint_img) if blueprint_img else paper('Blueprint', (0.1, 0.2, 0.45))
    dust_mote()
    room_fog()
    sky_backdrop()
    silhouette()
    return M
