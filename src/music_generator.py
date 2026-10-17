import os
import json
import math
import wave
import asyncio
import hashlib
import numpy as np
import librosa
import soundfile as sf
from scipy.signal import butter, sosfilt
from scipy.ndimage import gaussian_filter1d

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False


SR = 44100  # 44.1 kHz CD-kalitesi stereo ses
MUSIC_LIB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "music_library")
HISTORY_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "last_used_music_profiles.json")


def _soft_clip(x: np.ndarray, drive: float = 1.28) -> np.ndarray:
    return np.tanh(x * drive) / math.tanh(drive)


def _apply_vocal_presence_eq(mono_voice: np.ndarray) -> np.ndarray:
    """
    Açık kaynaklı nöral TTS (edge-tts) sesini stüdyo podcast / Reels içerik üreticisi
    mikrofonu kalitesine taşır:
    - 85 Hz altı uğultuyu temizler (High-pass)
    - 2.8 kHz - 5.5 kHz arası konuşma netliğini (presence) parlatır
    """
    if len(mono_voice) < 256:
        return mono_voice
    try:
        sos_hp = butter(2, 85.0 / (SR / 2.0), btype="highpass", output="sos")
        clean = sosfilt(sos_hp, mono_voice).astype(np.float32)
        sos_pres = butter(2, [2400.0 / (SR / 2.0), 5800.0 / (SR / 2.0)], btype="bandpass", output="sos")
        presence = sosfilt(sos_pres, clean).astype(np.float32)
        out = clean + presence * 0.38
        peak = np.max(np.abs(out))
        if peak > 1e-4:
            out = out / peak * 0.92
        return out.astype(np.float32)
    except Exception:
        return mono_voice


def _karplus_strong_pluck(freq: float, duration: float = 0.28, rng: np.random.Generator = None) -> np.ndarray:
    """
    Fiziksel modelleme (Karplus-Strong algoritması) ile gerçek akustik gitar/arp teli tınısı
    ve hafif hava geçişi (whoosh) üretir. Kıyafet kartları ekrana uçarken çalar.
    """
    if rng is None:
        rng = np.random.default_rng(7)
    n = int(SR * duration)
    delay_len = max(8, int(SR / max(80.0, freq)))
    buf = rng.uniform(-1.0, 1.0, delay_len).astype(np.float32)
    # Tel yumuşatma
    buf = np.convolve(buf, [0.25, 0.5, 0.25], mode="same").astype(np.float32)
    out = np.zeros(n, dtype=np.float32)
    idx = 0
    for i in range(n):
        out[i] = buf[idx]
        nxt = (idx + 1) % delay_len
        buf[idx] = 0.992 * 0.5 * (buf[idx] + buf[nxt])
        idx = nxt

    t = np.linspace(0, duration, n, endpoint=False)
    whoosh_env = np.sin(np.pi * np.clip(t / 0.12, 0, 1)) ** 2
    whoosh = rng.normal(0, 1, n).astype(np.float32) * whoosh_env * 0.08
    env = np.exp(-t * 9.5).astype(np.float32)
    return (out * env * 0.34 + whoosh).astype(np.float32)


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


def _load_stereo_segment(filepath: str, start_sec: float, duration_sec: float) -> np.ndarray:
    """
    Gerçek stüdyo enstrüman kaydından (MP3/OGG/WAV) belirtilen saniye aralığını
    44.1 kHz stereo float32 matris olarak yükler.
    """
    target_len = int(SR * duration_sec)
    if not os.path.exists(filepath):
        try:
            base_key = os.path.splitext(os.path.basename(filepath))[0]
            filepath = librosa.ex(base_key)
        except Exception:
            return np.zeros((target_len, 2), dtype=np.float32)

    try:
        y, _ = librosa.load(filepath, sr=SR, mono=False, offset=start_sec, duration=duration_sec + 0.5)
        if y.ndim == 1:
            stereo = np.column_stack([y, y]).astype(np.float32)
        else:
            stereo = np.column_stack([y[0], y[1 if y.shape[0] > 1 else 0]]).astype(np.float32)

        if stereo.shape[0] < target_len:
            repeats = int(math.ceil(target_len / max(1, stereo.shape[0])))
            stereo = np.tile(stereo, (repeats, 1))
        stereo = stereo[:target_len]
        peak = np.max(np.abs(stereo))
        if peak > 1e-4:
            stereo = stereo / peak
        return stereo.astype(np.float32)
    except Exception as e:
        print(f"[Enstrüman Kaydı Yükleme Uyarısı] {filepath}: {e}")
        return np.zeros((target_len, 2), dtype=np.float32)


