"""
make_audio.py - synthesises the complete soundtrack with numpy (no samples needed).

Outputs (48 kHz stereo WAV) in ../audio/:
  music.wav     ambient score in D minor -> resolves to D major when the clock strikes
  ambience.wav  room tone, evening wind, distant birds, wood creaks, candle crackle
  sfx.wav       every mechanical sound, synced frame-accurately to the animation:
                clock ticks, balance wheel, wall clocks, winding ratchet, gear release,
                orrery shimmer, lamp switch + filament hum, the hour bell
  events.json   the event timeline (used by the browser version)

Run:  python scripts/make_audio.py
"""
import json
import os
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

SR = 48000
FPS = 24
DUR = 60.0
N = int(SR * DUR)
rng = np.random.default_rng(1234)


def load_events():
    # cw_animation imports bpy; read the constants without needing Blender
    import importlib.util
    try:
        import cw_animation
        return cw_animation.timeline_events()
    except Exception:
        spec = importlib.util.spec_from_file_location("cw_anim_src", os.path.join(HERE, "cw_animation.py"))
        src = open(os.path.join(HERE, "cw_animation.py"), encoding='utf-8').read()
        src = src.replace("import bpy", "bpy = None").replace("from mathutils import Vector", "Vector = None")
        src = src.split("from cw_util import")[0] + src.split("TAU)\n", 1)[1]
        ns = {"__name__": "cw_anim_src", "TAU": 2 * np.pi}
        exec(compile("import math, os\nTAU = math.tau\n" + src.split("# ------------------------------------------------------------------ helpers")[0], "cw_anim", "exec"), ns)
        return ns['timeline_events']()


EV = load_events()
SEQ = EV['sequences']


def fs(frame):
    """frame -> sample index"""
    return int(round((frame - 1) / FPS * SR))


def tsec(n):
    return np.arange(n) / SR

# ------------------------------------------------------------------ DSP helpers

def fft_filter(x, lo=None, hi=None, order=2.0):
    """Zero-phase spectral band filter with smooth Butterworth-like edges."""
    X = np.fft.rfft(x, axis=0)
    f = np.fft.rfftfreq(x.shape[0], 1 / SR)
    g = np.ones_like(f)
    if hi:
        g *= 1 / np.sqrt(1 + (f / hi) ** (2 * order))
    if lo:
        g *= 1 / np.sqrt(1 + (lo / np.maximum(f, 1e-3)) ** (2 * order))
    if x.ndim == 2:
        g = g[:, None]
    return np.fft.irfft(X * g, n=x.shape[0], axis=0)


def resonator(x, freq, q):
    """Two-pole resonant band-pass (sample-by-sample, for short sounds only)."""
    w = 2 * np.pi * freq / SR
    r = np.exp(-w / (2 * q))
    a1, a2 = -2 * r * np.cos(w), r * r
    y = np.zeros_like(x)
    y1 = y2 = 0.0
    g = (1 - r)
    for i in range(len(x)):
        v = g * x[i] - a1 * y1 - a2 * y2
        y[i] = v
        y2, y1 = y1, v
    return y


def damped(freq, decay, dur, phase=0.0):
    t = tsec(int(dur * SR))
    return np.sin(2 * np.pi * freq * t + phase) * np.exp(-t / decay)


def env_adsr(n, a, d, s, r, sr=SR):
    a, d, r = int(a * sr), int(d * sr), int(r * sr)
    sus = max(0, n - a - d - r)
    e = np.concatenate([np.linspace(0, 1, max(a, 1)), np.linspace(1, s, max(d, 1)), np.full(sus, s),
                        np.linspace(s, 0, max(r, 1))])
    return e[:n] if len(e) >= n else np.pad(e, (0, n - len(e)))


def pan(mono, p):
    """p in [-1, 1] -> stereo with constant power."""
    a = (p + 1) * np.pi / 4
    return np.stack([mono * np.cos(a), mono * np.sin(a)], axis=1)


def place(buf, snd, at, gain=1.0):
    if at >= len(buf):
        return
    end = min(len(buf), at + len(snd))
    buf[at:end] += snd[:end - at] * gain


