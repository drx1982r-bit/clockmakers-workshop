"""
cw_compositor.py - professional colour grade (Blender 5.x compositor node group).

Render -> Bloom glare -> subtle lens dispersion -> colour balance
(teal shadows / warm highlights) -> gentle S-curve -> vignette -> output
"""
import bpy


def _set(node, name, value):
    for s in node.inputs:
        if s.name == name:
            try:
                s.default_value = value
                return
            except (TypeError, ValueError):
                continue


def build(sc, strength=1.0):
    ng = bpy.data.node_groups.get("CW_Grade")
    if ng:
        bpy.data.node_groups.remove(ng)
    ng = bpy.data.node_groups.new("CW_Grade", "CompositorNodeTree")
    ng.interface.new_socket("Image", in_out='OUTPUT', socket_type='NodeSocketColor')
    N, Lk = ng.nodes, ng.links
    rl = N.new("CompositorNodeRLayers"); rl.location = (-1200, 0)
    gl = N.new("CompositorNodeGlare"); gl.location = (-950, 0); gl.name = "Bloom"
    _set(gl, 'Type', 'Bloom'); _set(gl, 'Quality', 'High'); _set(gl, 'Threshold', 1.2)
    _set(gl, 'Smoothness', 0.3); _set(gl, 'Strength', 0.18); _set(gl, 'Size', 0.75)
    _set(gl, 'Saturation', 1.0)
    ld = N.new("CompositorNodeLensdist"); ld.location = (-750, 0); ld.name = "Lens"
    _set(ld, 'Distortion', -0.004); _set(ld, 'Dispersion', 0.006); _set(ld, 'Fit', True)
    cb = N.new("CompositorNodeColorBalance"); cb.location = (-550, 0); cb.name = "Grade"
    _set(cb, 'Type', 'Lift/Gamma/Gain')
    for s in cb.inputs:
        if s.type == 'RGBA':
            if s.name == 'Lift':
                s.default_value = (0.985, 1.0, 1.02, 1)
            elif s.name == 'Gamma':
                s.default_value = (1.0, 0.995, 0.985, 1)
            elif s.name == 'Gain':
                s.default_value = (1.04, 1.0, 0.95, 1)
    _set(cb, 'Factor', strength)
    cv = N.new("CompositorNodeCurveRGB"); cv.location = (-350, 0); cv.name = "Contrast"
    c = cv.mapping.curves[3]
    c.points[0].location = (0.0, 0.0)
    c.points[1].location = (1.0, 1.0)
    c.points.new(0.25, 0.22)
    c.points.new(0.75, 0.78)
    cv.mapping.update()
    em = N.new("CompositorNodeEllipseMask"); em.location = (-350, -300); em.name = "VignetteMask"
    _set(em, 'Size', (0.92, 0.82)); _set(em, 'Value', 1.0)
    bl = N.new("CompositorNodeBlur"); bl.location = (-150, -300); bl.name = "VignetteSoft"
    _set(bl, 'Size', (220.0, 220.0)); _set(bl, 'Type', 'Fast Gaussian')
    rel = N.new("CompositorNodeRelativeToPixel") if hasattr(bpy.types, 'CompositorNodeRelativeToPixel') else None
    mx = N.new("ShaderNodeMix"); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'; mx.location = (50, 0)
    mx.name = "Vignette"
    mx.inputs[0].default_value = 0.38 * strength
    out = N.new("NodeGroupOutput"); out.location = (300, 0)
    Lk.new(rl.outputs['Image'], gl.inputs['Image'])
    Lk.new(gl.outputs['Image'], ld.inputs['Image'])
    Lk.new(ld.outputs['Image'], cb.inputs['Image'])
    Lk.new(cb.outputs['Image'], cv.inputs['Image'])
    Lk.new(cv.outputs['Image'], mx.inputs[6])
    # vignette: mask is white inside -> invert via mix A=dark/B=white handled with blur of mask
    Lk.new(em.outputs['Mask'], bl.inputs['Image'])
    inv = N.new("CompositorNodeInvert"); inv.location = (-150, -450)
    # we want B = mask (white centre, dark edges)
    Lk.new(bl.outputs['Image'], mx.inputs[7])
    N.remove(inv)
    if rel:
        N.remove(rel)
    Lk.new(mx.outputs[2], out.inputs[0])
    sc.compositing_node_group = ng
    sc.render.use_compositing = True
    return ng
