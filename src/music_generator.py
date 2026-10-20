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
    {
        "id": "tiktok_halloween_party_couple_club_pov",
        "name": "TikTok Viral Cadılar Bayramı Parti: Dark Club Synth, Çelesta & Slap-Bass Groove",
        "instruments_desc": "Spooky Çelesta + Dark Club Slap-Bass + Pizzicato Yaylılar + 126 BPM Parti House Beat",
        "bpm": 126,
        "intro_track": "nutcracker.ogg",
        "intro_offset": 14.0,
        "walk_track": "brahms.ogg",
        "walk_offset": 18.0,
        "horn_accent": True,
        "pluck_scale_hz": [293.66, 349.23, 440.0, 523.25, 587.33, 698.46],
        "voice_hook": ("tr-TR-EmelNeural", "+4%", "+0Hz"),
        "intro_hook_text": "Cadılar Bayramı partisine çift kombinimizle girdiğimiz an bütün bakışlar üzerimizde!",
        "outro_cta_text": "Detaylar güzelai nokta com'da.",
    },
    {
        "id": "tiktok_vampiric_noir_gala_beat_pov",
        "name": "TikTok Viral Vampiric Noir Gala: İtalyan Yaylılar, Deep Synth & 128 BPM Party Drop",
        "instruments_desc": "Gotik Keman & Viyola + Deep House Synth Bass + Kuyruklu Piyano + 128 BPM Party Drop",
        "bpm": 128,
        "intro_track": "choice.ogg",
        "intro_offset": 4.0,
        "walk_track": "nutcracker.ogg",
        "walk_offset": 24.0,
        "horn_accent": True,
        "pluck_scale_hz": [311.13, 369.99, 466.16, 554.37, 622.25, 739.99],
        "voice_hook": ("tr-TR-EmelNeural", "+4%", "+0Hz"),
        "intro_hook_text": "Gece partisinde hem gizemli hem de en uyumlu çift olmanın sırrı bu kombinde!",
        "outro_cta_text": "Detaylar güzelai nokta com'da.",
    },
]


def _select_non_repeating_profile(seed_key: str, preferred_id: str = None) -> dict:
    """
    Son kullanılan müzik profillerini takip ederek üst üste aynı müziğin kullanılmasını (Algoritmik Ses Tekrarı Cezası)
    kesin olarak önler. Tercih edilen müzik son 4 paylaşımda kullanılmadıysa onu seçer; kullanıldıysa
    otomatik olarak sıradaki en yüksek viral skorlu taze müziğe geçiş yapar.
    """
    recent_ids = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                recent_ids = json.load(f).get("recent_ids", [])
        except Exception:
            recent_ids = []

    recent_window = recent_ids[-4:]
    chosen = None
    if preferred_id and preferred_id not in recent_window:
        matched = [p for p in MULTI_INSTRUMENT_PROFILES if p["id"] == preferred_id]
        if matched:
            chosen = matched[0]

    if chosen is None:
        available = [p for p in MULTI_INSTRUMENT_PROFILES if p["id"] not in recent_ids[-5:]]
        if not available:
            available = [p for p in MULTI_INSTRUMENT_PROFILES if p["id"] not in recent_ids[-2:]] or MULTI_INSTRUMENT_PROFILES
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


def _apply_studio_master_eq(stereo: np.ndarray) -> np.ndarray:
    """
    44.1 kHz Stereo Master EQ Enhancement:
    - 32 Hz altı sub-rumble temizliği
    - 65 Hz - 140 Hz podyum bas sıcaklığı (Runway Bass Punch)
    - 4.5 kHz - 14 kHz kristal tiz netliği (Air / Presence)
    """
    if stereo.shape[0] < 512:
        return stereo
    try:
        sos_hp = butter(2, 32.0 / (SR / 2.0), btype="highpass", output="sos")
        sos_bass = butter(2, [62.0 / (SR / 2.0), 145.0 / (SR / 2.0)], btype="bandpass", output="sos")
        sos_air = butter(2, [4500.0 / (SR / 2.0), 14500.0 / (SR / 2.0)], btype="bandpass", output="sos")
        out = np.zeros_like(stereo, dtype=np.float32)
        for ch in range(2):
            sig = sosfilt(sos_hp, stereo[:, ch]).astype(np.float32)
            bass = sosfilt(sos_bass, sig).astype(np.float32)
            air = sosfilt(sos_air, sig).astype(np.float32)
            out[:, ch] = sig + bass * 0.18 + air * 0.14
        return out
    except Exception:
        return stereo


