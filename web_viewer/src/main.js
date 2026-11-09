// The Clockmaker's Workshop at Dusk - interactive browser version
// Bundled into ../viewer.js (npm run build). Data comes from data/scene_data.js (window.CW_DATA).
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { BokehPass } from 'three/addons/postprocessing/BokehPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { RectAreaLightUniformsLib } from 'three/addons/lights/RectAreaLightUniformsLib.js';

const D = window.CW_DATA;
const EV = D.events;
const CAMS = D.cameras;
const FPS = EV.fps, FRAME_END = EV.frame_end, DURATION = (FRAME_END - 1) / FPS;
const $ = (id) => document.getElementById(id);
const B2T = (x, y, z) => new THREE.Vector3(x, z, -y);           // Blender (Z-up) -> three (Y-up)
const SUN_DIR = B2T(1.0, -0.42, -0.40).normalize();
const WINDOWS = [{ y: -0.6, w: 1.1 }, { y: 1.5, w: 1.1 }];
const SILL = 0.85, TOP = 2.75, WALL_X = -3.5;

// ------------------------------------------------------------------ quality presets
const QUALITY = {
  low:    { pr: 0.75, shadow: 1024, bloom: false, dof: false, transmission: false, dust: 500,  softShadows: false, extraShadows: false },
  medium: { pr: 1.0,  shadow: 2048, bloom: true,  dof: false, transmission: false, dust: 1200, softShadows: true,  extraShadows: false },
  high:   { pr: 1.5,  shadow: 2048, bloom: true,  dof: true,  transmission: true,  dust: 2000, softShadows: true,  extraShadows: true },
  ultra:  { pr: 2.0,  shadow: 4096, bloom: true,  dof: true,  transmission: true,  dust: 3200, softShadows: true,  extraShadows: true },
};
let Q = QUALITY[localGet('cw_quality') || 'high'] ? (localGet('cw_quality') || 'high') : 'high';

function localGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
function localSet(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* storage unavailable */ } }

// ------------------------------------------------------------------ renderer / scene
const canvas = $('view');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.AgXToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
RectAreaLightUniformsLib.init();

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x050403);
scene.fog = new THREE.FogExp2(0x2a1a0e, 0.022);
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.1;

const camera = new THREE.PerspectiveCamera(40, 16 / 9, 0.01, 80);
camera.position.set(2.9, 1.3, 2.7);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.minDistance = 0.05;
controls.maxDistance = 9;
controls.target.set(-0.6, 1.1, -0.6);
controls.enabled = false;

// ------------------------------------------------------------------ procedural textures
function hash(x, y, s) { const h = Math.sin(x * 127.1 + y * 311.7 + s * 74.7) * 43758.5453; return h - Math.floor(h); }
function vnoise(x, y, s) {
  const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
  const a = hash(xi, yi, s), b = hash(xi + 1, yi, s), c = hash(xi, yi + 1, s), d = hash(xi + 1, yi + 1, s);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}
function fbm(x, y, oct = 5, s = 0) { let v = 0, a = 0.5, f = 1; for (let i = 0; i < oct; i++) { v += a * vnoise(x * f, y * f, s + i); f *= 2; a *= 0.5; } return v; }

