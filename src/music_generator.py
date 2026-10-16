import os
import math
import wave
import hashlib
import numpy as np


SR = 44100  # 44.1 kHz CD-kalitesi stereo ses


def _soft_clip(x: np.ndarray, drive: float = 1.35) -> np.ndarray:
    return np.tanh(x * drive) / math.tanh(drive)


def _synth_kick(duration: float = 0.24, f_start: float = 135.0, f_end: float = 42.0) -> np.ndarray:
    n = int(SR * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    freq = f_end + (f_start - f_end) * np.exp(-t * 28.0)
    phase = 2.0 * np.pi * np.cumsum(freq) / SR
    env = np.exp(-t * 11.5)
    click = np.exp(-t * 180.0) * 0.35
    return (np.sin(phase) * env + click).astype(np.float32)


def _synth_clap(duration: float = 0.16, rng: np.random.Generator = None) -> np.ndarray:
    if rng is None:
        rng = np.random.default_rng(42)
    n = int(SR * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    noise = rng.normal(0, 1, n)
    # Çoklu mikro tokat zarfı (909 tarzı moda house clap)
    env = (
        0.5 * np.exp(-np.maximum(0, t) * 95.0)
        + 0.5 * np.exp(-np.maximum(0, t - 0.011) * 95.0) * (t >= 0.011)
        + 0.8 * np.exp(-np.maximum(0, t - 0.023) * 26.0) * (t >= 0.023)
    )
    return (noise * env * 0.42).astype(np.float32)


def _synth_hihat(duration: float = 0.09, open_hat: bool = False, rng: np.random.Generator = None) -> np.ndarray:
    if rng is None:
        rng = np.random.default_rng(99)
    dur = 0.22 if open_hat else duration
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    # Yüksek frekanslı metalik doku
    noise = rng.normal(0, 1, n)
    metallic = (
        np.sin(2 * np.pi * 6350 * t)
        + np.sin(2 * np.pi * 8420 * t)
        + np.sin(2 * np.pi * 10850 * t)
    ) / 3.0
    sig = np.diff(noise, prepend=0) * 0.65 + metallic * 0.35
    decay = 11.0 if open_hat else 48.0
    env = np.exp(-t * decay)
    return (sig * env * (0.28 if open_hat else 0.16)).astype(np.float32)


def _synth_whoosh_pop(duration: float = 0.22, pitch_mult: float = 1.0, rng: np.random.Generator = None) -> np.ndarray:
    """Graph Motion kıyafet girişlerinde duyulan estetik 'whoosh + pop' ses efekti."""
    if rng is None:
        rng = np.random.default_rng(7)
    n = int(SR * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    # 1) Hava geçişi (Whoosh)
    whoosh_env = np.sin(np.pi * np.clip(t / 0.14, 0, 1)) ** 2
    whoosh = rng.normal(0, 1, n) * whoosh_env * 0.16
    # 2) Tatlı balon/kart oturma sesi (Pop)
    pop_t = np.maximum(0, t - 0.08)
    pop_active = (t >= 0.08).astype(np.float32)
    f_pop = (220.0 * pitch_mult) + (460.0 * pitch_mult) * (1.0 - np.exp(-pop_t * 45.0))
    pop_phase = 2.0 * np.pi * np.cumsum(f_pop) / SR
    pop_env = np.exp(-pop_t * 32.0) * pop_active
    pop = np.sin(pop_phase) * pop_env * 0.38
    return (whoosh + pop).astype(np.float32)


def _synth_shutter_riser(duration: float = 0.85, rng: np.random.Generator = None) -> np.ndarray:
    """Sahne geçişi öncesi (4.55s - 5.40s) yükselen gerilim (riser) ve deklanşör geçişi."""
    if rng is None:
        rng = np.random.default_rng(123)
    n = int(SR * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    prog = (t / duration) ** 2.2
    freq = 180.0 + 1450.0 * prog
    phase = 2.0 * np.pi * np.cumsum(freq) / SR
    shimmer = np.sin(phase) * prog * 0.24
    noise_sweep = rng.normal(0, 1, n) * (prog ** 1.6) * 0.22
    return (shimmer + noise_sweep).astype(np.float32)


def _mix_at(stereo: np.ndarray, mono_clip: np.ndarray, start_sec: float, pan: float = 0.0, gain: float = 1.0):
    """Mono ses klibini stereo tamponda (L/R panlamalı) belirtilen saniyeye yerleştirir."""
    start_idx = int(start_sec * SR)
    if start_idx >= stereo.shape[0] or start_idx < 0:
        return
    end_idx = min(stereo.shape[0], start_idx + len(mono_clip))
    seg = mono_clip[: end_idx - start_idx] * gain
    left_gain = math.cos((pan + 1.0) * math.pi / 4.0)
    right_gain = math.sin((pan + 1.0) * math.pi / 4.0)
    stereo[start_idx:end_idx, 0] += seg * left_gain
    stereo[start_idx:end_idx, 1] += seg * right_gain


# 5 Farklı Viral Moda / Kombin Reels Müzik Teması (Her paylaşımda farklı bir trend atmosferi)
FASHION_TRACK_PROFILES = [
    {
        "name": "Milan Runway Deep House (Viral OOTD Mix)",
        "bpm": 124,
        "root_hz": 55.0,  # A1 minor 9th luxury house
        "chord_ratios": [1.0, 1.1892, 1.4983, 1.7818, 2.2449],
        "bass_pattern": [0, 0, 12, 0, 3, 3, 7, 10],
        "pluck_notes": [12, 15, 19, 22, 19, 15, 14, 12],
    },
    {
        "name": "Parisian Street Style Chill-House",
        "bpm": 120,
        "root_hz": 65.41,  # C2 minor 9th aesthetic groove
        "chord_ratios": [1.0, 1.1892, 1.4983, 1.7818, 2.2449],
        "bass_pattern": [0, 0, 7, 12, 5, 5, 3, 7],
        "pluck_notes": [15, 14, 12, 19, 17, 15, 12, 10],
    },
    {
        "name": "Zara Haul Viral Speed-Garage Beat",
        "bpm": 128,
        "root_hz": 58.27,  # Bb1 minor club fashion
        "chord_ratios": [1.0, 1.1892, 1.4983, 1.7818, 2.2449],
        "bass_pattern": [0, 12, 0, 10, 3, 15, 5, 7],
        "pluck_notes": [12, 19, 17, 15, 12, 15, 17, 22],
    },
    {
        "name": "Soho Luxury Minimal Tech-Groove",
        "bpm": 126,
        "root_hz": 49.0,  # G1 minor deep runway
        "chord_ratios": [1.0, 1.1892, 1.4983, 1.7818, 2.2449],
        "bass_pattern": [0, 0, 0, 12, 3, 3, 5, 7],
        "pluck_notes": [19, 15, 12, 14, 15, 19, 22, 19],
    },
    {
        "name": "Golden Hour Afro-House Fashion Edit",
        "bpm": 122,
        "root_hz": 61.74,  # B1 minor warm sunset
        "chord_ratios": [1.0, 1.1892, 1.4983, 1.7818, 2.2449],
        "bass_pattern": [0, 7, 12, 0, 5, 10, 7, 3],
        "pluck_notes": [12, 14, 15, 19, 17, 15, 14, 12],
    },
]


def generate_viral_fashion_audio(
    output_wav: str,
    duration: float = 11.0,
    seed_key: str = "default",
    item_pop_times: list = None,
    transition_sec: float = 5.4,
) -> dict:
    """
    Kombin Reels videosu için:
    1) İlk bölümde (0.0s - 5.4s) yumuşak filtreli lüks moda akorları + her kıyafet ekrana uçtuğunda
       tam karesiyle senkronize 'Whoosh & Pop' hareket ses efektleri,
    2) Geçiş anında (5.4s) riser + Bass Drop patlaması,
    3) İkinci bölümde (5.4s - 11.0s) sokakta yürüyen modelin adımlarına uyumlu tam enerji
       Viral Runway Deep House / OOTD ritmi üretir.
    """
    h = int(hashlib.md5(seed_key.encode("utf-8")).hexdigest()[:8], 16)
    rng = np.random.default_rng(h)
    profile = FASHION_TRACK_PROFILES[h % len(FASHION_TRACK_PROFILES)]

    bpm = profile["bpm"]
    beat_dur = 60.0 / bpm
    step_dur = beat_dur / 2.0  # 8'lik nota adımı
    root_hz = profile["root_hz"]

    n_samples = int(SR * duration)
    t_full = np.linspace(0, duration, n_samples, endpoint=False)
    stereo = np.zeros((n_samples, 2), dtype=np.float32)

    # 1. Sıcak Stereo Rhodes / Deep House Pad Akorları (Sidechain pompalama efektli)
    pad_l = np.zeros(n_samples, dtype=np.float32)
    pad_r = np.zeros(n_samples, dtype=np.float32)
    for idx, ratio in enumerate(profile["chord_ratios"]):
        freq = root_hz * 4.0 * ratio
        detune = 1.0025 if idx % 2 == 0 else 0.9975
        pad_l += np.sin(2.0 * np.pi * freq * t_full + idx * 0.5) * 0.055
        pad_r += np.sin(2.0 * np.pi * (freq * detune) * t_full + idx * 0.9) * 0.055

    # Sidechain envelope (her vuruşta nefes alan moda house etkisi)
    beat_phase = (t_full % beat_dur) / beat_dur
    sidechain = 0.25 + 0.75 * (1.0 - np.exp(-beat_phase * 5.5))
    # 2. sahnede (model yürüyüşünde) pad parlaklığı artar
    scene_boost = np.where(t_full >= transition_sec, 1.35, 0.85).astype(np.float32)
    stereo[:, 0] += pad_l * sidechain * scene_boost
    stereo[:, 1] += pad_r * sidechain * scene_boost

    # 2. Ritmik Davul, Sub-Bass ve Pluck Melodi Döngüsü
    kick = _synth_kick(0.24)
    kick_punch = _synth_kick(0.26, f_start=155.0, f_end=38.0) * 1.25
    clap = _synth_clap(0.16, rng)
    closed_hat = _synth_hihat(0.08, open_hat=False, rng=rng)
    open_hat = _synth_hihat(0.20, open_hat=True, rng=rng)

    total_beats = int(duration / beat_dur) + 1
    for b in range(total_beats):
        bt = b * beat_dur
        if bt >= duration:
            break

        in_walk_scene = bt >= (transition_sec - 0.08)

        # Kick: 1. sahnede yumuşak kalp atışı, 2. sahnede (model yürürken) tam güç 4x4 club kick
        if in_walk_scene:
            _mix_at(stereo, kick_punch, bt, pan=0.0, gain=0.95)
            # Off-beat açık hi-hat (Runway temposu)
            _mix_at(stereo, open_hat, bt + beat_dur * 0.5, pan=0.22, gain=0.85)
            # 16'lık kapalı hi-hat
            _mix_at(stereo, closed_hat, bt + beat_dur * 0.25, pan=-0.25, gain=0.6)
            _mix_at(stereo, closed_hat, bt + beat_dur * 0.75, pan=0.18, gain=0.65)
            # 2. ve 4. vuruşlarda Clap
            if b % 2 == 1:
                _mix_at(stereo, clap, bt, pan=-0.08, gain=0.90)
        else:
            # 1. sahnede (kolaj dizilirken) zarif filtreli groove
            if abs(bt - transition_sec) > 0.55:
                _mix_at(stereo, kick, bt, pan=0.0, gain=0.52)
                _mix_at(stereo, closed_hat, bt + beat_dur * 0.5, pan=0.15, gain=0.55)
                if b % 2 == 1:
                    _mix_at(stereo, clap, bt, pan=-0.1, gain=0.45)

    # 3. Deep House Sub-Bass & Estetik Pluck Melodisi (8'lik adımlarla)
    total_steps = int(duration / step_dur) + 1
    bass_pat = profile["bass_pattern"]
    pluck_pat = profile["pluck_notes"]

    for s in range(total_steps):
        st = s * step_dur
        if st >= duration:
            break
        in_walk = st >= (transition_sec - 0.05)

        # Sub-bass notası
        semitone = bass_pat[s % len(bass_pat)]
        f_bass = root_hz * (2.0 ** (semitone / 12.0))
        b_len = int(SR * step_dur * 0.88)
        tb = np.linspace(0, step_dur * 0.88, b_len, endpoint=False)
        b_env = np.exp(-tb * 7.5) * (1.0 - np.exp(-tb * 120.0))
        # FM harmonikli tok house bası
        mod = np.sin(2.0 * np.pi * f_bass * 2.0 * tb) * np.exp(-tb * 18.0) * (1.6 if in_walk else 0.7)
        bass_wave = np.sin(2.0 * np.pi * f_bass * tb + mod) * b_env
        _mix_at(stereo, bass_wave.astype(np.float32), st, pan=0.0, gain=0.42 if in_walk else 0.22)

        # Melodik Pluck (Marimba/Synth Pluck - Moda Reels imzası)
        p_semi = pluck_pat[s % len(pluck_pat)]
        f_pluck = root_hz * 4.0 * (2.0 ** (p_semi / 12.0))
        p_len = int(SR * step_dur * 0.65)
        tp = np.linspace(0, step_dur * 0.65, p_len, endpoint=False)
        p_env = np.exp(-tp * 16.0)
        pluck_wave = (np.sin(2.0 * np.pi * f_pluck * tp) + 0.35 * np.sin(2.0 * np.pi * f_pluck * 2.0 * tp)) * p_env
        pan_pos = 0.32 * math.sin(s * 0.9)
        _mix_at(stereo, pluck_wave.astype(np.float32), st, pan=pan_pos, gain=0.18 if in_walk else 0.11)

    # 4. Kıyafetlerin Ekrana Uçuş Anlarıyla Senkronize 'Whoosh + Pop' Efektleri
    if item_pop_times:
        for idx, pt in enumerate(item_pop_times):
            sfx = _synth_whoosh_pop(0.24, pitch_mult=0.92 + idx * 0.07, rng=rng)
            pan = -0.35 if idx % 2 == 0 else 0.35
            _mix_at(stereo, sfx, max(0.0, pt + 0.18), pan=pan, gain=0.85)

    # 5. Sahne Geçişi Riser (4.55s -> 5.40s) ve Bass Drop (5.40s)
    riser_dur = 0.85
    if transition_sec > riser_dur:
        riser = _synth_shutter_riser(riser_dur, rng=rng)
        _mix_at(stereo, riser, transition_sec - riser_dur, pan=0.0, gain=0.95)
    # Geçiş darbesi (Impact Sub Drop)
    drop_impact = _synth_kick(0.45, f_start=180.0, f_end=34.0)
    _mix_at(stereo, drop_impact, transition_sec, pan=0.0, gain=1.15)

    # 6. Yumuşak Giriş / Çıkış (Fade-in & Fade-out) ve Mastering Limiter
    fade_in = np.clip(t_full / 0.18, 0.0, 1.0)
    fade_out = np.clip((duration - t_full) / 0.85, 0.0, 1.0)
    master_env = (fade_in * fade_out)[:, None]
    stereo = _soft_clip(stereo * master_env, drive=1.45)

    peak = np.max(np.abs(stereo))
    if peak > 0:
        stereo = stereo / peak * 0.92

    os.makedirs(os.path.dirname(output_wav) or ".", exist_ok=True)
    pcm16 = (stereo * 32767.0).astype(np.int16)
    with wave.open(output_wav, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm16.tobytes())

    print(f"[Viral Müzik Motoru] '{profile['name']}' ({bpm} BPM) üretildi -> {output_wav}")
    return profile