async def _synthesize_tts_clip_async(text: str, voice: str, rate: str, pitch: str, out_mp3: str):
    comm = edge_tts.Communicate(text=text, voice=voice, rate=rate)
    await comm.save(out_mp3)


def _generate_spoken_clip(
    text: str,
    voice: str = "tr-TR-EmelNeural",
    rate: str = "+4%",
    pitch: str = "+0Hz",
    cache_tag: str = "clip",
) -> np.ndarray:
    """
    edge-tts kullanarak %100 doğal Türkçe nöral konuşma üretir.
    Robotik/metalik ses bozulmasına (phase vocoder artifact) yol açan time_stretch KESİNLİKLE uygulanmaz;
    doğal konuşma hızı ve temiz stüdyo EQ kullanılır.
    """
    if not HAS_EDGE_TTS or not text.strip():
        return np.zeros(0, dtype=np.float32)

    os.makedirs("output/_tts_cache", exist_ok=True)
    h_key = hashlib.md5(f"v2|{text}|{voice}|{rate}".encode("utf-8")).hexdigest()[:12]
    mp3_path = os.path.join("output/_tts_cache", f"tts_{cache_tag}_{h_key}.mp3")

    try:
        if not os.path.exists(mp3_path) or os.path.getsize(mp3_path) < 500:
            try:
                asyncio.run(_synthesize_tts_clip_async(text, voice, rate, pitch, mp3_path))
            except Exception:
                asyncio.run(_synthesize_tts_clip_async(text, "tr-TR-EmelNeural", "+4%", "+0Hz", mp3_path))
        y, _ = librosa.load(mp3_path, sr=SR, mono=True)
        y_trim, _ = librosa.effects.trim(y, top_db=30)
        if len(y_trim) < 100:
            return np.zeros(0, dtype=np.float32)

        return _apply_vocal_presence_eq(y_trim.astype(np.float32))
    except Exception as e:
        print(f"[Doğal Konuşma TTS Uyarısı] ({voice}): {e}")
        return np.zeros(0, dtype=np.float32)


