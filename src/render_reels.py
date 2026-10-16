import os
import math
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

from outfit_generator import load_cutout_image
from music_generator import generate_viral_fashion_audio


# 2K QHD+ Dikey Çözünürlük (Samsung Dynamic AMOLED 2X / 1440x2560 9:16 Standardı)
W, H = 1440, 2560
SCALE = W / 1080.0  # 1.3333x Süper-Örnekleme Ölçeği
FPS = 30


def S(val: float) -> int:
    """1080p koordinat ve boyutlarını 2K (1440x2560) çözünürlüğe kayıpsız ölçekler."""
    return int(round(val * SCALE))


def ease_out_back(t: float) -> float:
    """Graph Motion yaylanma (spring overshoot) eğrisi."""
    t = max(0.0, min(1.0, t))
    c1 = 1.70158
    c3 = c1 + 1.0
    return 1.0 + c3 * pow(t - 1.0, 3) + c1 * pow(t - 1.0, 2)


def ease_in_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2


def enhance_for_samsung_oled(img: Image.Image, is_cutout: bool = False) -> Image.Image:
    """
    Samsung Dynamic AMOLED 2X ekranlar için mikro-kontrast, kumaş dokusu keskinleştirme
    (Unsharp Mask) ve canlı renk doygunluğu optimizasyonu uygular.
    """
    has_alpha = img.mode == "RGBA"
    if has_alpha:
        r, g, b, a = img.split()
        rgb = Image.merge("RGB", (r, g, b))
    else:
        rgb = img.convert("RGB")

    # 1) Mikro-kontrast ve OLED derin siyah/parlaklık dengesi
    rgb = ImageEnhance.Contrast(rgb).enhance(1.07 if is_cutout else 1.09)
    # 2) Samsung AMOLED canlı renk kalibrasyonu
    rgb = ImageEnhance.Color(rgb).enhance(1.08 if is_cutout else 1.11)
    # 3) Kumaş dokusu, dikiş ve saç teli netliği için UnsharpMask
    rgb = rgb.filter(ImageFilter.UnsharpMask(radius=1.5, percent=135, threshold=2))

    if has_alpha:
        r2, g2, b2 = rgb.split()
        return Image.merge("RGBA", (r2, g2, b2, a))
    return rgb


def get_font(size_1080: int, bold: bool = True):
    size = S(size_1080)
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/georgia.ttf",
        "C:/Windows/Fonts/courbd.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def create_watermark_background(watermark_text: str = "@guzelaicom") -> Image.Image:
    """2K (1440x2560) çözünürlükte tekrarlayan silik filigranlı (@guzelaicom) arka plan."""
    bg = Image.new("RGBA", (W, H), (250, 249, 247, 255))
    draw = ImageDraw.Draw(bg)
    wm_font = get_font(22, bold=False)
    step_x = S(195)
    step_y = S(40)
    for y in range(S(10), H, step_y):
        for x in range(S(-40), W, step_x):
            draw.text((x, y), watermark_text, fill=(233, 231, 227, 255), font=wm_font)
    return bg


def add_drop_shadow(img: Image.Image, offset=(11, 19), blur_radius=16, shadow_alpha=52) -> Image.Image:
    """2K çözünürlükte gerçek kıyafet dekupe fotoğraflarına derinlik katan yumuşak OLED gölge."""
    pad = blur_radius * 2 + max(abs(offset[0]), abs(offset[1]))
    canvas = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    alpha = img.split()[3]
    shadow = Image.new("RGBA", img.size, (12, 12, 16, shadow_alpha))
    shadow.putalpha(alpha.point(lambda p: int(p * (shadow_alpha / 255.0))))
    canvas.paste(shadow, (pad + offset[0], pad + offset[1]))
    canvas = canvas.filter(ImageFilter.GaussianBlur(blur_radius))
    canvas.paste(img, (pad, pad), img)
    return canvas


def fetch_or_generate_model_frames(outfit: dict, output_dir: str) -> list:
    """Seçilen kombin arketipine ait yürüyüş karelerini 2K (1440x2560) Samsung OLED kalitesinde yükler."""
    candidate_frames = outfit.get("model_frames") or [
        "assets/outfit3_model_step1.jpg",
        "assets/outfit3_model_step2.jpg",
        "assets/outfit3_model_step3.jpg",
    ]
    loaded = []
    for p in candidate_frames:
        if os.path.exists(p):
            im = Image.open(p).convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
            im = enhance_for_samsung_oled(im, is_cutout=False)
            loaded.append(im)

    if len(loaded) < 2:
        fallback_frames = [
            "assets/trial1_model_street.jpg",
            "assets/trial1_model_step2.jpg",
            "assets/trial1_model_step3.jpg",
        ]
        for p in fallback_frames:
            if os.path.exists(p):
                im = Image.open(p).convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
                im = enhance_for_samsung_oled(im, is_cutout=False)
                loaded.append(im)

    if loaded:
        loaded[0].save(os.path.join(output_dir, "model_street.png"), compress_level=1)
    return loaded


