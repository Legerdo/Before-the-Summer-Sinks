"""Procedural ambience loops and sound effects (no external samples => no licensing issues).

Writes Ogg Vorbis to public/audio/amb and public/audio/se and public/data/sfx.json.
Usage: python synth.py [name ...]
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, fftconvolve, sosfilt, sosfiltfilt

ROOT = Path(__file__).resolve().parents[2]
SR = 44100
rng = np.random.default_rng(20260930)
OUT_AMB = ROOT / "public" / "audio" / "amb"
OUT_SE = ROOT / "public" / "audio" / "se"
TMP = ROOT / "art_work" / "sfx"


# ------------------------------------------------------------------ primitives
def t_axis(sec):
    return np.arange(int(sec * SR)) / SR


def white(n):
    return rng.standard_normal(n).astype(np.float32)


def pink(n):
    w = rng.standard_normal(n)
    f = np.fft.rfft(w)
    k = np.arange(len(f))
    k[0] = 1
    f /= np.sqrt(k)
    x = np.fft.irfft(f, n)
    return (x / (np.abs(x).max() + 1e-9)).astype(np.float32)


def brown(n):
    x = np.cumsum(rng.standard_normal(n))
    x -= np.convolve(x, np.ones(4001) / 4001, mode="same")
    return (x / (np.abs(x).max() + 1e-9)).astype(np.float32)


def bp(x, lo, hi, order=4):
    sos = butter(order, [lo, hi], btype="band", fs=SR, output="sos")
    return sosfilt(sos, x).astype(np.float32)


def lp(x, f, order=4):
    return sosfilt(butter(order, f, btype="low", fs=SR, output="sos"), x).astype(np.float32)


def hp(x, f, order=4):
    return sosfilt(butter(order, f, btype="high", fs=SR, output="sos"), x).astype(np.float32)


def smooth_noise(n, rate_hz, lo=0.0, hi=1.0):
    """Slowly varying random control signal."""
    k = max(2, int(n / SR * rate_hz) + 2)
    pts = rng.uniform(lo, hi, k)
    xs = np.linspace(0, n, k)
    return np.interp(np.arange(n), xs, pts).astype(np.float32)


def env_adsr(n, a, d, s, r):
    e = np.ones(n, np.float32) * s
    na, nd, nr = int(a * SR), int(d * SR), int(r * SR)
    na = min(na, n)
    e[:na] = np.linspace(0, 1, na)
    e[na:na + nd] = np.linspace(1, s, len(e[na:na + nd]))
    if nr > 0:
        e[-nr:] *= np.linspace(1, 0, min(nr, n))
    return e


def exp_env(n, tau):
    return np.exp(-np.arange(n) / (tau * SR)).astype(np.float32)


def reverb(x, sec=1.2, decay=3.0, wet=0.25, stereo=True):
    n = int(sec * SR)
    ir_l = white(n) * (np.linspace(1, 0, n) ** decay)
    ir_r = white(n) * (np.linspace(1, 0, n) ** decay)
    ir_l = lp(ir_l, 7000)
    ir_r = lp(ir_r, 7000)
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    wl = fftconvolve(x[:, 0], ir_l)[: len(x)]
    wr = fftconvolve(x[:, 1], ir_r if stereo else ir_l)[: len(x)]
    w = np.stack([wl, wr], 1)
    w /= np.abs(w).max() + 1e-9
    return (x * (1 - wet) + w * wet * np.abs(x).max()).astype(np.float32)


def pan(x, p):
    """p in [-1, 1]"""
    a = (p + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], 1).astype(np.float32)


def stereo_noise_bed(n, color="pink"):
    f = {"pink": pink, "white": white, "brown": brown}[color]
    return np.stack([f(n), f(n)], 1)


def make_loop(x, xf=2.0):
    """Crossfade the tail into the head so the buffer loops seamlessly."""
    X = int(xf * SR)
    out = x[:-X].copy()
    fade = np.linspace(0, 1, X)[:, None] if x.ndim == 2 else np.linspace(0, 1, X)
    out[:X] = out[:X] * np.sqrt(fade) + x[-X:] * np.sqrt(1 - fade)
    return out


def norm(x, peak=0.9):
    return (x / (np.abs(x).max() + 1e-9) * peak).astype(np.float32)


def rms_norm(x, db=-20):
    r = np.sqrt(np.mean(x ** 2)) + 1e-9
    y = x * (10 ** (db / 20) / r)
    pk = np.abs(y).max()
    if pk > 0.98:
        y *= 0.98 / pk
    return y.astype(np.float32)


def place(buf, clip, at):
    i = int(at * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(clip))
    buf[i:j] += clip[: j - i]


# ------------------------------------------------------------------ ambience
def amb_cicada(sec=40, far=False):
    n = int(sec * SR)
    out = np.zeros((n, 2), np.float32)
    voices = 5 if not far else 4
    for k in range(voices):
        f0 = rng.uniform(4300, 6800)
        carrier = bp(white(n), f0 * 0.82, min(f0 * 1.22, 20000), 3)
        buzz = 0.55 + 0.45 * np.sin(2 * np.pi * rng.uniform(38, 70) * t_axis(sec) + rng.uniform(0, 6))
        # "maem-maem" phrasing: bursts with swells, then silence
        ctl = np.zeros(n, np.float32)
        t = rng.uniform(0, 4)
        while t < sec:
            dur = rng.uniform(4, 11)
            rate = rng.uniform(1.6, 2.6)
            tt = t_axis(dur)
            ph = np.sin(2 * np.pi * rate * tt) * 0.5 + 0.5
            shape = np.minimum(1, tt / 1.2) * np.minimum(1, (dur - tt) / 1.8)
            seg = (0.35 + 0.65 * ph ** 2) * shape
            place(ctl, seg.astype(np.float32), t)
            t += dur + rng.uniform(0.5, 5)
        v = carrier * buzz * ctl
        out += pan(v, rng.uniform(-0.8, 0.8)) * rng.uniform(0.5, 1.0)
    bed = stereo_noise_bed(n, "pink")
    bed = np.stack([lp(bed[:, 0], 900), lp(bed[:, 1], 900)], 1) * 0.08 * smooth_noise(n, 0.2, 0.4, 1.0)[:, None]
    out = out + bed
    if far:
        out = np.stack([lp(out[:, 0], 5200), lp(out[:, 1], 5200)], 1)
    out = reverb(out, 1.4, 2.5, 0.35)
    return rms_norm(make_loop(out), -26 if far else -22)


def bubble(f0, dur, tau):
    tt = t_axis(dur)
    f = f0 * (1 + 0.9 * tt / dur)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) * exp_env(len(tt), tau)).astype(np.float32)


def amb_stream(sec=36, lake=False):
    n = int(sec * SR)
    bed = stereo_noise_bed(n, "pink")
    lo, hi = (120, 1400) if lake else (200, 3200)
    bed = np.stack([bp(bed[:, 0], lo, hi, 2), bp(bed[:, 1], lo, hi, 2)], 1)
    swell = smooth_noise(n, 0.35 if lake else 1.2, 0.35, 1.0)[:, None]
    out = bed * swell * (0.6 if lake else 0.8)
    count = int(sec * (6 if lake else 38))
    for _ in range(count):
        f0 = rng.uniform(300, 1100) if lake else rng.uniform(500, 2400)
        b = bubble(f0, 0.08, rng.uniform(0.008, 0.03)) * rng.uniform(0.05, 0.22)
        place(out, pan(b, rng.uniform(-0.9, 0.9)), rng.uniform(0, sec - 0.1))
    if lake:
        # gentle lapping at the shore
        for _ in range(int(sec / 2.8)):
            d = rng.uniform(0.8, 1.6)
            lap = lp(white(int(d * SR)), 900) * env_adsr(int(d * SR), 0.25, 0.3, 0.4, 0.6) * 0.5
            place(out, pan(lap, rng.uniform(-0.5, 0.5)), rng.uniform(0, sec - d))
    out = reverb(out, 0.9, 2.2, 0.2)
    return rms_norm(make_loop(out), -24 if lake else -21)


def cricket(sec, f0, rate, burst):
    n = int(sec * SR)
    x = np.zeros(n, np.float32)
    t = rng.uniform(0, 1)
    while t < sec - 0.3:
        for k in range(burst):
            d = 0.018
            tt = t_axis(d)
            s = np.sin(2 * np.pi * f0 * tt) * np.sin(np.pi * tt / d) ** 2
            place(x, s.astype(np.float32), t + k * (1 / 32))
        t += 1 / rate * rng.uniform(0.9, 1.1)
    return x


def frog(sec):
    n = int(sec * SR)
    x = np.zeros(n, np.float32)
    t = rng.uniform(0, 3)
    f = rng.uniform(260, 420)
    while t < sec - 1:
        for k in range(rng.integers(2, 5)):
            d = rng.uniform(0.09, 0.14)
            tt = t_axis(d)
            src = np.sign(np.sin(2 * np.pi * f * tt)) * 0.6 + np.sin(2 * np.pi * 2 * f * tt) * 0.4
            s = bp(src.astype(np.float32), f * 0.8, f * 4, 2) * np.sin(np.pi * tt / d)
            place(x, s, t + k * 0.2)
        t += rng.uniform(2.5, 6)
    return x


def amb_night(sec=40, far=False):
    n = int(sec * SR)
    out = np.zeros((n, 2), np.float32)
    for k in range(9):
        c = cricket(sec, rng.uniform(3800, 5200), rng.uniform(1.1, 2.4), int(rng.integers(2, 5)))
        out += pan(c, rng.uniform(-0.9, 0.9)) * rng.uniform(0.08, 0.22)
    for k in range(3):
        out += pan(frog(sec), rng.uniform(-0.8, 0.8)) * rng.uniform(0.05, 0.1)
    wind = stereo_noise_bed(n, "pink")
    wind = np.stack([bp(wind[:, 0], 150, 900, 2), bp(wind[:, 1], 150, 900, 2)], 1) * smooth_noise(n, 0.15, 0.2, 1)[:, None] * 0.12
    out += wind
    if far:
        out = np.stack([lp(out[:, 0], 3000), lp(out[:, 1], 3000)], 1)
    out = reverb(out, 1.6, 2.4, 0.35)
    return rms_norm(make_loop(out), -28 if far else -24)


def drops(n, rate, lo, hi, amp):
    x = np.zeros(n, np.float32)
    cnt = int(n / SR * rate)
    for _ in range(cnt):
        d = rng.uniform(0.004, 0.012)
        tt = t_axis(d)
        c = bp(white(len(tt)), lo, hi, 2) * exp_env(len(tt), d / 3)
        place(x, c * rng.uniform(0.2, 1) * amp, rng.uniform(0, n / SR - 0.02))
    return x


def amb_rain(sec=30, heavy=False):
    n = int(sec * SR)
    bed = stereo_noise_bed(n, "pink")
    bed = np.stack([bp(bed[:, 0], 350, 9000, 2), bp(bed[:, 1], 350, 9000, 2)], 1)
    out = bed * (0.55 if heavy else 0.35) * smooth_noise(n, 0.4, 0.7, 1.0)[:, None]
    for ch in range(2):
        out[:, ch] += drops(n, 2600 if heavy else 900, 1500, 9000, 0.35)
    if heavy:
        wind = stereo_noise_bed(n, "brown")
        gust = smooth_noise(n, 0.18, 0.15, 1.0) ** 2
        wind = np.stack([bp(wind[:, 0], 80, 700, 2), bp(wind[:, 1], 80, 700, 2)], 1) * gust[:, None] * 1.4
        out += wind
        # far rumbles
        for _ in range(3):
            d = rng.uniform(3, 6)
            r = lp(brown(int(d * SR)), 140) * env_adsr(int(d * SR), 0.6, 1.0, 0.6, 2.0) * 0.9
            place(out, pan(r, rng.uniform(-0.6, 0.6)), rng.uniform(0, sec - d))
    out = reverb(out, 1.0, 2.0, 0.2)
    return rms_norm(make_loop(out), -19 if heavy else -23)


def amb_wind(sec=30):
    n = int(sec * SR)
    x = stereo_noise_bed(n, "pink")
    c = smooth_noise(n, 0.2, 0.25, 1.0)
    x = np.stack([bp(x[:, 0], 180, 1200, 2), bp(x[:, 1], 200, 1300, 2)], 1) * c[:, None]
    leaves = np.stack([hp(white(n), 3000), hp(white(n), 3000)], 1) * (c ** 3)[:, None] * 0.05
    return rms_norm(make_loop(reverb(x + leaves, 1.2, 2.5, 0.3)), -27)


def amb_room(sec=24, fan=True):
    n = int(sec * SR)
    tt = t_axis(sec)
    tone = stereo_noise_bed(n, "brown") * 0.2
    if fan:
        hum = sum(np.sin(2 * np.pi * 60 * k * tt) / k ** 1.5 for k in range(1, 6)) * 0.02
        blade = bp(white(n), 250, 2200, 2) * (0.65 + 0.35 * np.sin(2 * np.pi * 14.5 * tt)) * 0.25
        tone += np.stack([hum + blade, hum * 0.9 + blade * 0.8], 1)
    return rms_norm(make_loop(tone), -34)


def amb_equipment(sec=24):
    n = int(sec * SR)
    tt = t_axis(sec)
    hum = sum(np.sin(2 * np.pi * 60 * k * tt + k) / k ** 1.2 for k in range(1, 8)) * 0.02
    buzz = hp(white(n), 5000) * 0.004
    out = np.stack([hum + buzz, hum + buzz], 1) + amb_night(sec + 2.5, far=True)[: n] * 0.4
    return rms_norm(make_loop(out.astype(np.float32)), -34)


def amb_static(sec=16):
    n = int(sec * SR)
    x = stereo_noise_bed(n, "white")
    x = np.stack([bp(x[:, 0], 900, 6000, 2), bp(x[:, 1], 900, 6000, 2)], 1) * smooth_noise(n, 2, 0.5, 1)[:, None]
    crack = np.zeros(n, np.float32)
    for _ in range(int(sec * 30)):
        place(crack, white(40) * rng.uniform(0.2, 1.4), rng.uniform(0, sec - 0.01))
    x += np.stack([crack, crack], 1) * 0.3
    return rms_norm(make_loop(x), -26)


def amb_tape(sec=16):
    n = int(sec * SR)
    tt = t_axis(sec)
    hiss = np.stack([hp(pink(n), 3000), hp(pink(n), 3000)], 1) * 0.3
    motor = (np.sin(2 * np.pi * 50 * tt) * 0.02 + np.sin(2 * np.pi * 150 * tt) * 0.01)
    return rms_norm(make_loop(hiss + motor[:, None]), -33)


def amb_demolish(sec=40):
    n = int(sec * SR)
    tt = t_axis(sec)
    engine = sum(np.sin(2 * np.pi * 34 * k * tt * (1 + 0.01 * np.sin(2 * np.pi * 0.3 * tt))) / k for k in range(1, 8))
    engine = lp(engine.astype(np.float32), 400) * smooth_noise(n, 0.3, 0.4, 1) * 0.35
    out = pan(engine, -0.3)
    for _ in range(int(sec / 3)):
        d = 0.6
        thud = lp(white(int(d * SR)), 250) * exp_env(int(d * SR), 0.12) * rng.uniform(0.4, 0.9)
        place(out, pan(thud, rng.uniform(-0.7, 0.7)), rng.uniform(0, sec - d))
    for _ in range(int(sec / 4)):
        d = 0.5
        f = rng.uniform(900, 2200)
        clank = sum(np.sin(2 * np.pi * f * r * t_axis(d)) for r in (1, 1.47, 2.09, 2.83)) * exp_env(int(d * SR), 0.07) * 0.12
        place(out, pan(clank.astype(np.float32), rng.uniform(-0.8, 0.8)), rng.uniform(0, sec - d))
    out += amb_cicada(sec + 2.5, far=True)[:n] * 0.5
    out = reverb(out, 1.8, 2.0, 0.4)
    return rms_norm(make_loop(out), -24)


def amb_city(sec=36):
    n = int(sec * SR)
    x = stereo_noise_bed(n, "brown")
    x = np.stack([lp(x[:, 0], 320), lp(x[:, 1], 320)], 1) * smooth_noise(n, 0.1, 0.6, 1)[:, None]
    for _ in range(5):
        d = rng.uniform(4, 7)
        m = int(d * SR)
        car = bp(pink(m), 200, 1500, 2) * np.sin(np.pi * np.arange(m) / m) ** 2 * 0.5
        p = np.linspace(rng.uniform(-1, 0), rng.uniform(0, 1), m)
        place(x, np.stack([car * np.cos((p + 1) * np.pi / 4), car * np.sin((p + 1) * np.pi / 4)], 1), rng.uniform(0, sec - d))
    return rms_norm(make_loop(reverb(x, 1.5, 2, 0.3)), -30)


def amb_hall(sec=30):
    """Low indoor murmur: many filtered voice-like formant blobs, unintelligible."""
    n = int(sec * SR)
    out = amb_room(sec + 2.5, fan=False)[:n] * 0.6
    for _ in range(int(sec * 5)):
        d = rng.uniform(0.25, 0.7)
        m = int(d * SR)
        f0 = rng.uniform(95, 230)
        tt = t_axis(d)
        f = f0 * (1 + 0.08 * np.sin(2 * np.pi * rng.uniform(2, 5) * tt))
        ph = 2 * np.pi * np.cumsum(f) / SR
        src = sum(np.sin(k * ph) / k for k in range(1, 18)).astype(np.float32)
        form = bp(src, rng.uniform(350, 700), rng.uniform(1200, 2600), 2) * np.sin(np.pi * tt / d) ** 2 * rng.uniform(0.05, 0.15)
        place(out, pan(form, rng.uniform(-0.9, 0.9)), rng.uniform(0, sec - d))
    out = np.stack([lp(out[:, 0], 2500), lp(out[:, 1], 2500)], 1)
    return rms_norm(make_loop(reverb(out, 1.4, 2.2, 0.45)), -30)


# ------------------------------------------------------------------ one-shots
def se_click(f=2200, d=0.05, amp=0.5):
    n = int(d * SR)
    x = (bp(white(n), f * 0.6, f * 1.6, 2) * exp_env(n, 0.006)) + np.sin(2 * np.pi * f * 0.5 * t_axis(d)) * exp_env(n, 0.01) * 0.3
    return norm(x.astype(np.float32), amp)


def se_tone(freqs, d, tau, amp=0.5, shimmer=0.0):
    tt = t_axis(d)
    x = sum(np.sin(2 * np.pi * f * tt) * (0.6 ** i) for i, f in enumerate(freqs))
    if shimmer:
        x = x * (1 + shimmer * np.sin(2 * np.pi * 6 * tt))
    x = x * exp_env(len(tt), tau) * np.minimum(1, tt / 0.004)
    return norm(x.astype(np.float32), amp)


def seq(*parts):
    """parts: (clip, start_sec)"""
    end = max(s + len(c) / SR for c, s in parts)
    out = np.zeros(int(end * SR) + 10, np.float32)
    for c, s in parts:
        place(out, c, s)
    return out


def se_radio_tune():
    d = 2.2
    n = int(d * SR)
    tt = t_axis(d)
    noise = bp(white(n), 700, 6000, 2) * (0.5 + 0.5 * smooth_noise(n, 8, 0, 1))
    whistle_f = 600 + 2600 * np.abs(np.sin(2 * np.pi * 0.35 * tt + 0.4))
    whistle = np.sin(2 * np.pi * np.cumsum(whistle_f) / SR) * 0.18 * smooth_noise(n, 3, 0, 1)
    x = (noise * 0.5 + whistle) * env_adsr(n, 0.05, 0.1, 1, 0.5)
    # lock onto the station at the end
    return norm(lp(x.astype(np.float32), 5000), 0.6)


def se_static_burst():
    d = 0.7
    n = int(d * SR)
    return norm(bp(white(n), 900, 7000, 2) * env_adsr(n, 0.005, 0.1, 0.6, 0.4), 0.55)


def se_feedback():
    d = 2.4
    n = int(d * SR)
    tt = t_axis(d)
    f = 2350 * (1 + 0.004 * np.sin(2 * np.pi * 5 * tt))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.3 * np.sin(2 * np.pi * np.cumsum(f * 2.01) / SR)
    e = (tt / d) ** 2.2 * np.minimum(1, (d - tt) / 0.06)
    return norm((x * e).astype(np.float32), 0.45)


def se_mic_tap():
    d = 0.25
    n = int(d * SR)
    x = lp(white(n), 300) * exp_env(n, 0.03) + np.sin(2 * np.pi * 90 * t_axis(d)) * exp_env(n, 0.05)
    return norm(x.astype(np.float32), 0.7)


def se_clunk(heavy=1.0):
    d = 0.2
    n = int(d * SR)
    a = bp(white(n), 800, 4000, 2) * exp_env(n, 0.004)
    b = lp(white(n), 500) * exp_env(n, 0.02) * heavy
    return (a * 0.6 + b).astype(np.float32)


def se_tape_insert():
    return norm(seq((se_clunk(0.3), 0), (se_click(3500, 0.03, 0.6), 0.12), (se_clunk(1.0), 0.28)), 0.7)


def se_tape_play():
    return norm(seq((se_clunk(1.2), 0), (se_click(1800, 0.04, 0.4), 0.05)), 0.75)


def se_tape_stop():
    return norm(seq((se_clunk(1.4), 0)), 0.75)


def se_tape_rewind():
    d = 2.5
    tt = t_axis(d)
    f = 180 + 520 * np.minimum(1, tt / 1.2)
    motor = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.3 + bp(white(len(tt)), 1500, 6000, 2) * 0.25
    x = seq((se_clunk(1.0), 0), ((motor * env_adsr(len(tt), 0.2, 0.1, 1, 0.3)).astype(np.float32), 0.1), (se_clunk(1.3), 2.6))
    return norm(x, 0.6)


def se_switch():
    return norm(seq((se_click(2800, 0.03, 0.8), 0), (se_click(1500, 0.03, 0.5), 0.035)), 0.6)


def se_door_slide():
    d = 1.1
    n = int(d * SR)
    tt = t_axis(d)
    rumble = bp(white(n), 120, 900, 2) * (0.6 + 0.4 * np.sin(2 * np.pi * 23 * tt)) * env_adsr(n, 0.1, 0.2, 0.8, 0.3)
    rattle = bp(white(n), 2000, 5000, 2) * (np.sin(2 * np.pi * 11 * tt) > 0.7) * 0.2
    x = seq(((rumble + rattle).astype(np.float32), 0), (se_clunk(0.8), 1.0))
    return norm(reverb(x, 0.4, 3, 0.15)[:, 0], 0.6)


def se_knock():
    one = lambda: (lp(white(int(0.12 * SR)), 900) * exp_env(int(0.12 * SR), 0.012)).astype(np.float32)
    return norm(seq((one(), 0), (one(), 0.22), (one(), 0.44)), 0.7)


def step(soft=1.0):
    d = 0.16
    n = int(d * SR)
    x = bp(white(n), 150, 2500, 2) * exp_env(n, 0.035) + drops(n, 300, 2000, 6000, 0.3)
    return (x * soft).astype(np.float32)


def se_footsteps(nsteps=5, gap=0.42):
    return norm(seq(*[(step(rng.uniform(0.7, 1.0)), i * gap * rng.uniform(0.95, 1.05)) for i in range(nsteps)]), 0.5)


def se_splash():
    d = 1.0
    n = int(d * SR)
    x = bp(white(n), 400, 6000, 2) * env_adsr(n, 0.005, 0.15, 0.3, 0.6)
    for _ in range(40):
        place(x, bubble(rng.uniform(500, 2000), 0.07, 0.02) * 0.3, rng.uniform(0, 0.8))
    return norm(x.astype(np.float32), 0.6)


def se_phone_ring():
    tt = t_axis(1.6)
    bell = (np.sin(2 * np.pi * 1100 * tt) + np.sin(2 * np.pi * 1350 * tt) * 0.8) * (np.sin(2 * np.pi * 20 * tt) > 0)
    bell = bell * np.minimum(1, tt / 0.01) * np.minimum(1, (1.6 - tt) / 0.05)
    one = bp(bell.astype(np.float32), 600, 4000, 2)
    return norm(seq((one, 0), (one, 3.0)), 0.5)


def se_pickup():
    return norm(seq((se_clunk(1.0), 0), (se_click(1200, 0.04, 0.3), 0.08)), 0.6)


def se_thunder(close=False):
    d = 6.0 if close else 7.5
    n = int(d * SR)
    x = lp(brown(n), 220 if close else 150) * env_adsr(n, 0.02 if close else 0.8, 0.8, 0.7, 3.5) * smooth_noise(n, 3, 0.4, 1)
    if close:
        crack = hp(white(int(0.4 * SR)), 900) * exp_env(int(0.4 * SR), 0.08) * 0.8
        x = seq((x.astype(np.float32), 0.05), (crack.astype(np.float32), 0))
    return norm(reverb(x, 2.5, 1.8, 0.4)[:, 0], 0.95)


def se_bell_school():
    notes = [659.25, 523.25, 587.33, 392.0, 392.0, 587.33, 659.25, 523.25]
    parts = []
    for i, f in enumerate(notes):
        parts.append((se_tone([f, f * 2.76, f * 5.4], 1.8, 0.6, 0.5), i * 0.62))
    return norm(reverb(seq(*parts), 2.0, 2.0, 0.35)[:, 0], 0.55)


def se_chime():
    parts = [(se_tone([f, f * 2.9], 2.4, 0.9, 0.3), rng.uniform(0, 1.2)) for f in (1568, 1760, 2093, 2349, 2637)]
    return norm(reverb(seq(*parts), 2.0, 2.2, 0.4)[:, 0], 0.45)


def se_heartbeat():
    beat = lambda a: (lp(white(int(0.15 * SR)), 120) * exp_env(int(0.15 * SR), 0.03) * a + np.sin(2 * np.pi * 55 * t_axis(0.15)) * exp_env(int(0.15 * SR), 0.04) * a).astype(np.float32)
    return norm(seq((beat(1), 0), (beat(0.7), 0.22), (beat(1), 0.95), (beat(0.7), 1.17)), 0.8)


def se_bus_arrive():
    d = 5.0
    n = int(d * SR)
    tt = t_axis(d)
    f = 42 * (1 - 0.3 * np.minimum(1, tt / 3.5))
    eng = sum(np.sin(2 * np.pi * np.cumsum(f * k) / SR) / k for k in range(1, 9)).astype(np.float32)
    eng = lp(eng, 700) * env_adsr(n, 1.2, 0.5, 0.9, 1.0) * 0.6
    brake = hp(white(int(1.0 * SR)), 2500) * env_adsr(int(1.0 * SR), 0.02, 0.2, 0.6, 0.6) * 0.3
    return norm(reverb(seq((eng, 0), (brake.astype(np.float32), 3.6), (se_clunk(1.2), 4.4)), 1.0, 2.5, 0.2)[:, 0], 0.7)


def se_bus_leave():
    d = 6.0
    n = int(d * SR)
    tt = t_axis(d)
    f = 30 + 40 * np.minimum(1, tt / 4)
    eng = sum(np.sin(2 * np.pi * np.cumsum(f * k) / SR) / k for k in range(1, 9)).astype(np.float32)
    eng = lp(eng, 800) * env_adsr(n, 0.5, 0.5, 0.9, 3.0) * np.linspace(1, 0.3, n)
    return norm(reverb(seq((se_clunk(1.0), 0), (eng.astype(np.float32), 0.3)), 1.2, 2.5, 0.25)[:, 0], 0.7)


def se_soda():
    pop = hp(white(int(0.05 * SR)), 600) * exp_env(int(0.05 * SR), 0.008)
    fizz = bp(white(int(1.4 * SR)), 3000, 11000, 2) * env_adsr(int(1.4 * SR), 0.01, 0.3, 0.4, 0.8) * 0.4
    return norm(seq((pop.astype(np.float32), 0), (fizz.astype(np.float32), 0.02)), 0.6)


def se_power_down():
    d = 1.6
    tt = t_axis(d)
    f = 120 * np.exp(-tt * 1.2)
    hum = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.linspace(1, 0, len(tt)) * 0.5
    return norm(seq((se_clunk(1.4), 0), (hum.astype(np.float32), 0.02)), 0.7)


def se_power_up():
    d = 1.4
    tt = t_axis(d)
    f = 40 + 80 * np.minimum(1, tt / 0.8)
    hum = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, tt / 0.5) * 0.35 * np.minimum(1, (d - tt) / 0.3)
    return norm(seq((se_click(2600, 0.03, 0.8), 0), (hum.astype(np.float32), 0.05)), 0.6)


def se_paper():
    d = 0.6
    n = int(d * SR)
    x = bp(white(n), 1500, 8000, 2) * smooth_noise(n, 30, 0, 1) ** 2 * env_adsr(n, 0.02, 0.1, 0.8, 0.2)
    return norm(x.astype(np.float32), 0.45)


def se_crash():
    d = 3.0
    n = int(d * SR)
    x = lp(white(n), 400) * exp_env(n, 0.5) + drops(n, 200, 800, 5000, 0.6) * exp_env(n, 0.8)
    return norm(reverb(x.astype(np.float32), 1.5, 2, 0.3)[:, 0], 0.8)


def ui_hover():
    return se_tone([1900], 0.05, 0.012, 0.18)


def ui_click():
    return seq((se_click(2600, 0.03, 0.4), 0), (se_tone([1320], 0.08, 0.02, 0.2), 0.0))


def ui_confirm():
    return norm(seq((se_tone([880, 1760], 0.3, 0.1, 0.35), 0), (se_tone([1318.5, 2637], 0.45, 0.16, 0.35), 0.07)), 0.45)


def ui_cancel():
    return norm(seq((se_tone([988], 0.18, 0.06, 0.3), 0), (se_tone([740], 0.25, 0.08, 0.3), 0.06)), 0.4)


def ui_choice():
    return norm(seq((se_tone([1046.5, 2093], 0.4, 0.14, 0.3), 0), (se_tone([1568, 3136], 0.6, 0.2, 0.3), 0.08), (se_tone([2093], 0.6, 0.25, 0.2), 0.16)), 0.45)


def ui_save():
    return norm(seq((se_tone([1318.5], 0.4, 0.12, 0.3), 0), (se_tone([1760], 0.5, 0.15, 0.3), 0.09), (se_tone([2637], 0.7, 0.2, 0.2), 0.18)), 0.4)


def ui_tick():
    return se_click(3200, 0.02, 0.3)


AMB = {
    "cicada": (lambda: amb_cicada(40), 1.0), "cicada_far": (lambda: amb_cicada(40, far=True), 1.0),
    "stream": (lambda: amb_stream(36), 1.0), "lake": (lambda: amb_stream(40, lake=True), 1.0),
    "night": (lambda: amb_night(40), 1.0), "night_far": (lambda: amb_night(40, far=True), 1.0),
    "rain": (lambda: amb_rain(30), 1.0), "storm": (lambda: amb_rain(30, heavy=True), 1.0),
    "wind": (lambda: amb_wind(30), 1.0), "room": (lambda: amb_room(24), 1.0), "equipment": (lambda: amb_equipment(24), 1.0),
    "static": (lambda: amb_static(16), 0.8), "tape_hiss": (lambda: amb_tape(16), 1.0), "demolish": (lambda: amb_demolish(40), 1.0),
    "city": (lambda: amb_city(36), 1.0), "hall": (lambda: amb_hall(30), 1.0),
}
SE = {
    "radio_tune": (se_radio_tune, 0.8), "static_burst": (se_static_burst, 0.7), "feedback": (se_feedback, 0.6),
    "mic_tap": (se_mic_tap, 0.8), "tape_insert": (se_tape_insert, 0.9), "tape_play": (se_tape_play, 0.9),
    "tape_stop": (se_tape_stop, 0.9), "tape_rewind": (se_tape_rewind, 0.8), "switch": (se_switch, 0.8),
    "door_slide": (se_door_slide, 0.8), "knock": (se_knock, 0.8), "footsteps": (lambda: se_footsteps(5), 0.7),
    "footsteps_run": (lambda: se_footsteps(9, 0.24), 0.7), "splash": (se_splash, 0.8), "phone_ring": (se_phone_ring, 0.7),
    "pickup": (se_pickup, 0.8), "thunder": (lambda: se_thunder(False), 1.0), "thunder_close": (lambda: se_thunder(True), 1.0),
    "school_bell": (se_bell_school, 0.7), "chime": (se_chime, 0.7), "heartbeat": (se_heartbeat, 0.9),
    "bus_arrive": (se_bus_arrive, 0.8), "bus_leave": (se_bus_leave, 0.8), "soda": (se_soda, 0.8),
    "power_down": (se_power_down, 0.9), "power_up": (se_power_up, 0.9), "paper": (se_paper, 0.7), "crash": (se_crash, 0.9),
    "ui_hover": (ui_hover, 0.6), "ui_click": (ui_click, 0.8), "ui_confirm": (ui_confirm, 0.8), "ui_cancel": (ui_cancel, 0.8),
    "ui_choice": (ui_choice, 0.8), "ui_save": (ui_save, 0.8), "ui_tick": (ui_tick, 0.7),
}


def write(x: np.ndarray, path: Path):
    TMP.mkdir(parents=True, exist_ok=True)
    wav = TMP / (path.stem + ".wav")
    sf.write(str(wav), x, SR, subtype="PCM_16")
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(wav), "-c:a", "libvorbis", "-q:a", "4", str(path)], check=True)


def main():
    only = set(sys.argv[1:])
    meta_p = ROOT / "public" / "data" / "sfx.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {"amb": {}, "se": {}}
    for name, (fn, vol) in AMB.items():
        if only and name not in only:
            continue
        write(fn(), OUT_AMB / f"{name}.ogg")
        meta["amb"][name] = {"src": f"audio/amb/{name}.ogg", "vol": vol}
        print("amb", name, flush=True)
    for name, (fn, vol) in SE.items():
        if only and name not in only:
            continue
        x = fn()
        if x.ndim == 1:
            x = np.stack([x, x], 1)
        min_len = int(0.15 * SR)  # tiny clicks still need a real buffer after Vorbis encoding
        if len(x) < min_len:
            x = np.concatenate([x, np.zeros((min_len - len(x), 2), np.float32)])
        write(x, OUT_SE / f"{name}.ogg")
        meta["se"][name] = {"src": f"audio/se/{name}.ogg", "vol": vol}
        print("se", name, flush=True)
    meta_p.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
