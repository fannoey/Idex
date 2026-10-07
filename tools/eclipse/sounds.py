"""Procedural sound design for ECLIPSE TWIN SWORDS (pure numpy -> .ogg via ffmpeg).

Every sound is built from oscillators, filtered noise and envelopes in three
layers (impact / body / tail):
  SOLAR  = crystal bells, bright "shing", warm major chords
  VOID   = sub-bass, dark filtered noise, low metallic rings, minor chords
  ECLIPSE= both families layered + long reverb tails
"""
import io
import math
import os
import shutil
import subprocess
import wave

import numpy as np

SR = 44100
RNG = np.random.default_rng(777)


# ----------------------------------------------------------------- basics

def T(dur):
    return np.arange(int(dur * SR)) / SR


def pad_to(x, n):
    return x[:n] if len(x) >= n else np.concatenate([x, np.zeros(n - len(x))])


def mix(dur, *layers):
    """layers: (signal, start_seconds, gain)"""
    out = np.zeros(int(dur * SR))
    for sig, start, gain in layers:
        i = int(start * SR)
        if i >= len(out):
            continue
        seg = sig[: len(out) - i]
        out[i:i + len(seg)] += seg * gain
    return out


def env_ad(n, attack, decay_tau, hold=0.0):
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    d = np.where(t < attack + hold, 1.0, np.exp(-(t - attack - hold) / decay_tau))
    return a * d


def env_swell(n, peak_at, release_tau, power=2.0):
    t = np.arange(n) / SR
    rise = np.clip(t / peak_at, 0, 1) ** power
    fall = np.where(t < peak_at, 1.0, np.exp(-(t - peak_at) / release_tau))
    return rise * fall


def osc(freq, n, shape="sine", phase=0.0):
    f = np.broadcast_to(np.asarray(freq, float), (n,))
    ph = 2 * math.pi * np.cumsum(f) / SR + phase
    if shape == "sine":
        return np.sin(ph)
    if shape == "saw":
        x = (ph / (2 * math.pi)) % 1.0
        return 2 * x - 1
    if shape == "tri":
        x = (ph / (2 * math.pi)) % 1.0
        return 4 * np.abs(x - 0.5) - 1
    raise ValueError(shape)


def noise(n):
    return RNG.standard_normal(n)


def fft_filter(x, lo=None, hi=None, slope=2.0):
    """Static band-limit with smooth roll-off (zero phase)."""
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    g = np.ones_like(f)
    if lo:
        g *= 1 / (1 + (lo / np.maximum(f, 1e-3)) ** (2 * slope))
    if hi:
        g *= 1 / (1 + (f / hi) ** (2 * slope))
    return np.fft.irfft(X * g, n)


def sweep_band(x, f0, f1, q=3.0, frame=1024, hop=256, log=True):
    """Time-varying band-pass (STFT) whose centre glides f0 -> f1."""
    n = len(x)
    win = np.hanning(frame)
    out = np.zeros(n + frame)
    norm = np.zeros(n + frame)
    freqs = np.fft.rfftfreq(frame, 1 / SR)
    xp = np.concatenate([x, np.zeros(frame)])
    count = max(1, (n) // hop)
    for k in range(count):
        i = k * hop
        t = i / max(n - 1, 1)
        fc = f0 * (f1 / f0) ** t if log else f0 + (f1 - f0) * t
        bw = fc / q
        g = np.exp(-0.5 * ((freqs - fc) / bw) ** 2)
        seg = np.fft.irfft(np.fft.rfft(xp[i:i + frame] * win) * g, frame)
        out[i:i + frame] += seg * win
        norm[i:i + frame] += win ** 2
    return out[:n] / np.maximum(norm[:n], 1e-3)


def reverb(x, seconds=1.2, damp=6000, wet=0.35, predelay=0.012):
    n_ir = int(seconds * SR)
    t = np.arange(n_ir) / SR
    ir = noise(n_ir) * np.exp(-t * 6.9 / seconds)
    ir = fft_filter(ir, lo=180, hi=damp)
    ir[: int(predelay * SR)] = 0
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
    n = len(x) + n_ir
    y = np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(ir, n), n)
    dry = np.concatenate([x, np.zeros(n_ir)])
    return dry * (1 - wet * 0.5) + y * wet