# 10 Farklı Gerçek Çoklu-Enstrüman Stüdyo Kaydı + Sadece Giriş Hook & Kapanış CTA ("Detaylar guzelai.com'da")
# (Ürünler tek tek okunmaz, ses tüm videoya yayılmaz; ortadaki ~6.5 saniye boyunca saf enstrüman müziği akar)
MULTI_INSTRUMENT_PROFILES = [
    {
        "id": "veor_uranis_da_da_da_2026",
        "name": "Veor Uranis – Da Da Da Dadada (Viral Reels Hit)",
        "instruments_desc": "Veor Uranis 'Da Da Da Dadada' Orijinal Viral Reels & TikTok Parçası (44.1 kHz Stereo Master)",
        "bpm": 124,
        "intro_track": "veor_uranis_da_da_da.wav",
        "intro_offset": 19.2,
        "walk_track": "veor_uranis_da_da_da.wav",
        "walk_offset": 24.4,
        "continuous_track": True,
        "horn_accent": False,
        "pluck_scale_hz": [293.66, 349.23, 440.0, 523.25, 587.33, 659.25],
        "voice_hook": ("tr-TR-EmelNeural", "+4%", "+0Hz"),
        "intro_hook_text": "Sokağa çıkarken herkesin dönüp baktığı o kusursuz sonbahar kombinim!",
        "outro_cta_text": "Detaylar güzelai nokta com'da.",
    },
    {
        "id": "milan_sax_bossa_guitar_inner_voice",
        "name": "Milano Saksafon, Akustik Gitar & Bossa-Lounge",
        "instruments_desc": "Tenor Saksafon + Akustik Klasik Gitar + Kontrbas + Latin Perküsyon & Canlı Trompet",
        "bpm": 122,
        "intro_track": "bossa_antigua.mp3",
        "intro_offset": 14.0,
        "walk_track": "bossa_antigua.mp3",
        "walk_offset": 56.5,
        "horn_accent": True,
        "pluck_scale_hz": [293.66, 349.23, 440.0, 523.25, 587.33, 659.25],
        "voice_hook": ("tr-TR-EmelNeural", "+4%", "+0Hz"),
        "intro_hook_text": "İç sesim bir dakika bile susmadığı için gün boyu böyleyim!",
        "outro_cta_text": "Detaylar güzelai nokta com'da.",
    },
    {
        "id": "old_money_violin_orchestra_pov",
        "name": "Senfonik Keman Orkestrası & Akustik Piyano (Brahms POV Remix)",
        "instruments_desc": "Senfonik Keman & Yaylı Orkestrası + Akustik Kuyruklu Piyano + Modern Runway Beat",
        "bpm": 126,
        "intro_track": "pistachio.ogg",
        "intro_offset": 4.0,
        "walk_track": "brahms.ogg",
        "walk_offset": 0.4,
        "horn_accent": False,
        "pluck_scale_hz": [277.18, 329.63, 369.99, 440.0, 554.37, 659.25],
        "voice_hook": ("tr-TR-EmelNeural", "+4%", "+0Hz"),
        "intro_hook_text": "Kafamın içinde kırk tilki dönerken dışarıya verdiğim sakinlik!",
        "outro_cta_text": "Detaylar güzelai nokta com'da.",
    },
    {
        "id": "nisantasi_funk_slapbass_brass_pov",
        "name": "Nişantaşı Funk Slap-Bass, Elektro Gitar & Bakır Nefesliler",
        "instruments_desc": "Funk Slap Bas + Ritim Elektro Gitar + Trompet/Saksafon Grubu + Canlı Stüdyo Davul",
        "bpm": 124,
        "intro_track": "vibeace.ogg",
        "intro_offset": 5.5,
        "walk_track": "funkorama.mp3",
        "walk_offset": 19.0,
        "horn_accent": True,
        "pluck_scale_hz": [261.63, 311.13, 392.00, 466.16, 523.25, 622.25],
        "voice_hook": ("tr-TR-EmelNeural", "+4%", "+0Hz"),
        "intro_hook_text": "Modum sıfırken bile kombinim on üzerinden on olmak zorunda!",
        "outro_cta_text": "Detaylar güzelai nokta com'da.",
    },
    {
        "id": "paris_cafe_accordion_strings_pov",
        "name": "Paris Cafe Akordeon, Akustik Yaylılar & Caz Gitar",
        "instruments_desc": "Fransız Akordeon + Pizzicato Yaylılar + Akustik Gitar + Cafe Lounge Ritmi",
        "bpm": 120,
        "intro_track": "sweetwaltz.ogg",
        "intro_offset": 1.5,
        "walk_track": "sweetwaltz.ogg",
        "walk_offset": 18.0,
        "horn_accent": False,
        "pluck_scale_hz": [293.66, 369.99, 440.0, 493.88, 587.33, 739.99],
        "voice_hook": ("tr-TR-EmelNeural", "+4%", "+0Hz"),
        "intro_hook_text": "Kimseyle konuşmak istemeyip yine de ortamdaki en şık kişi olma çabam!",
        "outro_cta_text": "Detaylar güzelai nokta com'da.",
    },
    {
        "id": "soho_lounge_sax_rhodes_pov",
        "name": "Soho Lounge Saksafon, Rhodes Elektrik Piyano & Caz Kontrbas",
        "instruments_desc": "Sıcak Lounge Saksafon + Fender Rhodes Piyano + Akustik Kontrbas + Fırça Davul",
        "bpm": 118,
        "intro_track": "lobby_time.mp3",
        "intro_offset": 8.0,
        "walk_track": "lobby_time.mp3",
        "walk_offset": 42.0,
        "horn_accent": True,
        "pluck_scale_hz": [246.94, 293.66, 369.99, 440.0, 493.88, 587.33],
        "voice_hook": ("tr-TR-EmelNeural", "+4%", "+0Hz"),
        "intro_hook_text": "Beş dakikada hazırlanıp çıkacağım dedikten yarım saat sonra ben!",
        "outro_cta_text": "Detaylar güzelai nokta com'da.",
    },
    {
        "id": "jazz_trumpet_grand_piano_pov",
        "name": "Caz Trompet, Akustik Kuyruklu Piyano & Swing Groove",
        "instruments_desc": "Sürdinli Caz Trompet + Akustik Kuyruklu Piyano + Yürüyen Kontrbas + Swing Ritmi",
        "bpm": 122,
        "intro_track": "jazz_brunch.mp3",
        "intro_offset": 12.0,
        "walk_track": "jazz_brunch.mp3",
        "walk_offset": 64.0,
        "horn_accent": True,
        "pluck_scale_hz": [261.63, 329.63, 392.0, 493.88, 523.25, 659.25],
        "voice_hook": ("tr-TR-EmelNeural", "+4%", "+0Hz"),
        "intro_hook_text": "İç sesimle tartışırken bir anda sokakta podyum yürüyüşüne geçtim!",
        "outro_cta_text": "Detaylar güzelai nokta com'da.",
    },
    {
        "id": "autumn_acoustic_guitar_groove_pov",
        "name": "Sonbahar Akustik Gitar, Sıcak Bas & Organik Stüdyo Davul",
        "instruments_desc": "Çelik Telli Akustik Gitar + Sıcak Bas Gitar + Canlı Akustik Davul & Hammond Org",
        "bpm": 120,
        "intro_track": "fishin.ogg",
        "intro_offset": 6.0,
        "walk_track": "fishin.ogg",
        "walk_offset": 28.0,
        "horn_accent": False,
        "pluck_scale_hz": [293.66, 369.99, 440.0, 587.33, 659.25, 739.99],
        "voice_hook": ("tr-TR-EmelNeural", "+4%", "+0Hz"),
        "intro_hook_text": "Giyecek hiçbir şeyim yok krizinden beş dakika sonra sokağa çıkarken ben!",
        "outro_cta_text": "Detaylar güzelai nokta com'da.",
    },
    {
        "id": "quiet_luxury_vibraphone_bass_pov",
        "name": "Quiet Luxury Vibrafon, Akustik Kontrbas & Minimal Caz Piyano",
        "instruments_desc": "Caz Vibrafon + Akustik Kontrbas + Kuyruklu Piyano + Yumuşak Lounge Perküsyon",
        "bpm": 118,
        "intro_track": "cool_vibes.mp3",
        "intro_offset": 15.0,
        "walk_track": "cool_vibes.mp3",
        "walk_offset": 52.0,
        "horn_accent": False,
        "pluck_scale_hz": [261.63, 311.13, 392.0, 466.16, 587.33, 698.46],
        "voice_hook": ("tr-TR-EmelNeural", "+4%", "+0Hz"),
        "intro_hook_text": "Dışarıdan sakin görünüyorum ama iç sesim bir dakika bile susmuyor!",
        "outro_cta_text": "Detaylar güzelai nokta com'da.",
    },
    {
        "id": "october_celesta_strings_beat_pov",
        "name": "Ekim & Cadılar Bayramı Çelesta, Pizzicato Yaylılar & Breakbeat",
        "instruments_desc": "Çelesta + Pizzicato Yaylı Orkestrası + Tahta Nefesliler + Canlı Breakbeat Drum & Bass",
        "bpm": 128,
        "intro_track": "nutcracker.ogg",
        "intro_offset": 8.0,
        "walk_track": "choice.ogg",
        "walk_offset": 2.0,
        "horn_accent": True,
        "pluck_scale_hz": [311.13, 369.99, 466.16, 554.37, 622.25, 739.99],
        "voice_hook": ("tr-TR-EmelNeural", "+4%", "+0Hz"),
        "intro_hook_text": "Plan iptal olunca üzülmeyip yine de kombinimi sergilemeye çıktım!",
        "outro_cta_text": "Detaylar güzelai nokta com'da.",
    },
    {
        "id": "sunset_electric_guitar_chillwave_pov",
        "name": "Sunset Elektro Gitar, Chill-Wave & Organik Groove",
        "instruments_desc": "Atmosferik Elektro Gitar + Chill-Wave Analog Pad + Sıcak Bas + Organik Ritim",
        "bpm": 120,
        "intro_track": "chill_wave.mp3",
        "intro_offset": 22.0,
        "walk_track": "chill_wave.mp3",
        "walk_offset": 68.0,
        "horn_accent": False,
        "pluck_scale_hz": [293.66, 349.23, 440.0, 523.25, 659.25, 783.99],
        "voice_hook": ("tr-TR-EmelNeural", "+4%", "+0Hz"),
        "intro_hook_text": "İç sesim bir dakika bile susmadığı için gün boyu böyleyim!",
        "outro_cta_text": "Detaylar güzelai nokta com'da.",
    },
]


