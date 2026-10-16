import os
import math
import subprocess
from io import BytesIO
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from outfit_generator import load_cutout_image
from music_generator import generate_viral_fashion_audio


W, H = 1080, 1920
FPS = 30


def ease_out_back(t: float) -> float:
    """Graph Motion yaylanma (spring overshoot) eğrisi."""
    t = max(0.0, min(1.0, t))
    c1 = 1.70158
    c3 = c1 + 1.0
    return 1.0 + c3 * pow(t - 1.0, 3) + c1 * pow(t - 1.0, 2)


def ease_in_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2


def get_font(size: int, bold: bool = True):
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
    """Tekrarlayan silik filigranlı (@guzelaicom) arka plan."""
    bg = Image.new("RGBA", (W, H), (249, 248, 246, 255))
    draw = ImageDraw.Draw(bg)
    wm_font = get_font(22, bold=False)
    step_x = 195
    step_y = 40
    for y in range(10, H, step_y):
        for x in range(-40, W, step_x):
            draw.text((x, y), watermark_text, fill=(233, 231, 227, 255), font=wm_font)
    return bg


def add_drop_shadow(img: Image.Image, offset=(8, 14), blur_radius=12, shadow_alpha=45) -> Image.Image:
    """Gerçek kıyafet dekupe fotoğraflarına derinlik katan yumuşak gölge."""
    pad = blur_radius * 2 + max(abs(offset[0]), abs(offset[1]))
    canvas = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    alpha = img.split()[3]
    shadow = Image.new("RGBA", img.size, (20, 20, 25, shadow_alpha))
    shadow.putalpha(alpha.point(lambda p: int(p * (shadow_alpha / 255.0))))
    canvas.paste(shadow, (pad + offset[0], pad + offset[1]))
    canvas = canvas.filter(ImageFilter.GaussianBlur(blur_radius))
    canvas.paste(img, (pad, pad), img)
    return canvas


def fetch_or_generate_model_frames(outfit: dict, output_dir: str) -> list:
    """Seçilen kombin arketipine ait sokak stili yürüyüş karelerini yükler."""
    candidate_frames = outfit.get("model_frames") or [
        "assets/outfit2_model_step1.jpg",
        "assets/outfit2_model_step2.jpg",
        "assets/outfit2_model_step3.jpg",
    ]
    loaded = []
    for p in candidate_frames:
        if os.path.exists(p):
            loaded.append(Image.open(p).convert("RGB").resize((W, H), Image.Resampling.LANCZOS))

    if len(loaded) < 2:
        fallback_frames = [
            "assets/trial1_model_street.jpg",
            "assets/trial1_model_step2.jpg",
            "assets/trial1_model_step3.jpg",
        ]
        for p in fallback_frames:
            if os.path.exists(p):
                loaded.append(Image.open(p).convert("RGB").resize((W, H), Image.Resampling.LANCZOS))

    if loaded:
        loaded[0].save(os.path.join(output_dir, "model_street.png"))
    return loaded