def reverb(x, seconds=2.4, mix=0.3, predelay=0.02, damp=4000):
    n_ir = int(seconds * SR)
    t = tsec(n_ir)
    irs = []
    for ch in range(2):
        nz = rng.standard_normal(n_ir)
        ir = nz * np.exp(-6.9 * t / seconds)
        ir = fft_filter(ir, lo=120, hi=damp, order=1)
        ir = np.concatenate([np.zeros(int(predelay * SR)), ir])
        irs.append(ir / np.sqrt(np.sum(ir ** 2)))
    out = np.zeros_like(x)
    L = len(x) + len(irs[0])
    nfft = 1 << (L - 1).bit_length()
    for ch in range(2):
        X = np.fft.rfft(x[:, ch], nfft)
        H = np.fft.rfft(irs[ch], nfft)
        out[:, ch] = np.fft.irfft(X * H, nfft)[:len(x)]
    return x * (1 - mix) + out * mix * 1.6


def shot_gain(points):
    """Piecewise-linear gain automation from (frame, gain) points."""
    fr = np.array([p[0] for p in points], float)
    gn = np.array([p[1] for p in points], float)
    t = np.arange(N) / SR * FPS + 1
    return np.interp(t, fr, gn)


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    pcm = (x * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def softlimit(x, ceiling=0.89):
    return np.tanh(x / ceiling) * ceiling


def fade_master(x):
    fi0, fi1 = EV['fade_in']
    fo0, fo1 = EV['fade_out']
    g = shot_gain([(1, 0.0), (fi1 + 12, 1.0), (fo0, 1.0), (fo1 + 2, 0.0)])
    return x * g[:, None]

# ------------------------------------------------------------------ sound designs

def snd_tick(freq=2300, body=(430, 910), length=0.09, bright=1.0):
    n = int(length * SR)
    burst = rng.standard_normal(n) * np.exp(-tsec(n) / 0.0025)
    s = resonator(burst, freq, 9) * 3.0 * bright
    for b in body:
        s += damped(b, 0.025, length) * 0.18
    s += resonator(burst, freq * 2.7, 14) * 1.2 * bright
    return s / (np.max(np.abs(s)) + 1e-9)


def snd_click(freq=5200, ring=3100, length=0.06):
    n = int(length * SR)
    burst = rng.standard_normal(n) * np.exp(-tsec(n) / 0.0012)
    s = resonator(burst, freq, 6) * 2 + damped(ring, 0.012, length) * 0.25
    return s / (np.max(np.abs(s)) + 1e-9)


def snd_bell(f0=233.08, length=9.0, strike=1.0):
    """Church/clock bell with inharmonic partials (hum, prime, tierce, quint, nominal...)."""
    partials = [(0.5, 1.0, 4.5), (1.0, 0.8, 3.2), (1.183, 0.55, 2.5), (1.506, 0.35, 2.0), (2.0, 0.6, 1.8),
                (2.514, 0.25, 1.2), (2.662, 0.2, 1.0), (3.011, 0.18, 0.8), (4.166, 0.12, 0.5), (5.433, 0.08, 0.35)]
    n = int(length * SR)
    t = tsec(n)
    s = np.zeros(n)
    for ratio, amp, dec in partials:
        detune = 1 + rng.uniform(-0.0015, 0.0015)
        beat = 1 + 0.08 * np.sin(2 * np.pi * rng.uniform(0.3, 1.2) * t)  # slow beating of partials
        s += amp * np.sin(2 * np.pi * f0 * ratio * detune * t + rng.uniform(0, 6)) * np.exp(-t / dec) * beat
    hit = rng.standard_normal(n) * np.exp(-t / 0.004)
    s += fft_filter(hit, lo=800, hi=6000) * 0.6 * strike
    return s / np.max(np.abs(s))


def snd_musicbox(freq, length=1.6):
    n = int(length * SR)
    t = tsec(n)
    idx = 2.2 * np.exp(-t / 0.15)
    s = np.sin(2 * np.pi * freq * t + idx * np.sin(2 * np.pi * freq * 3.5 * t)) * np.exp(-t / 0.7)
    s += 0.25 * np.sin(2 * np.pi * freq * 2.01 * t) * np.exp(-t / 0.35)
    s *= np.minimum(1, t / 0.002)
    return s


def note_hz(name):
    names = {'C': -9, 'C#': -8, 'Db': -8, 'D': -7, 'D#': -6, 'Eb': -6, 'E': -5, 'F': -4, 'F#': -3, 'Gb': -3,
             'G': -2, 'G#': -1, 'Ab': -1, 'A': 0, 'A#': 1, 'Bb': 1, 'B': 2}
    n, o = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((names[n] + (o - 4) * 12) / 12)


def pad_voice(freqs, dur, a=1.8, r=2.5, bright=4.0, detune=0.004):
    n = int(dur * SR)
    t = tsec(n)
    out = np.zeros((n, 2))
    for f in freqs:
        for ch, dt in ((0, -detune), (1, detune)):
            for v in (-1, 0, 1):
                ff = f * (1 + dt * v + rng.uniform(-0.0008, 0.0008))
                ph = rng.uniform(0, 6.28)
                wob = 1 + 0.002 * np.sin(2 * np.pi * 0.2 * t + ph)
                for h in range(1, 10):
                    amp = (1.0 / h) * np.exp(-h / bright)
                    out[:, ch] += amp * np.sin(2 * np.pi * ff * h * wob * t + ph * h)
    e = env_adsr(n, a, 0.5, 0.85, r)
    return out * e[:, None] / (len(freqs) * 3)

# ------------------------------------------------------------------ tracks

def make_sfx():
    out = np.zeros((N, 2))
    tick_a = snd_tick(2200, (420, 880))
    tick_b = snd_tick(2550, (470, 960))
    small = snd_tick(4800, (1500,), 0.04, 1.0)
    wall = [snd_tick(3100 + k * 400, (650 + k * 90,), 0.05) for k in range(3)]
    click = snd_click()
    # grand clock: louder in the close shots
    g_clock = shot_gain([(1, 0.0), (700, 0.0), (701, 1.0), (820, 1.0), (821, 0.75), (912, 0.8), (913, 0.45),
                         (1200, 0.45), (1201, 0.85), (1300, 0.85), (1301, 0.5), (1440, 0.35)])
    for i, b in enumerate(EV['beats']):
        s = fs(b + 3)
        place(out, pan((tick_a if i % 2 else tick_b) * 0.55, 0.1), s, g_clock[min(s, N - 1)])
    # bench movement: tiny fast ticks, mostly heard in the bench shots
    g_bench = shot_gain([(1, 0.05), (288, 0.08), (289, 0.35), (430, 0.45), (431, 0.9), (576, 0.9), (577, 0.06),
                         (1440, 0.05)])
    for f in EV['balance_ticks']:
        s = fs(f)
        place(out, pan(small * 0.25, -0.25), s, g_bench[min(s, N - 1)])
    # wall clocks: one tick per second each, slightly offset
    g_wall = shot_gain([(1, 0.6), (150, 0.6), (151, 1.0), (288, 1.0), (289, 0.35), (576, 0.3), (577, 0.25),
                        (1300, 0.25), (1301, 0.5), (1440, 0.6)])
    for k in range(3):
        for f in EV['wall_ticks']:
            s = fs(f + k * 7)
            place(out, pan(wall[k] * 0.11, -0.6 + k * 0.25), s, g_wall[min(s, N - 1)])
    # winding ratchet
    for f in EV['key_clicks']:
        place(out, pan(click * 0.5, 0.15), fs(f))
    # gear release 'clunk' + short whirr when the clock starts
    ts = fs(EV['tick_start'] - 2)
    cl = damped(110, 0.08, 0.4) + damped(230, 0.05, 0.4) * 0.5
    cl += fft_filter(rng.standard_normal(len(cl)) * np.exp(-tsec(len(cl)) / 0.02), lo=200, hi=2500) * 0.6
    place(out, pan(cl / np.max(np.abs(cl)) * 0.6, 0.05), ts)
    wn = int(1.2 * SR)
    wh = fft_filter(rng.standard_normal(wn), lo=900, hi=2600) * env_adsr(wn, 0.05, 0.3, 0.4, 0.8)
    place(out, pan(wh * 0.12, 0.1), ts)
    # orrery: soft mechanical purr + shimmering ignition of the sun
    o0 = fs(EV['orrery_start'])
    on = N - o0
    purr = fft_filter(rng.standard_normal(on), lo=150, hi=700) * 0.05
    purr *= np.minimum(1, tsec(on) / 4.0) * (1 + 0.3 * np.sin(2 * np.pi * 7.3 * tsec(on)))
    g_orr = shot_gain([(1, 0), (912, 0.5), (913, 1.0), (1200, 1.0), (1201, 0.4), (1440, 0.3)])
    out[o0:] += pan(purr, -0.1) * g_orr[o0:, None]
    s0, s1 = EV['sun_glow']
    notes = ['D5', 'F5', 'A5', 'C6', 'D6', 'F6', 'A6', 'D7']
    for i, nn in enumerate(notes):
        f = s0 + i * (s1 - s0) // len(notes)
        place(out, pan(snd_musicbox(note_hz(nn), 2.5) * 0.12, -0.5 + i * 0.14), fs(f))
    sw = int((s1 - s0) / FPS * SR) + SR
    swoosh = fft_filter(rng.standard_normal(sw), lo=2000, hi=9000) * env_adsr(sw, 2.5, 0.2, 0.6, 1.0) * 0.05
    place(out, pan(swoosh, 0.0), fs(s0))
    # pendant lamp: switch click, flickering filament buzz, steady hum
    lo = EV['lamp_on']
    place(out, pan(snd_click(3800, 1800, 0.08) * 0.7, -0.35), fs(lo - 1))
    state = [(lo, 1.0), (lo + 2, 0.0), (lo + 5, 0.7), (lo + 7, 0.15), (lo + 11, 1.0)]
    hn = N - fs(lo)
    t = tsec(hn)
    hum = (np.sin(2 * np.pi * 100 * t) + 0.5 * np.sin(2 * np.pi * 200 * t) + 0.25 * np.sin(2 * np.pi * 300 * t))
    hum += fft_filter(rng.standard_normal(hn), lo=2000, hi=5000) * 0.3
    gate = np.zeros(hn)
    for (f, v), nxt in zip(state, state[1:] + [(EV['frame_end'] + 10, 0)]):
        a, b = fs(f) - fs(lo), min(hn, fs(nxt[0]) - fs(lo))
        gate[a:b] = v
    gate = np.convolve(gate, np.ones(200) / 200, mode='same')
    level = np.where(np.arange(hn) < fs(lo + 14) - fs(lo), 0.06, 0.012)
    out[fs(lo):] += pan(hum * gate * level, -0.35)
    # the hour bell
    for i, c in enumerate(EV['chimes']):
        b = snd_bell(233.08 if i < len(EV['chimes']) - 1 else 233.08, 8.0)
        place(out, pan(b * 0.42, 0.25), fs(c))
    out = reverb(out, 1.4, 0.22, damp=6000)
    return out


def make_ambience():
    out = np.zeros((N, 2))
    t = tsec(N)
    # room tone
    pink = fft_filter(rng.standard_normal((N, 2)), lo=30, hi=320, order=1) * 0.025
    out += pink
    # evening wind outside, slowly breathing
    lfo = np.interp(t, np.linspace(0, DUR, 14), rng.uniform(0.3, 1.0, 14))
    wind = fft_filter(rng.standard_normal((N, 2)), lo=180, hi=900, order=2) * 0.05
    out += wind * lfo[:, None]
    # distant birds (fewer as dusk deepens)
    for k in range(9):
        at = rng.uniform(1.5, 38.0)
        dur = rng.uniform(0.08, 0.18)
        n = int(dur * SR)
        tt = tsec(n)
        f0 = rng.uniform(2600, 3800)
        chirp = np.sin(2 * np.pi * (f0 * tt + rng.uniform(-1, 1) * 5000 * tt ** 2))
        chirp *= np.sin(np.pi * tt / dur) ** 2
        for rep in range(rng.integers(1, 4)):
            place(out, pan(chirp * 0.018 * (1 - at / 50), rng.uniform(-0.9, -0.4)), int((at + rep * dur * 1.4) * SR))
    # old timber creaks
    for at in (9.5, 27.0, 46.5):
        n = int(0.7 * SR)
        tt = tsec(n)
        src = rng.standard_normal(n) * (0.5 + 0.5 * np.sin(2 * np.pi * 38 * tt) ** 8)
        cr = fft_filter(src, lo=300, hi=1400) * env_adsr(n, 0.1, 0.2, 0.6, 0.3)
        place(out, pan(cr * 0.06, rng.uniform(-0.3, 0.6)), int(at * SR))
    # candle crackle
    for k in range(70):
        at = rng.uniform(0, DUR)
        n = int(0.01 * SR)
        c = rng.standard_normal(n) * np.exp(-tsec(n) / 0.0015)
        place(out, pan(fft_filter(c, lo=1500) * rng.uniform(0.01, 0.03), 0.3), int(at * SR))
    return reverb(out, 1.8, 0.25)


def make_music():
    out = np.zeros((N, 2))
    sec = lambda f: (f - 1) / FPS
    chords = [  # (start frame, duration s, notes)
        (1, 6.4, ['D3', 'A3', 'E4', 'F4']),          # Dm(add9)
        (150, 6.4, ['Bb2', 'F3', 'A3', 'D4']),       # Bbmaj7
        (289, 6.0, ['G2', 'D3', 'Bb3', 'A4']),       # Gm9
        (433, 6.0, ['A2', 'E3', 'G3', 'D4']),        # A7sus4
        (577, 6.5, ['D3', 'A3', 'F4', 'E4']),        # Dm(add9)
        (733, 6.5, ['Bb2', 'F3', 'D4', 'A4']),       # Bbmaj7
        (889, 6.2, ['F3', 'C4', 'A4', 'E5']),        # Fmaj7
        (1037, 6.2, ['C3', 'G3', 'E4', 'D5']),       # Cadd9
        (1185, 4.8, ['A2', 'E3', 'G4', 'D5']),       # A7sus4 (tension before the hour)
        (1300, 6.4, ['D3', 'A3', 'F#4', 'A4', 'D5']),  # D major - the hour (Picardy third)
    ]
    for f, d, nn in chords:
        v = pad_voice([note_hz(x) for x in nn], d + 2.2, a=1.6, r=2.4, bright=3.0 if f < 900 else 4.5)
        place(out, v * (0.32 if f < 1300 else 0.42), fs(f))
    # low drone
    t = tsec(N)
    drone = np.sin(2 * np.pi * note_hz('D2') * t) * 0.6 + np.sin(2 * np.pi * note_hz('D2') * 2 * t) * 0.15
    dgain = shot_gain([(1, 0.0), (90, 0.5), (700, 0.7), (1185, 0.9), (1290, 0.4), (1300, 0.8), (1440, 0.0)])
    out += pan(drone * 0.08 * dgain, 0.0)
    # music box, locked to the clock's tick (one note per beat) once the clock is running
    seq = {577: ['D5', 'A5', 'F5', 'E5'], 733: ['D5', 'F5', 'Bb5', 'A5'], 889: ['C6', 'A5', 'F5', 'E5'],
           1037: ['D6', 'G5', 'E5', 'C5'], 1185: ['E5', 'D5', 'A4', 'G5']}
    keys_sorted = sorted(seq)
    for i, b in enumerate(EV['beats']):
        if b >= 1290:
            break
        sec_key = max([k for k in keys_sorted if k <= b] or [keys_sorted[0]])
        pattern = seq[sec_key]
        nn = pattern[i % 4]
        vel = 0.06 + 0.05 * min(1, i / 20)
        place(out, pan(snd_musicbox(note_hz(nn)) * vel, -0.4 + 0.8 * ((i * 3) % 5) / 4), fs(b + 3))
    # sparse notes in the bench section
    for f, nn in ((300, 'A5'), (348, 'F5'), (396, 'E5'), (444, 'D5'), (492, 'E5'), (540, 'C6')):
        place(out, pan(snd_musicbox(note_hz(nn), 2.0) * 0.05, 0.3), fs(f))
    # final arpeggio after the bell
    for i, nn in enumerate(['D5', 'F#5', 'A5', 'D6', 'F#6', 'A6']):
        place(out, pan(snd_musicbox(note_hz(nn), 2.5) * 0.07, -0.5 + i * 0.2), fs(1312 + i * 6))
    # string swell rising through The Heavens
    sw = pad_voice([note_hz('F4'), note_hz('A4'), note_hz('C5')], 13.0, a=6.0, r=3.5, bright=6.0, detune=0.006)
    place(out, sw * 0.22, fs(913))
    out = fft_filter(out, lo=40, hi=9000, order=1)
    return reverb(out, 3.2, 0.42, damp=5000)


def main():
    os.makedirs(os.path.join(ROOT, "audio"), exist_ok=True)
    print("[audio] synthesising sfx ...")
    sfx = make_sfx()
    print("[audio] synthesising ambience ...")
    amb = make_ambience()
    print("[audio] synthesising music ...")
    mus = make_music()
    for name, x, peak in (("sfx", sfx, 0.85), ("ambience", amb, 0.35), ("music", mus, 0.7)):
        x = fade_master(x)
        x = x / (np.max(np.abs(x)) + 1e-9) * peak
        write_wav(os.path.join(ROOT, "audio", f"{name}.wav"), softlimit(x))
        print(f"[audio] wrote audio/{name}.wav")
    # a reference full mix (what the film sounds like with default volumes)
    mix = softlimit(fade_master(sfx / np.max(np.abs(sfx)) * 0.85 * 0.9 + amb / np.max(np.abs(amb)) * 0.35 * 0.7
                                + mus / np.max(np.abs(mus)) * 0.7 * 0.55))
    write_wav(os.path.join(ROOT, "audio", "full_mix_preview.wav"), mix)
    ev = dict(EV)
    ev['sequences'] = [list(s) for s in ev['sequences']]
    json.dump(ev, open(os.path.join(ROOT, "audio", "events.json"), "w"), indent=1)
    print("[audio] wrote audio/events.json")


if __name__ == "__main__":
    main()
