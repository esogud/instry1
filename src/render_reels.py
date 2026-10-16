import os
import math
import subprocess
from io import BytesIO
from urllib.parse import quote
import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

try:
    from gradio_client import Client, handle_file
    HAS_GRADIO = True
except ImportError:
    HAS_GRADIO = False

from outfit_generator import load_cutout_image


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


def create_watermark_background(watermark_text: str = "@nemigiymeli") -> Image.Image:
    """Referans görseldeki gibi tekrarlayan silik filigranlı (@nemigiymeli tarzı) arka plan."""
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
    pad = blur_radius * 2 + max( abs(offset[0]), abs(offset[1]) )
    canvas = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    alpha = img.split()[3]
    shadow = Image.new("RGBA", img.size, (20, 20, 25, shadow_alpha))
    shadow.putalpha(alpha.point(lambda p: int(p * (shadow_alpha / 255.0))))
    canvas.paste(shadow, (pad + offset[0], pad + offset[1]))
    canvas = canvas.filter(ImageFilter.GaussianBlur(blur_radius))
    canvas.paste(img, (pad, pad), img)
    return canvas


def fetch_or_generate_model_frames(outfit: dict, output_dir: str) -> list:
    """
    1) Varsa önceden üretilmiş sokak stili yürüyüş karelerini yükler,
    2) Yoksa Pollinations Flux (Ücretsiz, API anahtarsız) ile 3 farklı yürüyüş adımı üretir.
    """
    local_frames = [
        "assets/trial1_model_street.jpg",
        "assets/trial1_model_step2.jpg",
        "assets/trial1_model_step3.jpg",
    ]
    loaded = []
    for p in local_frames:
        if os.path.exists(p):
            loaded.append(Image.open(p).convert("RGB").resize((W, H), Image.Resampling.LANCZOS))
    if len(loaded) >= 2:
        loaded[0].save(os.path.join(output_dir, "model_street.png"))
        return loaded

    # Ücretsiz bulut AI görsel üretimi (Pollinations Flux - 0 Maliyet)
    base_prompt = outfit["model_prompt"]
    poses = [
        "right leg stepping forward mid-stride on urban sidewalk",
        "left leg stepping forward mid-stride, jacket swaying naturally",
        "walking closer towards camera with warm confident expression",
    ]
    for idx, pose in enumerate(poses):
        full_prompt = f"{base_prompt}, {pose}"
        url = f"https://image.pollinations.ai/prompt/{quote(full_prompt)}?width=1080&height=1920&seed={100 + idx}&nologo=true&model=flux"
        try:
            resp = requests.get(url, timeout=45)
            if resp.status_code == 200:
                im = Image.open(BytesIO(resp.content)).convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
                loaded.append(im)
        except Exception as e:
            print(f"[AI Model Frame Uyarı] {e}")

    if loaded:
        loaded[0].save(os.path.join(output_dir, "model_street.png"))
    return loaded


def try_free_hf_video_generation(model_img_path: str, out_video_path: str) -> bool:
    """
    Hugging Face ZeroGPU üzerindeki ücretsiz Image-to-Video Space'lerini dener.
    Eğer ücretsiz GPU sırası doluysa False döner ve 2.5D çok-kareli yürüyüş motoru devreye girer.
    """
    if not HAS_GRADIO:
        return False
    spaces = [
        "Lightricks/LTX-Video",
        "Wan-AI/Wan2.1",
    ]
    hf_token = os.environ.get("HF_TOKEN") or None
    for space in spaces:
        try:
            print(f"[HF Ücretsiz Video AI] Deneniyor: {space}...")
            client = Client(space, hf_token=hf_token)
            # ZeroGPU kuyruğu müsaitse yürüyüş videosunu indirir
            res = client.predict(
                handle_file(model_img_path),
                "A stylish young woman walking naturally towards the camera on a city sidewalk, smooth realistic fashion walk, 85mm street photography",
                api_name="/predict"
            )
            if isinstance(res, str) and os.path.exists(res):
                import shutil
                shutil.copy(res, out_video_path)
                return True
        except Exception as e:
            print(f"[HF Space Bilgi] {space} meşgul, yerel yürüyüş motoru kullanılacak ({e})")
    return False