def render_kombin_reel(outfit: dict, output_mp4: str, watermark: str = "@guzelaicom") -> dict:
    out_dir = os.path.dirname(output_mp4) or "."
    os.makedirs(out_dir, exist_ok=True)
    bg_base = create_watermark_background(watermark)

    # 6 Kıyafet Parçasının Graph Motion Yerleşim ve Zamanlama Tablosu (1080x1920 Dikey Reels)
    items_cfg = [
        {
            "key": "outerwear",
            "target_xy": (35, 215),
            "target_size": (510, 540),
            "start_xy": (-580, 140),
            "start_angle": -18.0,
            "t_in": 0.25,
            "label_xy": (290, 795),
        },
        {
            "key": "cap",
            "target_xy": (480, 195),
            "target_size": (230, 140),
            "start_xy": (480, -220),
            "start_angle": 22.0,
            "t_in": 0.85,
            "label_xy": (595, 355),
        },
        {
            "key": "top",
            "target_xy": (625, 215),
            "target_size": (410, 415),
            "start_xy": (1180, 160),
            "start_angle": 16.0,
            "t_in": 1.45,
            "label_xy": (825, 655),
        },
        {
            "key": "bottom",
            "target_xy": (685, 520),
            "target_size": (310, 690),
            "start_xy": (1220, 750),
            "start_angle": 10.0,
            "t_in": 2.05,
            "label_xy": (835, 1245),
        },
        {
            "key": "bag",
            "target_xy": (355, 735),
            "target_size": (270, 275),
            "start_xy": (355, 1980),
            "start_angle": -15.0,
            "t_in": 2.65,
            "label_xy": (490, 1040),
        },
        {
            "key": "shoes",
            "target_xy": (85, 1055),
            "target_size": (375, 190),
            "start_xy": (-420, 1080),
            "start_angle": 14.0,
            "t_in": 3.25,
            "label_xy": (280, 1265),
        },
    ]

    # Görselleri hazırla
    prepared_items = []
    for cfg in items_cfg:
        item_data = outfit["items"][cfg["key"]]
        # Yeni kombin arketipinde temiz stüdyo dekupesini önceliklendir (mankenli ürün fotoğraflarının kolajı bozmaması için)
        raw_img = load_cutout_image(item_data)
        raw_img.thumbnail(cfg["target_size"], Image.Resampling.LANCZOS)
        shadowed = add_drop_shadow(raw_img)
        prepared_items.append({**cfg, "data": item_data, "img": shadowed})

    # Yürüyen model karelerini hazırla
    model_frames = fetch_or_generate_model_frames(outfit, out_dir)

    font_header = get_font(40, bold=True)
    font_brand = get_font(31, bold=True)
    font_price = get_font(27, bold=True)
    font_badge = get_font(33, bold=True)
    font_sub = get_font(25, bold=True)

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

            # Üst Başlık Bandı
            header_alpha = int(min(1.0, t / 0.4) * 255)
            draw.rounded_rectangle((220, 80, 860, 152), radius=36, fill=(24, 24, 28, header_alpha))
            draw.text((540, 116), "GÜNÜN KOMBİNİ • LİNKLİ", fill=(255, 255, 255, header_alpha), font=font_header, anchor="mm")

            # 1) Önce tüm kıyafet görsellerini çiz
            active_labels = []
            for idx, p in enumerate(prepared_items):
                dt = (t - p["t_in"]) / 0.65
                if dt <= 0:
                    continue
                prog = ease_out_back(min(1.0, dt))
                float_y = math.sin(t * 3.2 + idx * 1.1) * 5.0 if dt >= 1.0 else 0.0
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
                    ly_anim = int(ly + (1.0 - lbl_prog) * 22)
                    active_labels.append((lx, ly_anim, p["data"]))

            # 2) Tüm marka ve fiyat etiketlerini görsellerin üst katmanına çiz
            for lx, ly_anim, item_d in active_labels:
                brand = (item_d.get("brand") or "").strip()
                if len(brand) > 15:
                    brand = brand[:14] + "."
                price = item_d["price"]
                if brand:
                    draw.text((lx, ly_anim), brand, fill=(22, 22, 24, 255), font=font_brand, anchor="mm")
                    draw.text((lx, ly_anim + 34), price, fill=(45, 45, 48, 255), font=font_price, anchor="mm")
                else:
                    draw.text((lx, ly_anim), price, fill=(22, 22, 24, 255), font=font_brand, anchor="mm")

            # Alt Toplam Kombin & Link Bilgisi Bandı
            if t > 3.85:
                b_prog = ease_out_back(min(1.0, (t - 3.85) / 0.5))
                by = int(1720 - b_prog * 155)
                draw.rounded_rectangle((95, by, 985, by + 115), radius=48, fill=(22, 22, 26, 248))
                draw.text(
                    (540, by + 38),
                    f"TOPLAM KOMBİN: {total_price_str}  •  KAYDET",
                    fill=(255, 255, 255, 255),
                    font=font_badge,
                    anchor="mm",
                )
                draw.text(
                    (540, by + 82),
                    "» ÜRÜN LİNKLERİ AÇIKLAMADA & İLK YORUMDA «",
                    fill=(235, 212, 175, 255),
                    font=font_sub,
                    anchor="mm",
                )

            if abs(t - 5.0) < (0.5 / FPS):
                canvas.convert("RGB").save(os.path.join(out_dir, "kombin_collage.png"))

        # 2. BÖLÜM: Sokakta Yürüyen Model (5.4sn - 11.0sn)
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

                zoom = 1.03 + 0.09 * norm_w
                bob_y = math.sin(walk_t * math.pi * 3.3) * 11.0
                sway_x = math.cos(walk_t * math.pi * 1.65) * 6.0

                crop_w = int(W / zoom)
                crop_h = int(H / zoom)
                cx = max(0, min(W - crop_w, int((W - crop_w) / 2 + sway_x)))
                cy = max(0, min(H - crop_h, int((H - crop_h) / 2 + bob_y)))

                walk_frame = blended_model.crop((cx, cy, cx + crop_w, cy + crop_h)).resize((W, H), Image.Resampling.LANCZOS).convert("RGBA")
            else:
                walk_frame = bg_base.copy()

            mini_draw = ImageDraw.Draw(walk_frame)
            mini_draw.rounded_rectangle((45, 90, 620, 165), radius=36, fill=(20, 20, 24, 215))
            mini_draw.text((332, 128), "KOMBİNİN DURUŞU • LİNKLİ", fill=(255, 255, 255, 255), font=font_badge, anchor="mm")

            mini_draw.rounded_rectangle((55, 1605, 1025, 1735), radius=30, fill=(255, 255, 255, 232))
            mini_draw.text(
                (540, 1648),
                walk_summary_line,
                fill=(20, 20, 22, 255),
                font=font_price,
                anchor="mm",
            )
            mini_draw.text(
                (540, 1695),
                "» Tüm ürün linkleri & kodları açıklamada ve ilk yorumda! «",
                fill=(70, 50, 35, 255),
                font=font_sub,
                anchor="mm",
            )

            if t < collage_end_sec + 0.45:
                tr = (t - collage_end_sec) / 0.45
                final_frame = Image.blend(canvas.convert("RGB"), walk_frame.convert("RGB"), ease_in_out_cubic(tr))
            else:
                final_frame = walk_frame.convert("RGB")
        else:
            final_frame = canvas.convert("RGB")

        final_frame.save(os.path.join(frames_dir, f"frame_{f_idx:04d}.jpg"), quality=92)

    # Viral Moda / Kombin Reels Müziği + Hareket Ses Efektlerini (Whoosh/Pop + Bass Drop) Üret
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

    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", os.path.join(frames_dir, "frame_%04d.jpg"),
        "-i", wav_path,
        "-t", str(total_duration),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "21",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-shortest",
        output_mp4,
    ]
    subprocess.run(cmd, check=True)
    print(f"[BAŞARILI] Viral müzikli Reels videosu üretildi: {output_mp4}")
    return music_info