def _select_non_repeating_profile(seed_key: str) -> dict:
    """
    Son kullanılan müzik ve seslendirme profillerini takip ederek her videoda
    farklı bir enstrüman grubu ve farklı bir doğal konuşma hook'u seçer.
    """
    recent_ids = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                recent_ids = json.load(f).get("recent_ids", [])
        except Exception:
            recent_ids = []

    available = [p for p in MULTI_INSTRUMENT_PROFILES if p["id"] not in recent_ids[-6:]]
    if not available:
        available = MULTI_INSTRUMENT_PROFILES

    h = int(hashlib.md5(str(seed_key).encode("utf-8")).hexdigest()[:8], 16)
    chosen = available[h % len(available)]

    try:
        os.makedirs(os.path.dirname(HISTORY_FILE) or ".", exist_ok=True)
        recent_ids.append(chosen["id"])
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump({"recent_ids": recent_ids[-12:]}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return chosen


def generate_viral_fashion_audio(
    output_wav: str,
    duration: float = 11.0,
    seed_key: str = "default",
    item_pop_times: list = None,
    transition_sec: float = 5.4,
    outfit: dict = None,
) -> dict:
    """
    Açık kaynaklı çoklu-enstrüman stüdyo kayıtları + SADECE girişte kısa doğal Türkçe Hook cümlesi
    (0.12s - ~2.2s) ve kapanışta 'Detaylar güzelai.com'da' çağrısı (~8.8s - ~10.3s) üretir.
    Ortadaki ~6.5 saniye boyunca seslendirme yapılmaz; ürünler tek tek okunmaz; enstrüman müziği
    tam stüdyo kalitesinde nefes alır.
    """
    pref_id = (outfit or {}).get("preferred_music_id")
    if pref_id:
        matched = [p for p in MULTI_INSTRUMENT_PROFILES if p["id"] == pref_id]
        profile = dict(matched[0]) if matched else dict(_select_non_repeating_profile(seed_key))
    else:
        profile = dict(_select_non_repeating_profile(seed_key))
    h = int(hashlib.md5(f"{seed_key}_{profile['id']}".encode("utf-8")).hexdigest()[:8], 16)
    rng = np.random.default_rng(h)

    n_samples = int(SR * duration)
    trans_idx = int(SR * transition_sec)

    # 1. SAHNE 1 (0.0s -> 5.4s) & SAHNE 2 (5.4s -> 11.0s) GERÇEK ENSTRÜMAN STÜDYO KAYITLARINI YÜKLE
    intro_path = os.path.join(MUSIC_LIB_DIR, profile["intro_track"])
    walk_path = os.path.join(MUSIC_LIB_DIR, profile["walk_track"])

    music_stereo = np.zeros((n_samples, 2), dtype=np.float32)
    if profile.get("continuous_track"):
        full_stereo = _load_stereo_segment(intro_path, profile["intro_offset"], duration + 0.6)
        music_stereo[:trans_idx] = full_stereo[:trans_idx] * 0.86
        music_stereo[trans_idx:] = full_stereo[trans_idx:n_samples] * 0.98
    else:
        intro_stereo = _load_stereo_segment(intro_path, profile["intro_offset"], transition_sec + 0.5)
        walk_stereo = _load_stereo_segment(walk_path, profile["walk_offset"], (duration - transition_sec) + 0.6)
        music_stereo[:trans_idx] = intro_stereo[:trans_idx] * 0.82

        # Sahne geçişinde (5.15s - 5.65s) pürüzsüz crossfade + 2. sahnede tam stüdyo enerjisi
        cf_samples = int(0.35 * SR)
        walk_len = n_samples - trans_idx
        music_stereo[trans_idx:] = walk_stereo[:walk_len] * 0.96

        if trans_idx > cf_samples and walk_len > cf_samples:
            fade_out_curve = np.linspace(1.0, 0.0, cf_samples, dtype=np.float32)[:, None]
            fade_in_curve = np.linspace(0.0, 1.0, cf_samples, dtype=np.float32)[:, None]
            music_stereo[trans_idx - cf_samples : trans_idx] = (
                intro_stereo[trans_idx - cf_samples : trans_idx] * 0.82 * fade_out_curve
                + walk_stereo[:cf_samples] * 0.96 * fade_in_curve
            )

    # Sahne geçişinde gerçek caz trompet/nefesli vurgusu (Horn Drop Accent)
    if profile.get("horn_accent"):
        trumpet_path = os.path.join(MUSIC_LIB_DIR, "trumpet.ogg")
        horn_seg = _load_stereo_segment(trumpet_path, 0.0, 1.45)
        h_len = len(horn_seg)
        if trans_idx + h_len < n_samples:
            h_env = np.sin(np.pi * np.linspace(0, 1, h_len, dtype=np.float32))[:, None]
            music_stereo[trans_idx : trans_idx + h_len] += horn_seg * h_env * 0.32

    # 2. KIYAFET PARÇALARI UÇARKEN AKUSTİK TEL (KARPLUS-STRONG) & HAVA EFEKTİ
    sfx_stereo = np.zeros((n_samples, 2), dtype=np.float32)
    if item_pop_times:
        scale_hz = profile["pluck_scale_hz"]
        for idx, pt in enumerate(item_pop_times):
            note_hz = scale_hz[idx % len(scale_hz)]
            pluck_sfx = _karplus_strong_pluck(note_hz, duration=0.26, rng=rng)
            pan = -0.32 if idx % 2 == 0 else 0.32
            _mix_at(sfx_stereo, pluck_sfx, max(0.0, pt + 0.16), pan=pan, gain=0.58)

    # 3. SADECE GİRİŞ HOOK CÜMLESİ (0.12s - ~2.2s) VE KAPANIŞ "Detaylar guzelai.com'da" (~8.8s - ~10.3s)
    vocal_track = np.zeros((n_samples, 2), dtype=np.float32)
    vocal_envelope = np.zeros(n_samples, dtype=np.float32)

    v_name, v_rate, v_pitch = profile.get("voice_hook", ("tr-TR-EmelNeural", "+4%", "+0Hz"))
    custom_hook_voice = (outfit or {}).get("spoken_hook_text") or profile["intro_hook_text"]
    outro_cta_text = profile.get("outro_cta_text", "Detaylar güzelai nokta com'da.")

    clip_intro = _generate_spoken_clip(custom_hook_voice, voice=v_name, rate=v_rate, pitch=v_pitch, cache_tag="intro_hook")
    clip_outro = _generate_spoken_clip(outro_cta_text, voice=v_name, rate=v_rate, pitch=v_pitch, cache_tag="outro_cta")

    # Giriş Hook (0.14s -> maksimum 2.55s)
    t_intro_start = 0.14
    intro_dur_sec = 0.0
    if len(clip_intro) > 0:
        max_intro_samples = int(2.45 * SR)
        clip_intro = clip_intro[:max_intro_samples]
        _mix_at(vocal_track, clip_intro, t_intro_start, pan=0.0, gain=1.06)
        i_s = int(t_intro_start * SR)
        i_e = min(n_samples, i_s + len(clip_intro))
        vocal_envelope[i_s:i_e] = 1.0
        intro_dur_sec = (i_e - i_s) / SR

    # Kapanış CTA ("Detaylar güzelai.com'da", videonun son ~2.1 saniyesinde: ~8.85s -> ~10.35s)
    outro_dur_sec = len(clip_outro) / SR if len(clip_outro) > 0 else 0.0
    t_outro_start = max(transition_sec + 3.1, duration - outro_dur_sec - 0.65)
    if len(clip_outro) > 0:
        _mix_at(vocal_track, clip_outro, t_outro_start, pan=0.0, gain=1.06)
        o_s = int(t_outro_start * SR)
        o_e = min(n_samples, o_s + len(clip_outro))
        vocal_envelope[o_s:o_e] = 1.0

    # 4. AKILLI SIDECHAIN SES DUCKING:
    # Sadece girişteki ~2sn hook ve sondaki ~1.4sn kapanış sırasında müzik hafifçe %42'ye çekilir;
    # 2.3sn ile 8.8sn arasındaki 6.5 saniye boyunca enstrüman müziği %100 saf ve kesintisiz çalar!
    smooth_vox_mask = gaussian_filter1d(vocal_envelope, sigma=int(0.09 * SR))
    smooth_vox_mask = np.clip(smooth_vox_mask, 0.0, 1.0)
    ducking_gain = (1.0 - 0.58 * smooth_vox_mask)[:, None]

    stereo = music_stereo * ducking_gain + sfx_stereo + vocal_track

    # 5. Yumuşak Giriş / Çıkış (Fade-in & Fade-out) ve Stüdyo Mastering Limiter
    t_full = np.linspace(0, duration, n_samples, endpoint=False)
    fade_in = np.clip(t_full / 0.12, 0.0, 1.0)
    fade_out = np.clip((duration - t_full) / 0.55, 0.0, 1.0)
    master_env = (fade_in * fade_out)[:, None]
    stereo = _soft_clip(stereo * master_env, drive=1.22)

    peak = np.max(np.abs(stereo))
    if peak > 0:
        stereo = stereo / peak * 0.95

    os.makedirs(os.path.dirname(output_wav) or ".", exist_ok=True)
    pcm16 = (stereo * 32767.0).astype(np.int16)
    with wave.open(output_wav, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm16.tobytes())

    voice_ratio = float(np.mean(vocal_envelope > 0.1))
    middle_voice_ratio = float(np.mean(vocal_envelope[int(2.7 * SR) : int(8.5 * SR)] > 0.1))
    profile["dialogue_q"] = custom_hook_voice
    profile["dialogue_a"] = ""
    profile["dialogue_walk"] = "Detaylar guzelai.com'da!"
    profile["audio_quality_metrics"] = {
        "intro_hook_duration_sec": round(intro_dur_sec, 2),
        "outro_cta_start_sec": round(t_outro_start, 2),
        "outro_cta_duration_sec": round(outro_dur_sec, 2),
        "total_voice_ratio": round(voice_ratio, 3),
        "middle_music_only_voice_ratio": round(middle_voice_ratio, 4),
    }

    print(
        f"[Çoklu-Enstrüman & Doğal Hook Motoru] '{profile['name']}' "
        f"| Giriş Hook ({intro_dur_sec:.1f}sn) + 6.5sn Saf Enstrüman + Kapanış CTA ({outro_dur_sec:.1f}sn) -> {output_wav}"
    )
    return profile