def render_kombin_reel(outfit: dict, output_mp4: str, watermark: str = "@nemigiymeli"):
    os.makedirs(os.path.dirname(output_mp4), exist_ok=True)
    bg_base = create_watermark_background(watermark)

    # 6 Kıyafet Parçasının Graph Motion Yerleşim ve Zamanlama Tablosu (1080x1920 Dikey Reels)
    items_cfg = [
        {
            "key": "outerwear",
            "target_xy": (35, 220),
            "target_size": (535, 550),
            "start_xy": (-580, 140),
            "start_angle": -18.0,
            "t_in": 0.25,
            "label_xy": (300, 795),
        },
        {
            "key": "cap",
            "target_xy": (475, 195),
            "target_size": (225, 155),
            "start_xy": (475, -220),
            "start_angle": 22.0,
            "t_in": 0.85,
            "label_xy": (585, 365),
        },
        {
            "key": "top",
            "target_xy": (640, 210),
            "target_size": (405, 430),
            "start_xy": (1180, 160),
            "start_angle": 16.0,
            "t_in": 1.45,
            "label_xy": (685, 650),
        },
        {
            "key": "bottom",
            "target_xy": (725, 495),
            "target_size": (245, 720),
            "start_xy": (1220, 750),
            "start_angle": 10.0,
            "t_in": 2.05,
            "label_xy": (660, 1185),
        },
        {
            "key": "bag",
            "target_xy": (405, 725),
            "target_size": (235, 270),
            "start_xy": (405, 1980),
            "start_angle": -15.0,
            "t_in": 2.65,
            "label_xy": (520, 1015),
        },
        {
            "key": "shoes",
            "target_xy": (115, 1035),
            "target_size": (345, 155),
            "start_xy": (-420, 1080),
            "start_angle": 14.0,
            "t_in": 3.25,
            "label_xy": (290, 1215),
        },
    ]

    # Görselleri hazırla
    prepared_items = []
    for cfg in items_cfg:
        item_data = outfit["items"][cfg["key"]]
        raw_img = load_cutout_image(item_data)
        raw_img.thumbnail(cfg["target_size"], Image.Resampling.LANCZOS)
        shadowed = add_drop_shadow(raw_img)
        prepared_items.append({**cfg, "data": item_data, "img": shadowed})

    # Yürüyen model karelerini hazırla
    model_frames = fetch_or_generate_model_frames(outfit, os.path.dirname(output_mp4))

    font_header = get_font(42, bold=True)
    font_brand = get_font(34, bold=True)
    font_price = get_font(28, bold=True)
    font_badge = get_font(36, bold=True)

    total_duration = 11.0  # 0-5.5sn Graph Motion Kombin | 5.5-11.0sn Sokakta Yürüyen Model
    total_frames = int(total_duration * FPS)
    collage_end_sec = 5.4

    frames_dir = os.path.join(os.path.dirname(output_mp4), "_frames")
    os.makedirs(frames_dir, exist_ok=True)

    for f_idx in range(total_frames):
        t = f_idx / FPS

        if t <= collage_end_sec + 0.5:
            canvas = bg_base.copy()
            draw = ImageDraw.Draw(canvas)

            # Üst Başlık Bandı
            header_alpha = int(min(1.0, t / 0.4) * 255)
            draw.rounded_rectangle((260, 85, 820, 155), radius=35, fill=(28, 28, 30, header_alpha))
            draw.text((540, 120), "GÜNÜN KOMBİNİ", fill=(255, 255, 255, header_alpha), font=font_header, anchor="mm")

            for idx, p in enumerate(prepared_items):
                dt = (t - p["t_in"]) / 0.65
                if dt <= 0:
                    continue
                prog = ease_out_back(min(1.0, dt))
                # Graph Motion: dışarıdan yaylanarak yerine oturma + hafif süzülme (floating motion)
                float_y = math.sin(t * 3.2 + idx * 1.1) * 5.0 if dt >= 1.0 else 0.0
                cur_x = int(p["start_xy"][0] + (p["target_xy"][0] - p["start_xy"][0]) * prog)
                cur_y = int(p["start_xy"][1] + (p["target_xy"][1] - p["start_xy"][1]) * prog + float_y)
                cur_angle = p["start_angle"] * (1.0 - min(1.0, dt))

                item_img = p["img"]
                if abs(cur_angle) > 0.3:
                    item_img = item_img.rotate(cur_angle, resample=Image.Resampling.BICUBIC, expand=True)

                canvas.paste(item_img, (cur_x, cur_y), item_img)

                # Marka & Fiyat etiketi animasyonu
                if dt > 0.45:
                    lbl_prog = min(1.0, (dt - 0.45) / 0.4)
                    lx, ly = p["label_xy"]
                    ly_anim = int(ly + (1.0 - lbl_prog) * 22)
                    brand = p["data"]["brand"]
                    price = p["data"]["price"]
                    if brand:
                        draw.text((lx, ly_anim), brand, fill=(25, 25, 25, 255), font=font_brand, anchor="mm")
                        draw.text((lx, ly_anim + 34), price, fill=(45, 45, 45, 255), font=font_price, anchor="mm")
                    else:
                        draw.text((lx, ly_anim), price, fill=(25, 25, 25, 255), font=font_brand, anchor="mm")

            # Alt Toplam Kombin Bandı
            if t > 3.9:
                b_prog = ease_out_back(min(1.0, (t - 3.9) / 0.5))
                by = int(1720 - b_prog * 140)
                draw.rounded_rectangle((140, by, 940, by + 95), radius=48, fill=(25, 25, 28, 245))
                draw.text((540, by + 48), "TOPLAM KOMBİN: 1.383,15₺  •  KAYDET", fill=(255, 255, 255, 255), font=font_badge, anchor="mm")

            if abs(t - 5.0) < (0.5 / FPS):
                canvas.convert("RGB").save(os.path.join(os.path.dirname(output_mp4), "kombin_collage.png"))

        # 2. BÖLÜM: Kıyafetlerin Güzel Bir Kıza Giydirilip Sokakta Yürütülmesi (5.2sn - 11.0sn)
        if t >= collage_end_sec:
            walk_t = t - collage_end_sec
            walk_dur = total_duration - collage_end_sec
            norm_w = walk_t / walk_dur  # 0.0 -> 1.0

            # Çok kareli yürüyüş adımı geçişi (Step 1 -> Step 2 -> Step 3 -> Step 2 -> Step 1) + Kamera Takip (Dolly Zoom & Yürüyüş Salınımı)
            n_models = len(model_frames)
            if n_models > 0:
                cycle_pos = (walk_t * 1.65) % n_models
                idx_a = int(math.floor(cycle_pos)) % n_models
                idx_b = (idx_a + 1) % n_models
                blend = ease_in_out_cubic(cycle_pos - math.floor(cycle_pos))
                blended_model = Image.blend(model_frames[idx_a], model_frames[idx_b], blend)

                # Yürüyüş adımı dikey yaylanması (walking cadence bobbing) ve ileri doğru yaklaşma
                zoom = 1.03 + 0.09 * norm_w
                bob_y = math.sin(walk_t * math.pi * 3.3) * 11.0
                sway_x = math.cos(walk_t * math.pi * 1.65) * 6.0

                crop_w = int(W / zoom)
                crop_h = int(H / zoom)
                cx = int((W - crop_w) / 2 + sway_x)
                cy = int((H - crop_h) / 2 + bob_y)
                cx = max(0, min(W - crop_w, cx))
                cy = max(0, min(H - crop_h, cy))

                walk_frame = blended_model.crop((cx, cy, cx + crop_w, cy + crop_h)).resize((W, H), Image.Resampling.LANCZOS).convert("RGBA")
            else:
                walk_frame = bg_base.copy()

            # Sol üstte mini kombin referans kartı (izleyicinin kıyafetleri karşılaştırması için)
            mini_draw = ImageDraw.Draw(walk_frame)
            mini_draw.rounded_rectangle((45, 90, 560, 165), radius=36, fill=(20, 20, 24, 215))
            mini_draw.text((302, 128), "KOMBİNİN DURUŞU", fill=(255, 255, 255, 255), font=font_badge, anchor="mm")

            # Yürürken alt kısımda kayan parça etiketleri
            mini_draw.rounded_rectangle((65, 1620, 1015, 1730), radius=28, fill=(255, 255, 255, 225))
            mini_draw.text(
                (540, 1675),
                "H&M Ceket 379₺ • UCLA Kep 59,97₺ • ZARA Tayt 139,95₺ • NB 469,99₺",
                fill=(20, 20, 22, 255),
                font=font_price,
                anchor="mm"
            )

            # Sahne geçiş efekti (Flash & Cross-Dissolve)
            if t < collage_end_sec + 0.45:
                tr = (t - collage_end_sec) / 0.45
                final_frame = Image.blend(canvas.convert("RGB"), walk_frame.convert("RGB"), ease_in_out_cubic(tr))
            else:
                final_frame = walk_frame.convert("RGB")
        else:
            final_frame = canvas.convert("RGB")

        final_frame.save(os.path.join(frames_dir, f"frame_{f_idx:04d}.jpg"), quality=92)

    # Telifsiz moda ritmi (beat) ses dosyası oluştur ve FFmpeg ile MP4'e dönüştür
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", os.path.join(frames_dir, "frame_%04d.jpg"),
        "-f", "lavfi", "-i", "sine=frequency=110:sample_rate=44100",
        "-t", str(total_duration),
        "-filter_complex", "[1:a]volume=0.03,afade=t=out:st=9.5:d=1.5[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "21",
        "-c:a", "aac", "-shortest",
        output_mp4
    ]
    subprocess.run(cmd, check=True)
    print(f"[BAŞARILI] Reels videosu üretildi: {output_mp4}")