function canvasTex(size, fn, srgb = true, repeat = 1) {
  const c = document.createElement('canvas'); c.width = c.height = size;
  const ctx = c.getContext('2d'); const img = ctx.createImageData(size, size); const d = img.data;
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const [r, g, b] = fn(x / size, y / size); const i = (y * size + x) * 4;
    d[i] = r * 255; d[i + 1] = g * 255; d[i + 2] = b * 255; d[i + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(repeat, repeat);
  t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  t.anisotropy = 8;
  return t;
}
const mixc = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
const clamp01 = (v) => Math.max(0, Math.min(1, v));

function woodTex(dark, light, rings = 9, seed = 1) {
  return canvasTex(512, (u, v) => {
    const n = fbm(u * 3, v * 0.6, 4, seed);
    const r = (Math.sin((u * rings + n * 4) * Math.PI * 2) + 1) / 2;
    const fib = fbm(u * 60, v * 4, 3, seed + 5);
    return mixc(dark, light, clamp01(r * 0.65 + fib * 0.35));
  });
}
const TEX = {};
function buildTextures() {
  const S = (h) => { const c = new THREE.Color(h); c.convertLinearToSRGB(); return [c.r, c.g, c.b]; };
  TEX.walnut = woodTex([0.12, 0.06, 0.03], [0.38, 0.2, 0.1], 7, 2);
  TEX.oak = woodTex([0.3, 0.19, 0.1], [0.62, 0.45, 0.27], 5, 3);
  TEX.mahogany = woodTex([0.16, 0.05, 0.03], [0.45, 0.17, 0.08], 8, 4);
  TEX.timber = woodTex([0.08, 0.05, 0.03], [0.22, 0.14, 0.08], 4, 5);
  TEX.floor = canvasTex(1024, (u, v) => {
    const row = Math.floor(v * 5.2), off = (row * 0.37) % 1, plank = Math.floor(u * 0.62 + off);
    const tint = hash(row, plank, 9) * 0.35;
    const seam = (v * 5.2) % 1 < 0.02 || ((u * 0.62 + off) % 1) < 0.004 ? 0.25 : 1;
    const grain = fbm(u * 1.5, v * 40, 4, row) * 0.5 + 0.5;
    const wear = fbm(u * 2, v * 2, 4, 11);
    let c = mixc([0.36, 0.2, 0.1], [0.24, 0.12, 0.06], tint);
    c = mixc(c, [0.5, 0.36, 0.24], clamp01((wear - 0.5) * 2) * 0.4);
    return c.map((x) => x * seam * (0.75 + grain * 0.4));
  }, true, 1);
  TEX.plaster = canvasTex(512, (u, v) => {
    const n = fbm(u * 4, v * 4, 6, 21), f = fbm(u * 40, v * 40, 3, 22);
    const c = mixc([0.66, 0.58, 0.46], [0.55, 0.46, 0.35], clamp01((n - 0.4) * 1.4));
    return c.map((x) => x * (0.9 + f * 0.2));
  });
  TEX.rug = canvasTex(512, (u, v) => {
    const cx = (u * 3) % 1 - 0.5, cy = (v * 2) % 1 - 0.5;
    const r = Math.max(Math.abs(cx), Math.abs(cy)), ring = (Math.sin(r * 40) + 1) / 2;
    const border = (u < 0.06 || u > 0.94 || v < 0.08 || v > 0.92) ? 1 : 0;
    let c = mixc([0.45, 0.07, 0.05], [0.07, 0.08, 0.25], ring * 0.7);
    if (border) c = [0.75, 0.6, 0.35];
    const fz = fbm(u * 80, v * 80, 2, 3);
    return c.map((x) => x * (0.8 + fz * 0.3));
  }, true, 0.4);
  TEX.noise = canvasTex(256, (u, v) => { const n = fbm(u * 8, v * 8, 5, 31); return [n, n, n]; }, false, 4);
  TEX.earth = canvasTex(256, (u, v) => (fbm(u * 6, v * 6, 5, 41) > 0.52 ? [0.25, 0.38, 0.14] : [0.05, 0.16, 0.5]));
  TEX.jupiter = canvasTex(256, (u, v) => mixc([0.62, 0.45, 0.28], [0.9, 0.78, 0.6], (Math.sin(v * 40 + fbm(u * 4, v * 4) * 6) + 1) / 2));
  TEX.houses = canvasTex(256, (u, v) => {
    const wx = (u * 6) % 1, wy = (v * 5) % 1, lit = hash(Math.floor(u * 6), Math.floor(v * 5), 7) > 0.72;
    return (wx > 0.3 && wx < 0.7 && wy > 0.3 && wy < 0.75 && lit) ? [1.0, 0.65, 0.3] : [0.012, 0.01, 0.014];
  }, true, 1);
}

// ------------------------------------------------------------------ materials by name
const animatedMats = {};
function physical(p) { return new THREE.MeshPhysicalMaterial(p); }
function makeMaterial(name, orig) {
  const n = name.replace(/\.\d+$/, '');
  const q = QUALITY[Q];
  const brass = (rough, col = 0xc9944a) => physical({ color: col, metalness: 1, roughness: rough, roughnessMap: TEX.noise, envMapIntensity: 1.2 });
  const glassMat = (tint = 0xffffff, rough = 0.03) => q.transmission
    ? physical({ color: tint, metalness: 0, roughness: rough, transmission: 1, thickness: 0.004, ior: 1.5, transparent: true, envMapIntensity: 1.5 })
    : physical({ color: tint, metalness: 0, roughness: 0.04, transparent: true, opacity: 0.07, envMapIntensity: 2.0, depthWrite: false });
  const wood = (tex, rough, coat = 0, rep = 2) => { const t = tex.clone(); t.repeat.set(rep, rep); t.needsUpdate = true; return physical({ map: t, roughness: rough, clearcoat: coat, clearcoatRoughness: 0.1 }); };
  switch (true) {
    case /^BrassPolished/.test(n): return brass(0.18, 0xd8a656);
    case /^BrassGear/.test(n): return brass(0.24, 0xcd9a4e);
    case /^BrassDark/.test(n): return brass(0.45, 0x7a5426);
    case /^Brass/.test(n): return brass(0.34, 0xb98a44);
    case /^PerlageBrass/.test(n): return physical({ color: 0xdcb065, metalness: 1, roughness: 0.25, anisotropy: 0.6, roughnessMap: TEX.noise });
    case /^BluedSteel/.test(n): return physical({ color: 0x4a5c8c, metalness: 1, roughness: 0.18, iridescence: 1, iridescenceIOR: 2.1, iridescenceThicknessRange: [290, 340] });
    case /^SteelDark/.test(n): return physical({ color: 0x3a3a3e, metalness: 1, roughness: 0.35 });
    case /^Steel/.test(n): return physical({ color: 0xa8a8aa, metalness: 1, roughness: 0.28 });
    case /^Silver/.test(n): return physical({ color: 0xeeeeea, metalness: 1, roughness: 0.12 });
    case /^Copper/.test(n): return physical({ color: 0xe48a5e, metalness: 1, roughness: 0.3, roughnessMap: TEX.noise });
    case /^CastIron/.test(n): return physical({ color: 0x252527, metalness: 0.7, roughness: 0.65, roughnessMap: TEX.noise });
    case /^Walnut/.test(n): return wood(TEX.walnut, 0.4, 0.7, 2);
    case /^Mahogany/.test(n): return wood(TEX.mahogany, 0.38, 0.8, 2);
    case /^Oak/.test(n): return wood(TEX.oak, 0.6, 0, 1.5);
    case /^Beech/.test(n): return wood(TEX.oak, 0.4, 0.5, 6);
    case /^OldTimber/.test(n): return wood(TEX.timber, 0.75, 0, 1);
    case /^FloorPlanks/.test(n): return physical({ map: TEX.floor, roughness: 0.55, roughnessMap: TEX.noise, clearcoat: 0.15, clearcoatRoughness: 0.3 });
    case /^Plaster/.test(n): { const t = TEX.plaster.clone(); t.repeat.set(0.5, 0.5); t.needsUpdate = true; return physical({ map: t, roughness: 0.92 }); }
    case /^PaintGreen/.test(n): return physical({ color: 0x163a2b, roughness: 0.5 });
    case /^PaintCream/.test(n): return physical({ color: 0xc8b896, roughness: 0.55 });
    case /^PaintBlack/.test(n): return physical({ color: 0x080808, roughness: 0.3 });
    case /^ShadeGreen/.test(n): return physical({ color: 0x0f5a30, roughness: 0.2, clearcoat: 1, side: THREE.DoubleSide });
    case /^ShadeInner/.test(n): return physical({ color: 0xece4cf, roughness: 0.4, side: THREE.DoubleSide });
    case /^WindowGlass/.test(n): return glassMat(0xf0faf4, 0.05);
    case /^BottleGlass/.test(n): return glassMat(0xb08a3c, 0.05);
    case /^(Glass|JarGlass|LensGlass)/.test(n): return glassMat(0xffffff, 0.02);
    case /^EnamelIvory/.test(n): return physical({ color: 0xe0d0aa, roughness: 0.25, clearcoat: 1, clearcoatRoughness: 0.03 });
    case /^Enamel/.test(n): return physical({ color: 0xf0e8d6, roughness: 0.25, clearcoat: 1, clearcoatRoughness: 0.03 });
    case /^Velvet/.test(n): return physical({ color: 0x5c0a0e, roughness: 1, sheen: 1, sheenColor: 0xff8888, sheenRoughness: 0.35 });
    case /^Rug/.test(n): return physical({ map: TEX.rug, roughness: 0.95, sheen: 0.6, sheenColor: 0xffd0b0 });
    case /^BookRed/.test(n): return physical({ color: 0x6a120c, roughness: 0.9, sheen: 0.5 });
    case /^BookGreen/.test(n): return physical({ color: 0x14462a, roughness: 0.9, sheen: 0.5 });
    case /^BookBlue/.test(n): return physical({ color: 0x18204e, roughness: 0.9, sheen: 0.5 });
    case /^BookBrown/.test(n): return physical({ color: 0x5c3418, roughness: 0.9, sheen: 0.5 });
    case /^BookOchre/.test(n): return physical({ color: 0x9a6c20, roughness: 0.9, sheen: 0.5 });
    case /^Leather/.test(n): return physical({ color: 0x4a2410, roughness: 0.5, roughnessMap: TEX.noise });
    case /^CandleWax/.test(n): return physical({ color: 0xf2e2b8, roughness: 0.4, emissive: 0x3a2008, emissiveIntensity: 0.6 });
    case /^Flame/.test(n): { const m = new THREE.MeshBasicMaterial({ color: 0xffb050, transparent: true, opacity: 0.95, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }); m.color.multiplyScalar(4); animatedMats.flame = m; return m; }
    case /^BulbFilament/.test(n): { const m = physical({ color: 0x000000, emissive: 0xffaa55, emissiveIntensity: 0 }); animatedMats.bulb = m; return m; }
    case /^SunDiscGlow/.test(n): { const m = new THREE.MeshBasicMaterial({ color: 0xffb070, fog: false, toneMapped: false }); m.color.multiplyScalar(6); return m; }
    case /^OrrerySun/.test(n): { const m = physical({ color: 0xffa040, emissive: 0xff7a1a, emissiveIntensity: 0, roughness: 0.15, transmission: 0.0 }); animatedMats.orrery = m; return m; }
    case /^EarthEnamel/.test(n): return physical({ map: TEX.earth, roughness: 0.2, clearcoat: 1 });
    case /^JupiterEnamel/.test(n): return physical({ map: TEX.jupiter, roughness: 0.2, clearcoat: 1 });
    case /^MarsEnamel/.test(n): return physical({ color: 0x8a2410, roughness: 0.2, clearcoat: 1 });
    case /^VenusEnamel/.test(n): return physical({ color: 0xe8d090, roughness: 0.2, clearcoat: 1 });
    case /^IvoryBall/.test(n): return physical({ color: 0xe0d8c0, roughness: 0.25, clearcoat: 0.6 });
    case /^Sand/.test(n): return physical({ color: 0xc89a5c, roughness: 0.95 });
    case /^BlackLacquer/.test(n): return physical({ color: 0x050505, roughness: 0.15, clearcoat: 1 });
    case /^Rubber/.test(n): return physical({ color: 0x080808, roughness: 0.8 });
    case /^Paper/.test(n): return physical({ color: 0xd8c8a0, roughness: 0.85 });
    case /^Blueprint/.test(n): return orig && orig.map ? physical({ map: orig.map, roughness: 0.85 }) : physical({ color: 0x1f3a7a, roughness: 0.85 });
    case /^DuskSky/.test(n): return skyMaterial();
    case /^RooftopSilhouette/.test(n): return new THREE.MeshBasicMaterial({ map: TEX.houses, fog: false });
    default: return orig || physical({ color: 0x888888 });
  }
}

function skyMaterial() {
  const m = new THREE.ShaderMaterial({
    fog: false, uniforms: { uStrength: { value: 1.0 } },
    vertexShader: 'varying vec3 vW; void main(){ vec4 w = modelMatrix*vec4(position,1.0); vW = w.xyz; gl_Position = projectionMatrix*viewMatrix*w; }',
    fragmentShader: `uniform float uStrength; varying vec3 vW;
      void main(){ float h = clamp((vW.y + 3.0) / 22.0, 0.0, 1.0);
        vec3 c = mix(vec3(1.0,0.42,0.12), vec3(1.0,0.6,0.3), smoothstep(0.0,0.2,h));
        c = mix(c, vec3(0.75,0.45,0.42), smoothstep(0.2,0.4,h));
        c = mix(c, vec3(0.28,0.24,0.42), smoothstep(0.4,0.65,h));
        c = mix(c, vec3(0.06,0.07,0.18), smoothstep(0.65,1.0,h));
        gl_FragColor = vec4(c * 1.6 * uStrength, 1.0);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
  });
  animatedMats.sky = m;
  return m;
}

// ------------------------------------------------------------------ lights
const lights = {};
function buildLights() {
  const sun = new THREE.DirectionalLight(0xffb070, 11.0);
  sun.position.copy(SUN_DIR).multiplyScalar(-12).add(new THREE.Vector3(-1, 1, 0));
  sun.target.position.set(-1, 1, 0);
  sun.castShadow = true;
  const sc = sun.shadow.camera; sc.left = -6; sc.right = 6; sc.top = 6; sc.bottom = -6; sc.near = 1; sc.far = 30;
  sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.02;
  scene.add(sun, sun.target); lights.sun = sun;
  lights.hemi = new THREE.HemisphereLight(0x8a96b8, 0x3a2414, 0.09); scene.add(lights.hemi);
  WINDOWS.forEach((w, i) => {
    const ra = new THREE.RectAreaLight(0xa8b8ff, 0.7, w.w, TOP - SILL);
    ra.position.copy(B2T(WALL_X + 0.02, w.y, (SILL + TOP) / 2));
    ra.lookAt(B2T(0, w.y, (SILL + TOP) / 2)); scene.add(ra); lights['fill' + i] = ra;
  });
  const candle = new THREE.PointLight(0xff9a40, 0.6, 4, 2);
  candle.position.copy(B2T(0.28, 0.72, 1.16)); scene.add(candle); lights.candle = candle;
  const spot = new THREE.SpotLight(0xffc27a, 0, 6, THREE.MathUtils.degToRad(58), 0.6, 2);
  spot.position.copy(B2T(-0.6, 0.5, 2.1)); spot.target.position.copy(B2T(-0.6, 0.5, 0)); scene.add(spot, spot.target);
  spot.castShadow = true; spot.shadow.bias = -0.0005; lights.spot = spot;
  const orr = new THREE.PointLight(0xff8a30, 0, 3, 2); orr.position.copy(B2T(0.6, 2.55, 2.71)); scene.add(orr); lights.orrery = orr;
  const acc = new THREE.SpotLight(0xffcf96, 1.3, 5, THREE.MathUtils.degToRad(22), 0.7, 2);
  acc.position.copy(B2T(0.6, 1.0, 2.75)); acc.target.position.copy(B2T(0.6, 2.31, 1.85)); scene.add(acc, acc.target); lights.accent = acc;
  const bounce = new THREE.PointLight(0xffc89a, 0.25, 6, 2); bounce.position.copy(B2T(1.8, -1.8, 2.2)); scene.add(bounce);
  const trunk = new THREE.SpotLight(0xffa860, 1.2, 4, THREE.MathUtils.degToRad(35), 0.8, 2);
  trunk.position.copy(B2T(0.2, 1.55, 0.55)); trunk.target.position.copy(B2T(0.6, 2.55, 0.7)); scene.add(trunk, trunk.target);
}

// ------------------------------------------------------------------ light shafts (fake volumetrics)
let beamMat;
function buildBeams() {
  const pos = [], along = [];
  const L = 7.0;
  const d = SUN_DIR.clone();
  WINDOWS.forEach((w) => {
    for (let i = 0; i < 3; i++) for (let j = 0; j < 4; j++) {
      const y0 = w.y - w.w / 2 + (w.w / 3) * i + 0.02, y1 = y0 + w.w / 3 - 0.04;
      const z0 = SILL + ((TOP - SILL) / 4) * j + 0.02, z1 = z0 + (TOP - SILL) / 4 - 0.04;
      const c = [B2T(WALL_X - 0.12, y0, z0), B2T(WALL_X - 0.12, y1, z0), B2T(WALL_X - 0.12, y1, z1), B2T(WALL_X - 0.12, y0, z1)];
      const e = c.map((p) => p.clone().addScaledVector(d, L));
      for (let k = 0; k < 4; k++) {
        const a = c[k], b = c[(k + 1) % 4], ea = e[k], eb = e[(k + 1) % 4];
        for (const [p, t] of [[a, 0], [b, 0], [eb, 1], [a, 0], [eb, 1], [ea, 1]]) { pos.push(p.x, p.y, p.z); along.push(t); }
      }
    }
  });
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('along', new THREE.Float32BufferAttribute(along, 1));
  g.computeVertexNormals();
  beamMat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, fog: false,
    uniforms: { uTime: { value: 0 }, uStrength: { value: 1 }, uColor: { value: new THREE.Color(1.0, 0.62, 0.32) } },
    vertexShader: `attribute float along; varying float vA; varying vec3 vN; varying vec3 vV; varying vec3 vW;
      void main(){ vA = along; vec4 w = modelMatrix*vec4(position,1.0); vW = w.xyz;
        vN = normalize(mat3(modelMatrix)*normal); vV = normalize(cameraPosition - w.xyz);
        gl_Position = projectionMatrix*viewMatrix*w; }`,
    fragmentShader: `uniform float uTime; uniform float uStrength; uniform vec3 uColor; varying float vA; varying vec3 vN; varying vec3 vV; varying vec3 vW;
      float h(vec3 p){ return fract(sin(dot(p, vec3(12.9898,78.233,45.164)))*43758.5453); }
      void main(){
        float edge = pow(abs(dot(normalize(vN), normalize(vV))), 1.6);
        float fade = pow(1.0 - vA, 1.8) * smoothstep(0.0, 0.04, vA);
        float floorFade = smoothstep(0.0, 0.25, vW.y);
        float shimmer = 0.85 + 0.15 * sin(uTime * 0.7 + vW.x * 2.0 + vW.y * 3.0);
        float a = edge * fade * floorFade * shimmer * 0.12 * uStrength;
        gl_FragColor = vec4(uColor, a);
      }`,
  });
  const mesh = new THREE.Mesh(g, beamMat);
  mesh.renderOrder = 10;
  mesh.frustumCulled = false;
  scene.add(mesh);
}

// ------------------------------------------------------------------ dust motes
let dust;
function buildDust(count) {
  if (dust) { scene.remove(dust); dust.geometry.dispose(); }
  const p = new Float32Array(count * 3), s = new Float32Array(count);
  for (let i = 0; i < count; i++) {
    const v = B2T(-3.0 + Math.random() * 4.0, -1.4 + Math.random() * 3.6, 0.3 + Math.random() * 2.6);
    p.set([v.x, v.y, v.z], i * 3); s[i] = Math.random();
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(p, 3));
  g.setAttribute('seed', new THREE.BufferAttribute(s, 1));
  const m = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false,
    uniforms: { uTime: { value: 0 }, uPR: { value: renderer.getPixelRatio() }, uSun: { value: SUN_DIR }, uLight: { value: 1 } },
    vertexShader: `attribute float seed; uniform float uTime; uniform float uPR; uniform vec3 uSun; varying float vLit;
      bool inWin(vec3 q, float zc){ return q.z > zc - 0.55 && q.z < zc + 0.55 && q.y > 0.85 && q.y < 2.75; }
      void main(){
        vec3 p = position;
        float t = uTime * (0.05 + seed * 0.05);
        p += vec3(sin(t + seed * 30.0) * 0.25, sin(t * 0.7 + seed * 17.0) * 0.12, cos(t * 0.8 + seed * 9.0) * 0.25);
        float k = (p.x + 3.5) / uSun.x;          // trace back to the window plane
        vec3 q = p - uSun * k;
        vLit = (k > 0.0 && (inWin(q, 0.6) || inWin(q, -1.5))) ? 1.0 : 0.06;
        vec4 mv = modelViewMatrix * vec4(p, 1.0);
        gl_PointSize = (1.0 + seed * 1.6) * uPR * (3.2 / -mv.z);
        gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `uniform float uLight; varying float vLit;
      void main(){ vec2 c = gl_PointCoord - 0.5; float a = smoothstep(0.5, 0.0, length(c));
        gl_FragColor = vec4(vec3(1.0, 0.82, 0.6) * 1.4 * uLight, a * vLit); }`,
  });
  dust = new THREE.Points(g, m);
  dust.frustumCulled = false;
  scene.add(dust);
}

// ------------------------------------------------------------------ post-processing
let composer, bloom, bokeh, gradePass;
function buildComposer() {
  const q = QUALITY[Q];
  composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  bokeh = new BokehPass(scene, camera, { focus: 2.0, aperture: 0.0015, maxblur: 0.008 });
  bokeh.enabled = q.dof;
  composer.addPass(bokeh);
  bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.22, 0.5, 0.92);
  bloom.enabled = q.bloom;
  composer.addPass(bloom);
  composer.addPass(new OutputPass());
  gradePass = new ShaderPass({
    uniforms: { tDiffuse: { value: null }, uTime: { value: 0 }, uFade: { value: 1 } },
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }',
    fragmentShader: `uniform sampler2D tDiffuse; uniform float uTime; uniform float uFade; varying vec2 vUv;
      float h(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233)) + uTime) * 43758.5453); }
      void main(){ vec3 c = texture2D(tDiffuse, vUv).rgb;
        float l = dot(c, vec3(0.299,0.587,0.114));
        c = mix(c * vec3(0.96,1.0,1.05), c * vec3(1.05,1.0,0.93), smoothstep(0.1, 0.7, l));   // teal shadows, warm highlights
        vec2 d = vUv - 0.5; c *= 1.0 - smoothstep(0.35, 0.85, length(d * vec2(1.0, 0.8))) * 0.45; // vignette
        c += (h(vUv * 800.0) - 0.5) * 0.018;                                                       // film grain
        gl_FragColor = vec4(c * uFade, 1.0); }`,
  });
  composer.addPass(gradePass);
}