def render_kombin_reel(outfit: dict, output_mp4: str, watermark: str = "@guzelaicom") -> dict:
    out_dir = os.path.dirname(output_mp4) or "."
    os.makedirs(out_dir, exist_ok=True)
    bg_base = create_watermark_background(watermark)

    # 6 Kıyafet Parçasının 2K (1440x2560) Graph Motion Yerleşim ve Zamanlama Tablosu
    items_cfg = [
        {
            "key": "outerwear",
            "target_xy": (S(35), S(215)),
            "target_size": (S(510), S(540)),
            "start_xy": (S(-580), S(140)),
            "start_angle": -18.0,
            "t_in": 0.25,
            "label_xy": (S(290), S(795)),
        },
        {
            "key": "cap",
            "target_xy": (S(480), S(195)),
            "target_size": (S(230), S(140)),
            "start_xy": (S(480), S(-220)),
            "start_angle": 22.0,
            "t_in": 0.85,
            "label_xy": (S(595), S(355)),
        },
        {
            "key": "top",
            "target_xy": (S(625), S(215)),
            "target_size": (S(410), S(415)),
            "start_xy": (S(1180), S(160)),
            "start_angle": 16.0,
            "t_in": 1.45,
            "label_xy": (S(825), S(655)),
        },
        {
            "key": "bottom",
            "target_xy": (S(685), S(520)),
            "target_size": (S(310), S(690)),
            "start_xy": (S(1220), S(750)),
            "start_angle": 10.0,
            "t_in": 2.05,
            "label_xy": (S(835), S(1245)),
        },
        {
            "key": "bag",
            "target_xy": (S(355), S(735)),
            "target_size": (S(270), S(275)),
            "start_xy": (S(355), S(1980)),
            "start_angle": -15.0,
            "t_in": 2.65,
            "label_xy": (S(490), S(1040)),
        },
        {
            "key": "shoes",
            "target_xy": (S(85), S(1055)),
            "target_size": (S(375), S(190)),
            "start_xy": (S(-420), S(1080)),
            "start_angle": 14.0,
            "t_in": 3.25,
            "label_xy": (S(280), S(1265)),
        },
    ]

    # Görselleri 2K çözünürlüğe ölçekle ve Samsung OLED keskinleştirmesi uygula
    prepared_items = []
    for cfg in items_cfg:
        item_data = outfit["items"][cfg["key"]]
        raw_img = load_cutout_image(item_data)
        # Küçük dekupe görsellerini de tam 2K hedef kutusuna Lanczos ile büyüt
        tw, th = cfg["target_size"]
        scale_f = min(tw / max(1, raw_img.width), th / max(1, raw_img.height))
        new_w = max(1, int(round(raw_img.width * scale_f)))
        new_h = max(1, int(round(raw_img.height * scale_f)))
        raw_img = raw_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        raw_img = enhance_for_samsung_oled(raw_img, is_cutout=True)
        shadowed = add_drop_shadow(raw_img)
        prepared_items.append({**cfg, "data": item_data, "img": shadowed})

    # Yürüyen model karelerini 2K OLED kalitesinde hazırla
    model_frames = fetch_or_generate_model_frames(outfit, out_dir)

    font_header = get_font(40, bold=True)
    font_brand = get_font(31, bold=True)
    font_price = get_font(27, bold=True)
    font_badge = get_font(33, bold=True)
    font_sub = get_font(24, bold=True)
    font_legal = get_font(19, bold=False)

    total_duration = 11.0
    total_frames = int(total_duration * FPS)
    collage_end_sec = 5.4

    total_price_str = outfit.get("total_price_str", "2.490₺")
    it_map = outfit["items"]
    walk_summary_line = (
        f"{it_map['outerwear']['brand']} {it_map['outerwear']['price']} • "
        f"{it_map['top']['brand']} {it_map['top']['price']} • "
        f"{it_map['bottom']['brand']} {it_map['bottom']['price']} • "
        f"{it_map['shoes']['brand']} {it_map['shoes']['price']}"
    )
    if len(walk_summary_line) > 66:
        walk_summary_line = walk_summary_line[:64] + "..."

    frames_dir = os.path.join(out_dir, "_frames")
    os.makedirs(frames_dir, exist_ok=True)

    for f_idx in range(total_frames):
        t = f_idx / FPS

        if t <= collage_end_sec + 0.5:
            canvas = bg_base.copy()
            draw = ImageDraw.Draw(canvas)

            # Üst Başlık Bandı (True OLED Black)
            header_alpha = int(min(1.0, t / 0.4) * 255)
            draw.rounded_rectangle((S(220), S(80), S(860), S(152)), radius=S(36), fill=(10, 10, 14, header_alpha))
            draw.text((S(540), S(116)), "GÜNÜN KOMBİNİ • LİNKLİ", fill=(255, 255, 255, header_alpha), font=font_header, anchor="mm")

            # 1) Önce tüm kıyafet görsellerini çiz
            active_labels = []
            for idx, p in enumerate(prepared_items):
                dt = (t - p["t_in"]) / 0.65
                if dt <= 0:
                    continue
                prog = ease_out_back(min(1.0, dt))
                float_y = math.sin(t * 3.2 + idx * 1.1) * S(5.0) if dt >= 1.0 else 0.0
                cur_x = int(p["start_xy"][0] + (p["target_xy"][0] - p["start_xy"][0]) * prog)
                cur_y = int(p["start_xy"][1] + (p["target_xy"][1] - p["start_xy"][1]) * prog + float_y)
                cur_angle = p["start_angle"] * (1.0 - min(1.0, dt))

                item_img = p["img"]
                if abs(cur_angle) > 0.3:
                    item_img = item_img.rotate(cur_angle, resample=Image.Resampling.BICUBIC, expand=True)

                canvas.paste(item_img, (cur_x, cur_y), item_img)

                if dt > 0.45:
                    lbl_prog = min(1.0, (dt - 0.45) / 0.4)
                    lx, ly = p["label_xy"]
                    ly_anim = int(ly + (1.0 - lbl_prog) * S(22))
                    active_labels.append((lx, ly_anim, p["data"]))

            # 2) Tüm marka ve fiyat etiketlerini görsellerin üst katmanına çiz
            for lx, ly_anim, item_d in active_labels:
                brand = (item_d.get("brand") or "").strip()
                if len(brand) > 15:
                    brand = brand[:14] + "."
                price = item_d["price"]
                if brand:
                    draw.text((lx, ly_anim), brand, fill=(14, 14, 18, 255), font=font_brand, anchor="mm")
                    draw.text((lx, ly_anim + S(34)), price, fill=(38, 38, 42, 255), font=font_price, anchor="mm")
                else:
                    draw.text((lx, ly_anim), price, fill=(14, 14, 18, 255), font=font_brand, anchor="mm")

            # Alt Toplam Kombin & Link Bilgisi Bandı (True OLED Black)
            if t > 3.85:
                b_prog = ease_out_back(min(1.0, (t - 3.85) / 0.5))
                by = int(S(1710) - b_prog * S(155))
                draw.rounded_rectangle((S(85), by, S(995), by + S(138)), radius=S(48), fill=(10, 10, 14, 250))
                draw.text(
                    (S(540), by + S(35)),
                    f"TOPLAM KOMBİN: {total_price_str}  •  KAYDET",
                    fill=(255, 255, 255, 255),
                    font=font_badge,
                    anchor="mm",
                )
                draw.text(
                    (S(540), by + S(76)),
                    "» LİNKLER AÇIKLAMADA, YORUMDA & THREADS'TE «",
                    fill=(242, 218, 178, 255),
                    font=font_sub,
                    anchor="mm",
                )
                draw.text(
                    (S(540), by + S(114)),
                    "Reklam / iş birliği içermez • Kombin önerisidir (zorunlu #reklam)",
                    fill=(195, 195, 202, 245),
                    font=font_legal,
                    anchor="mm",
                )

            if abs(t - 5.0) < (0.5 / FPS):
                canvas.convert("RGB").save(os.path.join(out_dir, "kombin_collage.png"), compress_level=1)

        # 2. BÖLÜM: 2K Sokakta / Mekanda Yürüyen Model (5.4sn - 11.0sn)
        if t >= collage_end_sec:
            walk_t = t - collage_end_sec
            walk_dur = total_duration - collage_end_sec
            norm_w = walk_t / walk_dur

            n_models = len(model_frames)
            if n_models > 0:
                cycle_pos = (walk_t * 1.65) % n_models
                idx_a = int(math.floor(cycle_pos)) % n_models
                idx_b = (idx_a + 1) % n_models
                blend = ease_in_out_cubic(cycle_pos - math.floor(cycle_pos))
                blended_model = Image.blend(model_frames[idx_a], model_frames[idx_b], blend)

                zoom = 1.03 + 0.08 * norm_w
                bob_y = math.sin(walk_t * math.pi * 3.3) * S(10.0)
                sway_x = math.cos(walk_t * math.pi * 1.65) * S(5.5)

                crop_w = int(W / zoom)
                crop_h = int(H / zoom)
                cx = max(0, min(W - crop_w, int((W - crop_w) / 2 + sway_x)))
                cy = max(0, min(H - crop_h, int((H - crop_h) / 2 + bob_y)))

                walk_frame = blended_model.crop((cx, cy, cx + crop_w, cy + crop_h)).resize((W, H), Image.Resampling.LANCZOS).convert("RGBA")
            else:
                walk_frame = bg_base.copy()

            mini_draw = ImageDraw.Draw(walk_frame)
            mini_draw.rounded_rectangle((S(45), S(90), S(620), S(165)), radius=S(36), fill=(10, 10, 14, 228))
            mini_draw.text((S(332), S(128)), "KOMBİNİN DURUŞU • 2K UHD", fill=(255, 255, 255, 255), font=font_badge, anchor="mm")

            mini_draw.rounded_rectangle((S(55), S(1595), S(1025), S(1755)), radius=S(30), fill=(255, 255, 255, 240))
            mini_draw.text(
                (S(540), S(1632)),
                walk_summary_line,
                fill=(12, 12, 16, 255),
                font=font_price,
                anchor="mm",
            )
            mini_draw.text(
                (S(540), S(1680)),
                "» Ürün linkleri açıklamada, ilk yorumda & Threads'te! «",
                fill=(65, 45, 30, 255),
                font=font_sub,
                anchor="mm",
            )
            mini_draw.text(
                (S(540), S(1724)),
                "Reklam / iş birliği içermez • Kombin önerisidir (zorunlu #reklam)",
                fill=(105, 105, 112, 255),
                font=font_legal,
                anchor="mm",
            )

            if t < collage_end_sec + 0.45:
                tr = (t - collage_end_sec) / 0.45
                final_frame = Image.blend(canvas.convert("RGB"), walk_frame.convert("RGB"), ease_in_out_cubic(tr))
            else:
                final_frame = walk_frame.convert("RGB")
        else:
            final_frame = canvas.convert("RGB")

        # 4:4:4 Tam Chroma (subsampling=0) ve %98 Kalite ile Kayıpsız Ara Kare Kaydı
        final_frame.save(os.path.join(frames_dir, f"frame_{f_idx:04d}.jpg"), quality=98, subsampling=0)

    # Viral Moda / Kombin Reels Müziği + Hareket Ses Efektlerini Üret
    wav_path = os.path.join(out_dir, "viral_fashion_track.wav")
    pop_times = [c["t_in"] for c in items_cfg]
    music_info = generate_viral_fashion_audio(
        output_wav=wav_path,
        duration=total_duration,
        seed_key=outfit.get("timestamp", "default"),
        item_pop_times=pop_times,
        transition_sec=collage_end_sec,
    )
    outfit["music_info"] = music_info

    # 2K QHD+ (1440x2560) Samsung OLED Master Kodlama:
    # - BT.709 tam renk uzayı ve kontrast bayrakları
    # - Luma/Chroma unsharp mask filtresi (unsharp=5:5:0.55:3:3:0.0)
    # - Yüksek profil H.264 (CRF 15, ~18 Mbps tavan bit hızı)
    import shutil
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        import imageio_ffmpeg
        ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()

    cmd = [
        ffmpeg_bin, "-y",
        "-framerate", str(FPS),
        "-i", os.path.join(frames_dir, "frame_%04d.jpg"),
        "-i", wav_path,
        "-t", str(total_duration),
        "-vf", "unsharp=5:5:0.55:3:3:0.0",
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264",
        "-preset", "slow",
        "-profile:v", "high",
        "-level:v", "5.1",
        "-crf", "15",
        "-b:v", "16M",
        "-maxrate", "20M",
        "-bufsize", "32M",
        "-pix_fmt", "yuv420p",
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-colorspace", "bt709",
        "-color_range", "tv",
        "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "256k", "-ar", "44100", "-ac", "2",
        "-shortest",
        output_mp4,
    ]
    subprocess.run(cmd, check=True)
    print(f"[BAŞARILI] 2K QHD+ (1440x2560) Samsung OLED Master Reels videosu üretildi: {output_mp4}")
    return music_info