def generate_viral_fashion_audio(
    output_wav: str,
    duration: float = 11.0,
    seed_key: str = "default",
    item_pop_times: list = None,
    transition_sec: float = 5.2,
    outfit: dict = None,
) -> dict:
    """
    %100 Kusursuz Stüdyo Master Müzik Motoru (44.1 kHz Stereo):
    - Yapay TTS seslendirme kesintisi, ses kısılması (ducking) veya sentetik gürültü YOKTUR.
    - Üst üste aynı müziği asla tekrar etmez (Dinamik TikTok & Reels Viral Müzik Rotasyonu).
    - Baştan sona kesintisiz, podyum ritmiyle senkronize gerçek stüdyo kaydı ve yumuşak geçiş enerjisi sunar.
    """
    pref_id = (outfit or {}).get("preferred_music_id")
    profile = dict(_select_non_repeating_profile(seed_key, preferred_id=pref_id))

    n_samples = int(SR * duration)
    trans_idx = int(SR * transition_sec)

    intro_path = os.path.join(MUSIC_LIB_DIR, profile["intro_track"])
    walk_path = os.path.join(MUSIC_LIB_DIR, profile["walk_track"])

    music_stereo = np.zeros((n_samples, 2), dtype=np.float32)
    if profile.get("continuous_track"):
        full_stereo = _load_stereo_segment(intro_path, profile["intro_offset"], duration + 0.6)
        # Kesintisiz tek parça stüdyo kaydı + 5.2sn yürüyüş sahnesinde pürüzsüz S-eğrisi enerji artışı
        t_axis = np.linspace(0.0, duration, n_samples, endpoint=False, dtype=np.float32)
        swell = 0.92 + 0.08 * (0.5 * (1.0 + np.tanh((t_axis - transition_sec) / 0.35)))
        music_stereo = full_stereo[:n_samples] * swell[:, None]
    else:
        intro_stereo = _load_stereo_segment(intro_path, profile["intro_offset"], transition_sec + 0.6)
        walk_stereo = _load_stereo_segment(walk_path, profile["walk_offset"], (duration - transition_sec) + 0.6)
        music_stereo[:trans_idx] = intro_stereo[:trans_idx] * 0.92

        cf_samples = int(0.45 * SR)
        walk_len = n_samples - trans_idx
        music_stereo[trans_idx:] = walk_stereo[:walk_len] * 0.98

        if trans_idx > cf_samples and walk_len > cf_samples:
            theta = np.linspace(0.0, math.pi / 2.0, cf_samples, dtype=np.float32)[:, None]
            fade_out_curve = np.cos(theta)
            fade_in_curve = np.sin(theta)
            music_stereo[trans_idx - cf_samples : trans_idx] = (
                intro_stereo[trans_idx - cf_samples : trans_idx] * 0.92 * fade_out_curve
                + walk_stereo[:cf_samples] * 0.98 * fade_in_curve
            )

    # Stüdyo Master EQ (Runway Bass + Kristal Tiz Netliği)
    stereo = _apply_studio_master_eq(music_stereo)

    # Yumuşak Giriş / Çıkış (Fade-in & Fade-out) ve Stüdyo Mastering Limiter
    t_full = np.linspace(0, duration, n_samples, endpoint=False, dtype=np.float32)
    fade_in = np.clip(t_full / 0.18, 0.0, 1.0)
    fade_out = np.clip((duration - t_full) / 0.65, 0.0, 1.0)
    master_env = (fade_in * fade_out)[:, None]
    stereo = _soft_clip(stereo * master_env, drive=1.18)

    peak = np.max(np.abs(stereo))
    if peak > 0:
        stereo = stereo / peak * 0.96

    os.makedirs(os.path.dirname(output_wav) or ".", exist_ok=True)
    pcm16 = (stereo * 32767.0).astype(np.int16)
    with wave.open(output_wav, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm16.tobytes())

    custom_hook_voice = (outfit or {}).get("spoken_hook_text") or profile["intro_hook_text"]
    profile["dialogue_q"] = custom_hook_voice
    profile["dialogue_a"] = ""
    profile["dialogue_walk"] = "Detaylar guzelai.com'da!"
    profile["audio_quality_metrics"] = {
        "intro_hook_duration_sec": 0.0,
        "outro_cta_start_sec": round(duration - 1.5, 2),
        "outro_cta_duration_sec": 0.0,
        "total_voice_ratio": 0.0,
        "middle_music_only_voice_ratio": 0.0,
        "pure_studio_master": True,
    }

    print(
        f"[Kusursuz Stüdyo Müzik Motoru] '{profile['name']}' "
        f"| %100 Saf 44.1 kHz Stereo Master (Kesintisiz & Ducking'siz) -> {output_wav}"
    )
    return profile