// ------------------------------------------------------------------ timeline state
const state = { t: 0, playing: false, speed: 1, mode: 'cinematic', shot: -1, selected: null, lastShot: -1 };
const frameOf = (t) => 1 + t * FPS;
function keyInterp(frame, keys) {
  if (frame <= keys[0][0]) return keys[0][1];
  for (let i = 1; i < keys.length; i++) if (frame <= keys[i][0]) {
    const [f0, v0] = keys[i - 1], [f1, v1] = keys[i]; const u = (frame - f0) / (f1 - f0);
    const s = u * u * (3 - 2 * u); return v0 + (v1 - v0) * s;
  }
  return keys[keys.length - 1][1];
}
function stepInterp(frame, keys) { let v = keys[0][1]; for (const [f, x] of keys) if (frame >= f) v = x; return v; }

function shotIndexAt(frame) { let idx = 0; CAMS.shots.forEach((s, i) => { if (frame >= s.start) idx = i; }); return idx; }

const tmpQ = new THREE.Quaternion(), tmpQ2 = new THREE.Quaternion();
function applyShotCamera(idx, frame) {
  const s = CAMS.shots[idx];
  const f = Math.min(Math.max(frame, s.start), s.end) - 1;
  const i0 = Math.floor(f), i1 = Math.min(i0 + 1, s.frames.length - 1), u = f - i0;
  const a = s.frames[i0], b = s.frames[i1];
  camera.position.set(a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u);
  tmpQ.set(a[3], a[4], a[5], a[6]); tmpQ2.set(b[3], b[4], b[5], b[6]);
  camera.quaternion.copy(tmpQ).slerp(tmpQ2, u);
  const lens = a[7] + (b[7] - a[7]) * u;
  camera.fov = THREE.MathUtils.radToDeg(2 * Math.atan(18 / lens / camera.aspect));
  camera.updateProjectionMatrix();
  if (bokeh) {
    const fd = a[8] + (b[8] - a[8]) * u;
    bokeh.uniforms.focus.value = fd;
    bokeh.uniforms.aperture.value = Math.min(0.02, 0.0009 * (lens / 35) ** 2 / (s.fstop / 2.8));
  }
}