def soft_clip(x, drive=1.0):
    return np.tanh(x * drive) / np.tanh(drive)


# --------------------------------------------------------------- voices

def bell(freq, dur, decay=0.6, partials=((1, 1.0), (2.76, 0.55), (5.40, 0.28), (8.93, 0.14), (13.3, 0.06)), detune=0.002):
    n = int(dur * SR)
    out = np.zeros(n)
    for ratio, amp in partials:
        f = freq * ratio * (1 + RNG.uniform(-detune, detune))
        tau = decay / (1 + 0.6 * (ratio - 1))
        out += amp * osc(f, n) * env_ad(n, 0.002, tau)
    return out


def church_bell(freq, dur, decay=1.4):
    return bell(freq, dur, decay, ((0.5, 0.6), (1, 1.0), (1.19, 0.6), (1.5, 0.45), (2.0, 0.5), (2.52, 0.25), (3.0, 0.2), (4.1, 0.1)))


def thump(f0, f1, dur, tau=0.12):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t / (tau * 0.5))
    return osc(f, n) * env_ad(n, 0.003, tau)


def crack(dur=0.05, lo=2500):
    n = int(dur * SR)
    return fft_filter(noise(n), lo=lo) * env_ad(n, 0.0008, dur / 3)


def whoosh(dur, f0, f1, q=2.5, peak=0.35, release=0.18):
    n = int(dur * SR)
    return sweep_band(noise(n), f0, f1, q) * env_swell(n, peak * dur, release * dur + 0.02)


