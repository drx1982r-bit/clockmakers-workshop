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
import bpy

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