let mixer, action, gltfRoot;
function updateWorld(dt) {
  const fr = frameOf(state.t);
  if (mixer) { mixer.setTime(Math.min(state.t, action.getClip().duration - 0.0001)); }
  // light story: sun sinks, lamp switches on, orrery ignites
  const sunK = keyInterp(fr, [[1, 1.0], [600, 0.96], [1440, 0.57]]);
  lights.sun.intensity = 11.0 * sunK;
  lights.sun.color.setRGB(1.0, 0.6 - (1 - sunK) * 0.45, 0.33 - (1 - sunK) * 0.4);
  if (beamMat) { beamMat.uniforms.uStrength.value = sunK; beamMat.uniforms.uTime.value = state.t; beamMat.uniforms.uColor.value.copy(lights.sun.color); }
  if (animatedMats.sky) animatedMats.sky.uniforms.uStrength.value = keyInterp(fr, [[1, 1], [1440, 0.6]]);
  const L0 = EV.lamp_on;
  const lamp = stepInterp(fr, [[1, 0], [L0, 1], [L0 + 2, 0], [L0 + 5, 0.7], [L0 + 7, 0.15], [L0 + 11, 1]]);
  lights.spot.intensity = lamp * 9;
  if (animatedMats.bulb) animatedMats.bulb.emissiveIntensity = lamp * 9;
  const [g0, g1] = EV.sun_glow;
  const glow = keyInterp(fr, [[g0, 0], [g0 + 20, 0.22], [g0 + 26, 0.12], [g1, 1]]);
  lights.orrery.intensity = glow * 0.5;
  if (animatedMats.orrery) animatedMats.orrery.emissiveIntensity = glow * 3;
  const fl = 0.85 + 0.15 * Math.sin(performance.now() * 0.013) * Math.sin(performance.now() * 0.0071 + 1.3);
  lights.candle.intensity = 0.6 * fl;
  if (animatedMats.flame) animatedMats.flame.opacity = 0.8 + 0.2 * fl;
  // fades
  const fade = Math.min(keyInterp(fr, [[1, 0], [EV.fade_in[1], 1]]), keyInterp(fr, [[EV.fade_out[0], 1], [EV.fade_out[1], 0]]));
  gradePass.uniforms.uFade.value = state.mode === 'free' ? 1 : fade;
  gradePass.uniforms.uTime.value = state.t;
  if (dust) dust.material.uniforms.uTime.value = performance.now() / 1000;
  // camera
  if (state.mode === 'cinematic' || state.mode === 'shot') {
    const idx = state.mode === 'cinematic' ? shotIndexAt(fr) : state.shot;
    applyShotCamera(idx, fr);
    if (idx !== state.lastShot) { state.lastShot = idx; onShotChange(idx); }
  } else {
    controls.update();
    if (bokeh) bokeh.enabled = false;
  }
  if (bokeh && state.mode !== 'free') bokeh.enabled = QUALITY[Q].dof;
}