def shing(freq, dur, decay=0.35):
    """Crystalline blade ring: inharmonic high partials with a slight pitch fall."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for ratio, amp in ((1, 1.0), (1.51, 0.7), (2.23, 0.5), (2.97, 0.35), (4.1, 0.2)):
        f = freq * ratio * (1 - 0.03 * (1 - np.exp(-t / 0.08)))
        out += amp * osc(f, n) * env_ad(n, 0.001, decay / ratio ** 0.5)
    return out


def pad(freqs, dur, attack=0.3, release=0.5, detune=0.006, bright=2500, shape="saw"):
    n = int(dur * SR)
    out = np.zeros(n)
    for f in freqs:
        for d in (-detune, 0, detune):
            out += osc(f * (1 + d), n, shape, phase=RNG.uniform(0, 6.28))
    out = fft_filter(out, lo=60, hi=bright)
    t = np.arange(n) / SR
    env = np.clip(t / attack, 0, 1) * np.clip((dur - t) / release, 0, 1)
    return out * env / (len(freqs) * 3)


def sparkle(dur, count, fmin, fmax, decay=0.18, start=0.0, spread=None):
    n = int(dur * SR)
    out = np.zeros(n)
    span = spread if spread else dur * 0.7
    for _ in range(count):
        st = int((start + RNG.uniform(0, span)) * SR)
        if st >= n:
            continue
        b = bell(RNG.uniform(fmin, fmax), min(dur, 0.6), decay)
        seg = b[: n - st]
        out[st:st + len(seg)] += seg * RNG.uniform(0.3, 1.0)
    return out


def rumble(dur, cutoff=180, attack=0.2):
    n = int(dur * SR)
    return fft_filter(noise(n), lo=25, hi=cutoff) * env_swell(n, attack, dur * 0.4)


def reverse(x):
    return x[::-1].copy()


# ------------------------------------------------------------- the sounds

def s_solar_slash():
    d = 0.75
    return reverb(mix(d,
                      (whoosh(0.32, 900, 5200, 2.2, 0.45), 0.0, 0.55),
                      (shing(2100, 0.6, 0.32), 0.05, 0.42),
                      (shing(3150, 0.5, 0.22), 0.06, 0.22),
                      (crack(0.03, 4000), 0.05, 0.25),
                      (sparkle(0.5, 6, 3500, 7000, 0.1, 0.06, 0.2), 0.0, 0.12)), 0.9, 7000, 0.3)


def s_solar_hit():
    d = 0.6
    return reverb(mix(d,
                      (thump(160, 60, 0.3, 0.09), 0.0, 0.9),
                      (crack(0.04, 2000), 0.0, 0.5),
                      (bell(1760, 0.5, 0.28), 0.0, 0.35),
                      (bell(2640, 0.4, 0.2), 0.005, 0.2)), 0.8, 6500, 0.28)


def s_spear_cast():
    d = 1.2
    notes = [1046.5, 1318.5, 1568.0, 2093.0]
    layers = [(bell(f, 0.9, 0.5), 0.07 * i, 0.32) for i, f in enumerate(notes)]
    layers.append((whoosh(1.0, 600, 6000, 3.0, 0.8, 0.15), 0.0, 0.35))
    layers.append((sparkle(1.0, 10, 4000, 8000, 0.12, 0.2, 0.7), 0.0, 0.1))
    return reverb(mix(d, *layers), 1.4, 7500, 0.4)


def s_spear_fall():
    d = 0.6
    n = int(0.55 * SR)
    t = np.arange(n) / SR
    tone = osc(1500 * np.exp(-t * 3.2) + 180, n) * env_swell(n, 0.25, 0.25) * 0.25
    return reverb(mix(d, (whoosh(0.55, 7000, 600, 2.0, 0.6, 0.1), 0.0, 0.8), (tone, 0.0, 1.0)), 0.6, 6000, 0.25)


def s_spear_impact():
    d = 2.0
    blast = fft_filter(noise(int(1.0 * SR)), lo=40, hi=3000) * env_ad(int(1.0 * SR), 0.003, 0.22)
    return reverb(soft_clip(mix(d,
                                (thump(110, 38, 0.8, 0.3), 0.0, 1.0),
                                (blast, 0.0, 0.55),
                                (church_bell(392, 1.8, 1.2), 0.0, 0.45),
                                (crack(0.06, 1800), 0.0, 0.6),
                                (sparkle(1.2, 14, 2500, 7500, 0.15, 0.03, 0.5), 0.0, 0.12)), 1.4), 1.8, 6000, 0.4)


def s_solar_crown():
    d = 1.9
    chord = pad([440, 554.4, 659.3, 880], 1.8, attack=0.25, release=0.9, bright=3200)
    # vowel-ish formants for a choir colour
    choir = sweep_band(chord, 700, 1100, 1.6) * 1.6 + chord * 0.5
    return reverb(mix(d,
                      (choir, 0.0, 0.9),
                      (bell(1760, 1.4, 0.9), 0.05, 0.25),
                      (bell(2217, 1.2, 0.8), 0.12, 0.18),
                      (sparkle(1.6, 16, 3000, 8000, 0.2, 0.0, 1.2), 0.0, 0.12),
                      (whoosh(0.8, 400, 4000, 2.0, 0.6, 0.2), 0.0, 0.3)), 2.0, 7000, 0.45)


def s_void_crescent():
    d = 0.8
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    hum = osc(95 * np.exp(-t * 1.0), n) * env_swell(n, 0.12, 0.2)
    ring = bell(310, 0.6, 0.35, ((1, 1.0), (1.52, 0.6), (2.23, 0.4), (3.1, 0.2)))
    return reverb(mix(d,
                      (whoosh(0.45, 260, 1800, 2.0, 0.5, 0.2), 0.0, 0.85),
                      (hum, 0.0, 0.7),
                      (ring, 0.06, 0.25),
                      (fft_filter(crack(0.05, 600), hi=2500), 0.07, 0.3)), 1.0, 3000, 0.35)


def s_void_hit():
    d = 0.65
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    pop = osc(900 * np.exp(-t * 18) + 90, n) * env_ad(n, 0.001, 0.08)
    swell = reverse(fft_filter(noise(int(0.2 * SR)), lo=200, hi=2500) * env_ad(int(0.2 * SR), 0.001, 0.06))
    return reverb(mix(d,
                      (swell, 0.0, 0.35),
                      (thump(110, 38, 0.4, 0.14), 0.18, 1.0),
                      (pop, 0.18, 0.4),
                      (fft_filter(noise(int(0.25 * SR)), hi=900) * env_ad(int(0.25 * SR), 0.002, 0.06), 0.18, 0.5)), 0.9, 2500, 0.3)


def s_abyss_field():
    d = 1.8
    n = int(1.7 * SR)
    t = np.arange(n) / SR
    drone = osc(55, n) * (0.7 + 0.3 * np.sin(2 * math.pi * 5 * t)) * env_swell(n, 0.35, 0.8)
    swirl = sweep_band(noise(n), 200, 2400, 3.5) * env_swell(n, 0.6, 0.5)
    swirl2 = sweep_band(noise(n), 2200, 300, 4.0) * env_swell(n, 0.5, 0.5)
    rev = reverse(fft_filter(noise(int(0.5 * SR)), lo=500, hi=6000) * env_ad(int(0.5 * SR), 0.001, 0.15))
    return reverb(mix(d, (rev, 0.0, 0.3), (drone, 0.1, 0.9), (swirl, 0.15, 0.6), (swirl2, 0.3, 0.4),
                      (thump(80, 35, 0.6, 0.25), 0.45, 0.8)), 1.6, 2500, 0.4)


def s_field_pulse():
    d = 0.45
    return reverb(mix(d, (thump(85, 45, 0.3, 0.1), 0.0, 0.8),
                      (fft_filter(noise(int(0.25 * SR)), lo=150, hi=1200) * env_ad(int(0.25 * SR), 0.01, 0.07), 0.0, 0.35)), 0.6, 2000, 0.3)


def s_moonfall_charge():
    d = 1.4
    n = int(1.35 * SR)
    t = np.arange(n) / SR
    choir = pad([110, 130.8, 164.8, 220], 1.35, attack=0.4, release=0.25, bright=1400)
    choir = sweep_band(choir, 400, 750, 1.5) * 1.8 + choir * 0.4
    rise = osc(60 + 50 * (t / t[-1]) ** 2, n, "saw")
    rise = fft_filter(rise, hi=500) * env_swell(n, 1.1, 0.1, 1.5)
    swell = reverse(fft_filter(noise(int(0.6 * SR)), lo=300, hi=5000) * env_ad(int(0.6 * SR), 0.001, 0.2))
    return reverb(mix(d, (rumble(1.35, 160, 1.0), 0.0, 0.8), (choir, 0.0, 0.7), (rise, 0.0, 0.35), (swell, 0.75, 0.45)), 1.4, 2500, 0.38)


def s_moonfall_impact():
    d = 2.4
    blast = fft_filter(noise(int(1.2 * SR)), lo=30, hi=1800) * env_ad(int(1.2 * SR), 0.004, 0.3)
    crunch = soft_clip(fft_filter(noise(int(0.3 * SR)), lo=300, hi=2500) * 3, 2.5) * env_ad(int(0.3 * SR), 0.001, 0.07)
    return reverb(soft_clip(mix(d,
                                (thump(70, 26, 1.2, 0.45), 0.0, 1.2),
                                (blast, 0.0, 0.7),
                                (crunch, 0.0, 0.35),
                                (bell(196, 1.6, 0.9, ((1, 1.0), (1.48, 0.5), (2.31, 0.4), (3.2, 0.2))), 0.0, 0.3),
                                (sparkle(1.6, 18, 3000, 9000, 0.14, 0.08, 0.9), 0.0, 0.1)), 1.6), 2.2, 2400, 0.45)


def s_eclipse_activate():
    d = 2.0
    gold = pad([523.3, 659.3, 784.0], 1.6, attack=0.05, release=1.2, bright=4000)
    void = pad([220, 261.6, 329.6], 1.6, attack=0.05, release=1.2, bright=1200)
    return reverb(mix(d,
                      (whoosh(0.5, 300, 6000, 2.0, 0.85, 0.1), 0.0, 0.5),
                      (thump(140, 40, 0.6, 0.2), 0.38, 1.0),
                      (church_bell(523.3, 1.6, 1.1), 0.38, 0.35),
                      (gold, 0.38, 0.6), (void, 0.38, 0.7),
                      (sparkle(1.2, 20, 2500, 9000, 0.18, 0.4, 0.8), 0.0, 0.12)), 2.0, 5000, 0.45)


def s_eclipse_charge():
    d = 2.3
    n = int(2.0 * SR)
    t = np.arange(n) / SR
    k = t / t[-1]
    riser = osc(80 * (5 ** (k ** 1.6)), n, "saw")
    riser = sweep_band(riser, 300, 5000, 1.2) * (0.3 + 0.7 * k ** 1.5)
    trem = 0.6 + 0.4 * np.sin(2 * math.pi * (3 + 14 * k ** 2) * t)
    noise_rise = sweep_band(noise(n), 200, 7000, 1.5) * k ** 2.2
    choir = pad([220, 277.2, 329.6, 440, 554.4], 2.0, attack=1.2, release=0.08, bright=2500)
    choir = sweep_band(choir, 600, 1200, 1.6) * 1.6
    sub = osc(45, n) * k ** 2 * 0.6
    body = (riser * 0.5 + noise_rise * 0.5) * trem + choir * 0.55 + sub
    wet = reverb(mix(d, (body, 0.0, 1.0), (rumble(2.0, 120, 1.6), 0.0, 0.6)), 0.9, 4000, 0.25)
    tt = np.arange(len(wet)) / SR
    return wet * np.clip((2.02 - tt) / 0.1, 0, 1)   # hard stop: silence for the black-eclipse hit-stop


def s_eclipse_rumble():
    d = 1.4
    suck = reverse(sweep_band(noise(int(0.45 * SR)), 300, 5000, 2.0) * env_ad(int(0.45 * SR), 0.001, 0.15))
    return mix(d, (rumble(1.3, 110, 0.15), 0.0, 1.1), (osc(34, int(1.2 * SR)) * env_swell(int(1.2 * SR), 0.1, 0.5), 0.0, 0.6),
               (suck, 0.0, 0.5))


def s_eclipse_impact():
    d = 3.0
    blast = fft_filter(noise(int(1.6 * SR)), lo=25, hi=2600) * env_ad(int(1.6 * SR), 0.003, 0.4)
    crunch = soft_clip(fft_filter(noise(int(0.35 * SR)), lo=250, hi=3500) * 3, 3) * env_ad(int(0.35 * SR), 0.001, 0.08)
    ring = bell(262, 2.2, 1.4, ((0.5, 0.5), (1, 1.0), (1.19, 0.55), (1.5, 0.5), (2.0, 0.4), (2.52, 0.25), (3.0, 0.2)))
    return reverb(soft_clip(mix(d,
                                (thump(90, 22, 1.6, 0.55), 0.0, 1.3),
                                (blast, 0.0, 0.8),
                                (crunch, 0.0, 0.45),
                                (crack(0.08, 1500), 0.0, 0.6),
                                (ring, 0.0, 0.35)), 1.8), 2.8, 3500, 0.5)


def s_eclipse_burst():
    d = 2.6
    gold = pad([659.3, 784.0, 987.8, 1318.5], 2.0, attack=0.02, release=1.6, bright=6000, shape="tri")
    void = pad([164.8, 196.0, 246.9], 2.0, attack=0.02, release=1.6, bright=900)
    return reverb(mix(d,
                      (sparkle(2.2, 40, 2000, 10000, 0.22, 0.0, 1.4), 0.0, 0.3),
                      (whoosh(1.2, 8000, 800, 1.6, 0.05, 0.6), 0.0, 0.4),
                      (gold, 0.0, 0.5), (void, 0.0, 0.6)), 2.6, 7000, 0.5)


def s_eclipse_ready():
    d = 1.1
    return reverb(mix(d, (bell(1318.5, 0.9, 0.5), 0.0, 0.45), (bell(987.8, 0.9, 0.55), 0.12, 0.45),
                      (sparkle(0.7, 8, 4000, 9000, 0.1, 0.0, 0.3), 0.0, 0.12)), 1.2, 7000, 0.4)


def s_select():
    d = 0.5
    return reverb(mix(d, (bell(2349, 0.35, 0.12), 0.0, 0.5), (bell(3136, 0.3, 0.1), 0.045, 0.4),
                      (crack(0.015, 5000), 0.0, 0.15)), 0.4, 8000, 0.25)


SOUNDS = {
    # id: (file, builder, volume, max_distance)
    "solaris.slash": ("solar_slash", s_solar_slash, 0.9, 32),
    "solaris.slash_hit": ("solar_slash_hit", s_solar_hit, 0.9, 32),
    "solaris.spear_cast": ("solar_spear_cast", s_spear_cast, 0.85, 40),
    "solaris.spear_fall": ("solar_spear_fall", s_spear_fall, 0.9, 40),
    "solaris.spear_impact": ("solar_spear_impact", s_spear_impact, 1.0, 48),
    "solaris.crown": ("solar_crown", s_solar_crown, 0.9, 40),
    "noctis.crescent": ("void_crescent", s_void_crescent, 0.9, 32),
    "noctis.crescent_hit": ("void_crescent_hit", s_void_hit, 0.9, 32),
    "noctis.field": ("void_abyss_field", s_abyss_field, 0.95, 40),
    "noctis.field_pulse": ("void_field_pulse", s_field_pulse, 0.7, 24),
    "noctis.moonfall_charge": ("void_moonfall_charge", s_moonfall_charge, 0.95, 48),
    "noctis.moonfall_impact": ("void_moonfall_impact", s_moonfall_impact, 1.0, 56),
    "eclipse.activate": ("eclipse_activate", s_eclipse_activate, 1.0, 48),
    "eclipse.charge": ("eclipse_charge", s_eclipse_charge, 1.0, 64),
    "eclipse.rumble": ("eclipse_rumble", s_eclipse_rumble, 1.0, 64),
    "eclipse.impact": ("eclipse_impact", s_eclipse_impact, 1.0, 72),
    "eclipse.burst": ("eclipse_burst", s_eclipse_burst, 0.95, 64),
    "eclipse.ready": ("eclipse_ready", s_eclipse_ready, 0.8, 16),
    "eclipse.select": ("eclipse_select", s_select, 0.5, 8),
}


def _wav_bytes(x):
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def finish(x, peak_db=-1.0, fade=0.03):
    x = x - np.mean(x)
    # trim trailing silence
    thr = 10 ** (-60 / 20) * np.max(np.abs(x))
    idx = np.nonzero(np.abs(x) > thr)[0]
    if len(idx):
        x = x[: min(len(x), idx[-1] + int(0.05 * SR))]
    n = int(fade * SR)
    if len(x) > n:
        x[-n:] *= np.linspace(1, 0, n)
    peak = np.max(np.abs(x)) + 1e-9
    return x / peak * 10 ** (peak_db / 20)


def build_all(out_dir, keep_wav_dir=None):
    os.makedirs(out_dir, exist_ok=True)
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required to encode .ogg sounds")
    defs = {}
    for sid, (fname, fn, vol, maxd) in SOUNDS.items():
        x = finish(fn())
        wav = _wav_bytes(x)
        ogg = os.path.join(out_dir, fname + ".ogg")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "wav", "-i", "pipe:0", "-c:a", "libvorbis",
                        "-q:a", "5", "-ac", "1", ogg], input=wav, check=True)
        if keep_wav_dir:
            os.makedirs(keep_wav_dir, exist_ok=True)
            with open(os.path.join(keep_wav_dir, fname + ".wav"), "wb") as f:
                f.write(wav)
        defs[sid] = {"category": "player", "min_distance": 4.0, "max_distance": float(maxd),
                     "sounds": [{"name": f"sounds/eclipse/{fname}", "volume": vol, "load_on_low_memory": True}]}
    return defs


if __name__ == "__main__":
    import time
    t = time.time()
    d = build_all("/tmp/claude-0/snd", "/tmp/claude-0/snd_wav")
    print(len(d), "sounds in", round(time.time() - t, 1), "s")