// ------------------------------------------------------------------ audio
const audio = {};
const vol = { master: 0.9, music: 0.55, ambience: 0.7, sfx: 0.9, muted: false };
function buildAudio() {
  for (const n of ['music', 'ambience', 'sfx']) {
    const a = new Audio(`audio/${n}.mp3`); a.preload = 'auto'; audio[n] = a;
  }
  applyVolumes();
}
function applyVolumes() {
  for (const n in audio) audio[n].volume = vol.muted ? 0 : Math.min(1, vol.master * vol[n]);
}
function audioSync(force) {
  for (const n in audio) {
    const a = audio[n];
    a.playbackRate = state.speed;
    if (!state.playing || state.speed < 0.5 || state.speed > 2) { if (!a.paused) a.pause(); continue; }
    if (force || Math.abs(a.currentTime - state.t) > 0.2) { try { a.currentTime = state.t; } catch (e) { /* not loaded yet */ } }
    if (a.paused) a.play().catch(() => {});
  }
}

// ------------------------------------------------------------------ UI
const chapters = EV.sequences;
function fmt(t) { const m = Math.floor(t / 60), s = (t % 60); return `${m}:${s.toFixed(1).padStart(4, '0')}`; }
function setPlaying(p) { state.playing = p; $('play').innerHTML = p ? ICON.pause : ICON.play; $('play').title = p ? 'Pause (Space)' : 'Play (Space)'; audioSync(true); }
function seek(t) { state.t = Math.max(0, Math.min(DURATION, t)); audioSync(true); }
function setMode(mode, shot = -1) {
  state.mode = mode; state.shot = shot;
  controls.enabled = mode === 'free';
  if (mode === 'free') {
    const fwd = new THREE.Vector3(0, 0, -1).applyQuaternion(camera.quaternion);
    controls.target.copy(camera.position).addScaledVector(fwd, 1.5);
  }
  if (mode === 'shot') seek((CAMS.shots[shot].start - 1) / FPS);
  $('camsel').value = mode === 'shot' ? String(shot) : mode;
  state.lastShot = -1;
  if (mode === 'free') showCaption('Free camera', 'Drag to orbit - scroll to zoom - right-drag to pan - click objects to inspect');
}
let capTimer;
function showCaption(title, sub) {
  const c = $('caption'); c.querySelector('h2').textContent = title; c.querySelector('p').textContent = sub || '';
  c.classList.add('show'); clearTimeout(capTimer); capTimer = setTimeout(() => c.classList.remove('show'), 3800);
}
function onShotChange(idx) {
  const fr = frameOf(state.t);
  const ch = chapters.filter((c) => c[1] <= fr).pop();
  $('chapter').textContent = ch ? ch[0] : '';
  const s = CAMS.shots[idx];
  if (state.mode === 'cinematic' && chapters.some((c) => c[1] === s.start)) showCaption(ch[0], s.label);
  document.querySelectorAll('.chap').forEach((el) => el.classList.toggle('on', Number(el.dataset.f) <= fr));
}

const ICON = {
  play: '<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>',
  pause: '<svg viewBox="0 0 24 24"><path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>',
};

function buildUI() {
  $('play').innerHTML = ICON.play;
  $('play').onclick = () => setPlaying(!state.playing);
  $('restart').onclick = () => { seek(0); setPlaying(true); };
  const tl = $('timeline');
  chapters.forEach(([name, f]) => {
    const m = document.createElement('button'); m.className = 'chap'; m.dataset.f = f;
    m.style.left = `${((f - 1) / (FRAME_END - 1)) * 100}%`; m.title = name; m.innerHTML = `<span>${name}</span>`;
    m.onclick = (e) => { e.stopPropagation(); seek((f - 1) / FPS); };
    tl.appendChild(m);
  });
  let dragging = false;
  const scrub = (e) => { const r = tl.getBoundingClientRect(); seek(((e.clientX - r.left) / r.width) * DURATION); };
  tl.addEventListener('pointerdown', (e) => { dragging = true; tl.setPointerCapture(e.pointerId); scrub(e); });
  tl.addEventListener('pointermove', (e) => { if (dragging) scrub(e); });
  tl.addEventListener('pointerup', () => { dragging = false; });
  $('speed').onchange = (e) => { state.speed = Number(e.target.value); audioSync(true); };
  const cs = $('camsel');
  cs.innerHTML = '<option value="cinematic">Cinematic (auto cuts)</option>' +
    CAMS.shots.map((s, i) => `<option value="${i}">${s.label}</option>`).join('') +
    '<option value="free">Free camera (orbit)</option>';
  cs.onchange = (e) => { const v = e.target.value; if (v === 'cinematic' || v === 'free') setMode(v); else setMode('shot', Number(v)); };
  const qs = $('quality'); qs.value = Q;
  qs.onchange = (e) => { localSet('cw_quality', e.target.value); location.reload(); };
  for (const k of ['master', 'music', 'ambience', 'sfx']) {
    const el = $('v_' + k); el.value = vol[k]; el.oninput = () => { vol[k] = Number(el.value); applyVolumes(); };
  }
  $('mute').onclick = () => { vol.muted = !vol.muted; $('mute').classList.toggle('off', vol.muted); applyVolumes(); };
  $('audiobtn').onclick = () => $('audiopanel').classList.toggle('open');
  $('helpbtn').onclick = () => $('help').classList.toggle('open');
  $('help').onclick = () => $('help').classList.remove('open');
  $('fullscreen').onclick = () => { if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen().catch(() => {}); };
  $('closeinfo').onclick = () => select(null);
  $('focusbtn').onclick = () => focusSelected();
  window.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
    if (e.code === 'Space') { e.preventDefault(); setPlaying(!state.playing); }
    else if (e.key === 'r' || e.key === 'R') { seek(0); setPlaying(true); }
    else if (e.key === 'f' || e.key === 'F') setMode('free');
    else if (e.key === 'c' || e.key === 'C') setMode('cinematic');
    else if (e.key === 'ArrowRight') seek(state.t + 2);
    else if (e.key === 'ArrowLeft') seek(state.t - 2);
    else if (e.key === 'ArrowUp') { state.speed = Math.min(2, state.speed * 2); $('speed').value = String(state.speed); audioSync(true); }
    else if (e.key === 'ArrowDown') { state.speed = Math.max(0.25, state.speed / 2); $('speed').value = String(state.speed); audioSync(true); }
    else if (/^[1-5]$/.test(e.key)) seek((chapters[Number(e.key) - 1][1] - 1) / FPS);
    else if (e.key === 'Escape') select(null);
  });
  // object picking (click without drag)
  const ray = new THREE.Raycaster(); const ndc = new THREE.Vector2(); let down = null;
  canvas.addEventListener('pointerdown', (e) => { down = [e.clientX, e.clientY]; });
  canvas.addEventListener('pointerup', (e) => {
    if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5) return;
    const r = canvas.getBoundingClientRect();
    ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const hits = ray.intersectObjects(pickables, false);
    const solid = hits.find((h) => !/Glass/.test(h.object.material.name));   // click through glass
    select(hits.length ? (solid || hits[0]).object : null);
  });
  canvas.addEventListener('pointermove', (e) => {
    const r = canvas.getBoundingClientRect();
    ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const hit = ray.intersectObjects(pickables, false)[0];
    canvas.style.cursor = hit && infoOf(hit.object) ? 'pointer' : (state.mode === 'free' ? 'grab' : 'default');
  });
}

const pickables = [];
let highlight;
function infoOf(o) { while (o) { if (o.userData && o.userData.cw_info) return { o, info: o.userData.cw_info }; o = o.parent; } return null; }
function prettyName(n) { return n.replace(/^(Clock|Prop|Orrery|Movement|Bench|Shelf|Cabinet|Watch|Wall)_?/, '').replace(/[_\d]+$/, '').replace(/_/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2').trim() || n; }
function select(obj) {
  if (highlight) { scene.remove(highlight); highlight = null; }
  const r = obj ? infoOf(obj) : null;
  state.selected = r ? r.o : null;
  if (!r) { $('info').classList.remove('open'); return; }
  highlight = new THREE.BoxHelper(r.o, 0xffd28a); highlight.material.transparent = true; highlight.material.opacity = 0.7;
  scene.add(highlight);
  $('infoname').textContent = prettyName(r.o.name);
  $('infotext').textContent = r.info;
  $('info').classList.add('open');
}
function focusSelected() {
  if (!state.selected) return;
  const box = new THREE.Box3().setFromObject(state.selected), c = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3()).length();
  setMode('free');
  const dir = camera.position.clone().sub(c).normalize();
  const goal = c.clone().addScaledVector(dir, Math.max(0.12, size * 1.6));
  const from = camera.position.clone(), tFrom = controls.target.clone(), t0 = performance.now();
  const step = () => {
    const u = Math.min(1, (performance.now() - t0) / 900), s = u * u * (3 - 2 * u);
    camera.position.lerpVectors(from, goal, s); controls.target.lerpVectors(tFrom, c, s);
    if (u < 1) requestAnimationFrame(step);
  };
  step();
}

// ------------------------------------------------------------------ resize / loop
function resize() {
  const w = window.innerWidth, h = window.innerHeight;
  const pr = Math.min(window.devicePixelRatio || 1, QUALITY[Q].pr);
  renderer.setPixelRatio(pr); renderer.setSize(w, h, false);
  composer.setPixelRatio(pr); composer.setSize(w, h);
  camera.aspect = w / h; camera.updateProjectionMatrix();
  if (dust) dust.material.uniforms.uPR.value = pr;
}

const clock = new THREE.Clock();
let fpsAcc = 0, fpsN = 0;
function loop() {
  requestAnimationFrame(loop);
  const dt = Math.min(0.1, clock.getDelta());
  if (state.playing) {
    state.t += dt * state.speed;
    if (state.t >= DURATION) { state.t = 0; audioSync(true); }
  }
  updateWorld(dt);
  if (highlight) highlight.update();
  $('time').textContent = `${fmt(state.t)} / ${fmt(DURATION)}`;
  $('progress').style.width = `${(state.t / DURATION) * 100}%`;
  composer.render(dt);
  fpsAcc += dt; fpsN++;
  if (fpsAcc > 1) { $('fps').textContent = `${Math.round(fpsN / fpsAcc)} fps`; fpsAcc = 0; fpsN = 0; }
  if (window.__cwFrames !== undefined) window.__cwFrames++;
}

// ------------------------------------------------------------------ boot
function b64ToBuffer(b64) {
  const bin = atob(b64); const len = bin.length; const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
}

async function boot() {
  $('loadmsg').textContent = 'Generating materials...';
  await new Promise((r) => setTimeout(r, 30));
  buildTextures();
  $('loadmsg').textContent = 'Building the workshop...';
  await new Promise((r) => setTimeout(r, 30));
  const loader = new GLTFLoader();
  const b64 = D.glb || (window.CW_GLB_PARTS ? window.CW_GLB_PARTS.join('') : null);   // embedded or split parts
  const buf = b64 ? b64ToBuffer(b64) : await (await fetch('data/scene.glb')).arrayBuffer();
  const gltf = await loader.parseAsync(buf, '');
  gltfRoot = gltf.scene;
  const cache = {};
  const q = QUALITY[Q];
  gltfRoot.traverse((o) => {
    if (!o.isMesh) return;
    const nm = o.material && o.material.name ? o.material.name : 'default';
    if (!cache[nm]) { cache[nm] = makeMaterial(nm, o.material); cache[nm].name = nm; }
    o.material = cache[nm];
    const glassy = /Glass|Flame|DuskSky|Rooftop|SunDisc/.test(nm);
    o.castShadow = !glassy && !/^(Floor|Ceiling|RoomFog)/.test(o.name) && !/^(House|Roof|Chimney|DuskSky|SunDisc)/.test(o.name);
    o.receiveShadow = !/Flame|DuskSky|Rooftop|SunDisc/.test(nm);
    if (infoOf(o)) pickables.push(o);
  });
  scene.add(gltfRoot);
  mixer = new THREE.AnimationMixer(gltfRoot);
  const clip = gltf.animations[0];
  action = mixer.clipAction(clip); action.play();
  buildLights();
  lights.sun.shadow.mapSize.set(q.shadow, q.shadow);
  lights.spot.shadow.mapSize.set(q.shadow / 2, q.shadow / 2);
  lights.spot.castShadow = q.extraShadows;
  renderer.shadowMap.type = q.softShadows ? THREE.PCFSoftShadowMap : THREE.PCFShadowMap;
  buildBeams();
  buildDust(q.dust);
  buildComposer();
  buildAudio();
  buildUI();
  resize();
  window.addEventListener('resize', resize);
  setMode('cinematic');
  updateWorld(0);
  $('loading').classList.add('ready');
  $('loadmsg').textContent = '';
  $('enter').onclick = () => { $('loading').classList.add('gone'); setPlaying(true); };
  window.__cwReady = true;
  loop();
  // test hooks (used by automated screenshots)
  window.__cw = { seek, setMode, setPlaying, select, state, pickables, renderer };
}

boot().catch((e) => { console.error(e); $('loadmsg').textContent = 'Could not start: ' + e.message; });
