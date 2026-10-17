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


def _draw_auto_pill_badge(
    draw: ImageDraw.ImageDraw,
    center_x: int,
    center_y: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill_rgba: tuple,
    text_rgba: tuple,
    pad_x: int,
    pad_y: int,
    radius: int,
    outline_rgba: tuple = None,
    outline_width: int = 0,
):
    """Metin genişliğini ölçerek kutunun dışına taşmayan otomatik boyutlu kapsül rozet çizer."""
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    except Exception:
        tw = int(len(text) * S(18))
        th = S(32)
    half_w = min((W - S(40)) // 2, (tw // 2) + pad_x)
    half_h = (th // 2) + pad_y
    rect = (center_x - half_w, center_y - half_h, center_x + half_w, center_y + half_h)
    draw.rounded_rectangle(
        rect,
        radius=radius,
        fill=fill_rgba,
        outline=outline_rgba,
        width=outline_width,
    )
    draw.text((center_x, center_y), text, fill=text_rgba, font=font, anchor="mm")


def _tr_upper(s: str) -> str:
    return (s or "").replace("i", "İ").replace("ı", "I").upper()


def _wrap_hook_lines(text: str, max_chars: int = 24) -> list:
    """Splits a viral hook title into 2-3 punchy uppercase magazine cover lines."""
    raw = "".join(ch for ch in (text or "") if ord(ch) < 0x2000 or ch in "’‘“”–—")
    clean = raw.strip()
    if ":" in clean:
        parts = [p.strip() for p in clean.split(":", 1) if p.strip()]
        if len(parts) == 2 and len(parts[1]) >= 10:
            clean = parts[1]
    words = _tr_upper(clean).split()
    lines = []
    cur = []
    for w in words:
        if sum(len(x) for x in cur) + len(cur) + len(w) <= max_chars:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
            if len(lines) == 2:
                break
    if cur and len(lines) < 3:
        lines.append(" ".join(cur))
    return lines[:3] or ["SONBAHAR KAPSÜL", "KOMBİN ÖNERİSİ"]


def generate_hook_cover_photo(
    outfit: dict,
    model_frames: list,
    prepared_items: list,
    out_dir: str,
) -> Image.Image:
    """
    2K QHD+ (1440x2560) çözünürlükte, hem Instagram/TikTok 9:16 tam ekranında hem de
    profil ızgarasında (3:4 ve 1:1 merkez kırpma alanında) yüksek tıklanma oranı (CTR) sağlayan
    Dergi Kapak Kalitesinde 'Viral Hook Kapak Fotoğrafı' (output/hook_cover.jpg) üretir.
    """
    if model_frames:
        base = model_frames[0].copy().convert("RGBA")
    else:
        base = create_watermark_background("@guzelaicom")

    # Üst ve alt sinematik karartma gradyanı (Merkezdeki model yüzünü/kombini açık bırakır, metin okunabilirliğini %100 yapar)
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(grad)
    for y in range(S(380)):
        alpha = int(175 * (1.0 - (y / float(S(380)))) ** 1.4)
        gdraw.line([(0, y), (W, y)], fill=(8, 8, 12, alpha))
    for y in range(H - S(860), H):
        prog = (y - (H - S(860))) / float(S(860))
        alpha = int(225 * (prog ** 1.25))
        gdraw.line([(0, y), (W, y)], fill=(8, 8, 12, alpha))
    base = Image.alpha_composite(base, grad)
    draw = ImageDraw.Draw(base)

    font_kicker = get_font(23, bold=True)
    font_cover_big = get_font(44, bold=True)
    font_cover_sub = get_font(24, bold=True)
    font_mini_price = get_font(20, bold=True)

    # 1) Üst Merkez Tarih & Konsept Rozeti (Profil ızgarası üst sınırının içinde: Y = S(235))
    cal_concept = outfit.get("calendar_concept", {})
    top_tag = (
        outfit.get("video_badge_collage")
        or cal_concept.get("palette_name")
        or "» PINTEREST OLD MONEY SONBAHAR KOMBİNİ «"
    ).replace("🔥", "").replace("✨", "").replace("★", "").strip()
    _draw_auto_pill_badge(
        draw=draw,
        center_x=W // 2,
        center_y=S(235),
        text=top_tag[:44],
        font=font_kicker,
        fill_rgba=(14, 14, 18, 235),
        text_rgba=(242, 218, 178, 255),
        pad_x=S(32),
        pad_y=S(16),
        radius=S(28),
        outline_rgba=(242, 218, 178, 210),
        outline_width=S(2),
    )

    # 2) Sağ Dikey Sütunda 4 Yüzen Mini Kombin Parça Kartı (Görsel + Fiyat Rozeti)
    showcase_keys = ["outerwear", "top", "bottom", "bag"]
    card_w, card_h = S(188), S(205)
    card_x = W - card_w - S(34)
    start_y = S(340)
    gap_y = S(222)

    for idx_c, k_name in enumerate(showcase_keys):
        p_match = next((p for p in prepared_items if p["key"] == k_name), None)
        if not p_match:
            continue
        cy = start_y + idx_c * gap_y
        # Yarı saydam lüks krem kart kutusu
        draw.rounded_rectangle(
            (card_x, cy, card_x + card_w, cy + card_h),
            radius=S(24),
            fill=(252, 250, 246, 238),
            outline=(218, 195, 158, 255),
            width=S(3),
        )
        thumb = p_match["img"].copy()
        thumb.thumbnail((card_w - S(22), card_h - S(56)), Image.Resampling.LANCZOS)
        tx = card_x + (card_w - thumb.width) // 2
        ty = cy + S(8) + (card_h - S(56) - thumb.height) // 2
        base.paste(thumb, (tx, ty), thumb)

        # Fiyat şeridi
        price_txt = p_match["data"].get("price", "")
        draw.rounded_rectangle(
            (card_x + S(12), cy + card_h - S(44), card_x + card_w - S(12), cy + card_h - S(8)),
            radius=S(12),
            fill=(16, 16, 22, 248),
        )
        draw.text(
            (card_x + card_w // 2, cy + card_h - S(26)),
            price_txt,
            fill=(242, 218, 178, 255),
            font=font_mini_price,
            anchor="mm",
        )

    # 3) Alt-Merkez (3:4 ve 1:1 Profil Izgarası Güvenli Alanı: Y = S(1300)..S(1685)) Viral Hook Başlık Kutusu
    hook_lines = _wrap_hook_lines(
        outfit.get("hook_title") or outfit.get("archetype_title") or "OLD MONEY SONBAHAR KOMBİNİ",
        max_chars=22,
    )
    box_top = S(1300)
    box_bot = S(1685)
    draw.rounded_rectangle(
        (S(46), box_top, W - S(46), box_bot),
        radius=S(38),
        fill=(12, 12, 16, 222),
        outline=(242, 218, 178, 225),
        width=S(3),
    )

    # Üst Altın Kicker Etiketi
    total_price_str = outfit.get("total_price_str", "5.519,09₺")
    _draw_auto_pill_badge(
        draw=draw,
        center_x=W // 2,
        center_y=box_top + S(46),
        text=f"» 6 PARÇA DOĞRULANMIŞ KOMBİN • {total_price_str} «",
        font=font_kicker,
        fill_rgba=(188, 142, 78, 255),
        text_rgba=(12, 12, 16, 255),
        pad_x=S(28),
        pad_y=S(12),
        radius=S(20),
    )

    # Ana Büyük Dergi Hook Başlığı (2 veya 3 satır)
    line_start_y = box_top + S(122) if len(hook_lines) == 3 else box_top + S(142)
    line_step = S(62)
    for i_ln, ln_txt in enumerate(hook_lines):
        ly = line_start_y + i_ln * line_step
        draw.text(
            (W // 2, ly),
            ln_txt,
            fill=(255, 255, 255, 255),
            font=font_cover_big,
            anchor="mm",
        )

    # Alt Çağrı (CTA) Bandı
    _draw_auto_pill_badge(
        draw=draw,
        center_x=W // 2,
        center_y=box_bot - S(48),
        text="» TÜM LİNKLER & KODLAR: GUZELAI.COM «",
        font=font_cover_sub,
        fill_rgba=(230, 90, 127, 255),
        text_rgba=(255, 255, 255, 255),
        pad_x=S(30),
        pad_y=S(14),
        radius=S(22),
    )

    rgb_cover = base.convert("RGB")
    cover_jpg_path = os.path.join(out_dir, "hook_cover.jpg")
    cover_png_path = os.path.join(out_dir, "hook_cover.png")
    rgb_cover.save(cover_jpg_path, "JPEG", quality=98, subsampling=0)
    rgb_cover.save(cover_png_path, compress_level=1)
    print(f"🖼️ [Viral Hook Kapak Fotoğrafı]: {cover_jpg_path} (1440x2560 2K QHD+) üretildi.")
    return rgb_cover


def render_kombin_reel(outfit: dict, output_mp4: str, watermark: str = "@guzelaicom") -> dict:
    out_dir = os.path.dirname(output_mp4) or "."
    os.makedirs(out_dir, exist_ok=True)
    bg_base = create_watermark_background(watermark)

    # 6 Kıyafet Parçasının 2K (1440x2560) Çakışmasız Graph Motion Yerleşim ve Zamanlama Tablosu
    # NOT: İlk 0.40sn'de (Frame 0..11) Viral Hook Kapak Fotoğrafı gösterilir, ardından
    # t=0.40sn'de 1. parça zaten ekranda başlar (ASLA boş beyaz kare oluşmaz!).
    items_cfg = [
        {
            "key": "outerwear",
            "target_xy": (S(45), S(205)),
            "target_size": (S(460), S(490)),
            "start_xy": (S(-580), S(140)),
            "start_angle": -18.0,
            "t_in": 0.10,
            "label_xy": (S(275), S(742)),
        },
        {
            "key": "cap",
            "target_xy": (S(490), S(195)),
            "target_size": (S(215), S(115)),
            "start_xy": (S(490), S(-220)),
            "start_angle": 22.0,
            "t_in": 0.65,
            "label_xy": (S(598), S(345)),
        },
        {
            "key": "top",
            "target_xy": (S(645), S(200)),
            "target_size": (S(375), S(395)),
            "start_xy": (S(1180), S(160)),
            "start_angle": 16.0,
            "t_in": 1.20,
            "label_xy": (S(832), S(635)),
        },
        {
            "key": "bottom",
            "target_xy": (S(680), S(695)),
            "target_size": (S(310), S(590)),
            "start_xy": (S(1220), S(750)),
            "start_angle": 10.0,
            "t_in": 1.75,
            "label_xy": (S(835), S(1328)),
        },
        {
            "key": "bag",
            "target_xy": (S(370), S(685)),
            "target_size": (S(265), S(295)),
            "start_xy": (S(370), S(1980)),
            "start_angle": -15.0,
            "t_in": 2.30,
            "label_xy": (S(502), S(1022)),
        },
        {
            "key": "shoes",
            "target_xy": (S(65), S(1060)),
            "target_size": (S(395), S(195)),
            "start_xy": (S(-420), S(1080)),
            "start_angle": 14.0,
            "t_in": 2.85,
            "label_xy": (S(265), S(1305)),
        },
    ]

    # Görselleri 2K çözünürlüğe ölçekle ve Samsung OLED keskinleştirmesi uygula
    prepared_items = []
    for cfg in items_cfg:
        item_data = outfit["items"][cfg["key"]]
        raw_img = load_cutout_image(item_data)
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

    # Dergi Kalitesinde 2K Viral Hook Kapak Fotoğrafını (output/hook_cover.jpg) üret
    hook_cover_rgb = generate_hook_cover_photo(outfit, model_frames, prepared_items, out_dir)
    outfit["hook_cover_path"] = os.path.join(out_dir, "hook_cover.jpg")

    # Tesla + Cadılar Bayramı Eğimli Pist (Sky-Ramp) arka planı ve şeffaf tam boy model dekupe görseli
    ramp_bg_img = None
    ramp_cutout_img = None
    ramp_bg_path = outfit.get("ramp_empty_bg")
    ramp_cutout_path = outfit.get("ramp_model_cutout")
    if ramp_bg_path and os.path.exists(ramp_bg_path):
        ramp_bg_img = Image.open(ramp_bg_path).convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
        ramp_bg_img = enhance_for_samsung_oled(ramp_bg_img, is_cutout=False)
    if ramp_cutout_path and os.path.exists(ramp_cutout_path):
        ramp_cutout_img = Image.open(ramp_cutout_path).convert("RGBA")
        alpha_c = ramp_cutout_img.split()[3]
        bbox_c = alpha_c.point(lambda p: 255 if p > 25 else 0).getbbox()
        if bbox_c:
            ramp_cutout_img = ramp_cutout_img.crop(bbox_c)
        ramp_cutout_img = enhance_for_samsung_oled(ramp_cutout_img, is_cutout=True)

    font_header = get_font(34, bold=True)
    font_brand = get_font(27, bold=True)
    font_price = get_font(25, bold=True)
    font_badge = get_font(30, bold=True)
    font_sub = get_font(23, bold=True)
    font_legal = get_font(18, bold=False)

    # Her bir ürün için görselli ürün link kartı (output/item_card_{key}.jpg) üret
    for p in prepared_items:
        try:
            cw, ch = 800, 1000
            card_bg = Image.new("RGBA", (cw, ch), (249, 247, 243, 255))
            cdraw = ImageDraw.Draw(card_bg)
            cdraw.rounded_rectangle((30, 30, cw - 30, 95), radius=24, fill=(14, 14, 18, 255))
            cdraw.text((cw // 2, 62), f"{p['data'].get('brand', 'MAĞAZA')} • DOĞRULANMIŞ ÜRÜN", fill=(255, 255, 255, 255), font=font_price, anchor="mm")
            p_img = p["img"].copy()
            p_img.thumbnail((580, 580), Image.Resampling.LANCZOS)
            card_bg.paste(p_img, ((cw - p_img.width) // 2, 130 + (580 - p_img.height) // 2), p_img)
            cdraw.rounded_rectangle((35, 735, cw - 35, 965), radius=28, fill=(14, 14, 18, 248))
            p_name = str(p["data"].get("name", ""))[:38]
            cdraw.text((cw // 2, 780), p_name, fill=(255, 255, 255, 255), font=font_sub, anchor="mm")
            cdraw.text((cw // 2, 835), f"FİYAT: {p['data'].get('price', '')}  |  KOD: {p['data'].get('sku', '-')}", fill=(242, 218, 178, 255), font=font_price, anchor="mm")
            cdraw.text((cw // 2, 890), "» Görselli Link: guzelai.com/#kombinler «", fill=(210, 210, 220, 255), font=font_sub, anchor="mm")
            cdraw.text((cw // 2, 935), "Reklam/iş birliği içermez • Kombin önerisidir (zorunlu #reklam)", fill=(165, 165, 175, 255), font=font_legal, anchor="mm")
            card_path = os.path.join(out_dir, f"item_card_{p['key']}.jpg")
            card_bg.convert("RGB").save(card_path, quality=94)
            p["data"]["visual_card_path"] = card_path
        except Exception as ce:
            print(f"[Görsel Ürün Kartı Uyarısı] {p['key']}: {ce}")

    total_duration = 11.0
    total_frames = int(total_duration * FPS)
    collage_end_sec = 5.2

    total_price_str = outfit.get("total_price_str", "2.490₺")
    it_map = outfit["items"]

    def _short_brand(b: str, fallback_label: str) -> str:
        b_clean = (b or "").strip().upper()
        if b_clean in ("GENEL MARKALAR", "TRENDYOL", ""):
            return fallback_label
        return b_clean[:11]

    walk_summary_line = (
        f"{_short_brand(it_map['outerwear']['brand'], 'CEKET')} {it_map['outerwear']['price']} • "
        f"{_short_brand(it_map['top']['brand'], 'TRİKO')} {it_map['top']['price']} • "
        f"{_short_brand(it_map['bottom']['brand'], 'PALAZZO')} {it_map['bottom']['price']} • "
        f"{_short_brand(it_map['shoes']['brand'], 'SNEAKER')} {it_map['shoes']['price']}"
    )

    frames_dir = os.path.join(out_dir, "_frames")
    os.makedirs(frames_dir, exist_ok=True)

    for f_idx in range(total_frames):
        t = f_idx / FPS

        # İLK 0.36 SANİYE (f_idx = 0..10): Viral Hook Kapak Fotoğrafı (Frame 0 ASLA boş beyaz olmaz!)
        if f_idx <= 10:
            zoom_c = 1.0 + 0.018 * (f_idx / 10.0)
            cw_c = int(W / zoom_c)
            ch_c = int(H / zoom_c)
            cx_c = (W - cw_c) // 2
            cy_c = (H - ch_c) // 2
            cover_frame = hook_cover_rgb.crop((cx_c, cy_c, cx_c + cw_c, cy_c + ch_c)).resize((W, H), Image.Resampling.LANCZOS)
            cover_frame.save(os.path.join(frames_dir, f"frame_{f_idx:04d}.jpg"), quality=98, subsampling=0)
            continue

        if t <= collage_end_sec + 0.15:
            canvas = bg_base.copy()
            draw = ImageDraw.Draw(canvas)

            # Üst Başlık Bandı (Otomatik Boyutlanan Kapsül - Taşma Yapmaz)
            header_alpha = 255
            collage_badge = (
                outfit.get("video_badge_collage", "» PINTEREST OLD MONEY SONBAHAR KOMBİNİ «")
                .replace("🔥", "★")
                .replace("✨", "★")
                .replace("🎃", "★")
            )
            _draw_auto_pill_badge(
                draw=draw,
                center_x=W // 2,
                center_y=S(112),
                text=collage_badge,
                font=font_header,
                fill_rgba=(10, 10, 14, header_alpha),
                text_rgba=(255, 255, 255, header_alpha),
                pad_x=S(38),
                pad_y=S(20),
                radius=S(34),
            )

            # 1) Önce tüm kıyafet görsellerini çiz
            active_labels = []
            for idx, p in enumerate(prepared_items):
                dt = (t - p["t_in"]) / 0.62
                if dt <= 0:
                    continue
                prog = ease_out_back(min(1.0, dt))
                float_y = math.sin(t * 3.0 + idx * 1.1) * S(4.0) if dt >= 1.0 else 0.0
                cur_x = int(p["start_xy"][0] + (p["target_xy"][0] - p["start_xy"][0]) * prog)
                cur_y = int(p["start_xy"][1] + (p["target_xy"][1] - p["start_xy"][1]) * prog + float_y)
                cur_angle = p["start_angle"] * (1.0 - min(1.0, dt))

                item_img = p["img"]
                if abs(cur_angle) > 0.3:
                    item_img = item_img.rotate(cur_angle, resample=Image.Resampling.BICUBIC, expand=True)

                canvas.paste(item_img, (cur_x, cur_y), item_img)

                if dt > 0.42:
                    lbl_prog = min(1.0, (dt - 0.42) / 0.38)
                    lx, ly = p["label_xy"]
                    ly_anim = int(ly + (1.0 - lbl_prog) * S(18))
                    active_labels.append((lx, ly_anim, p["data"], p["key"]))

            # 2) Tüm marka ve fiyat etiketlerini yüksek kontrastlı krem/siyah kapsül rozet içinde çiz (kıyafetle asla karışmaz)
            for lx, ly_anim, item_d, item_k in active_labels:
                raw_b = (item_d.get("brand") or "").strip().upper()
                if raw_b == "GENEL MARKALAR":
                    raw_b = "DERİ CEKET" if item_k == "outerwear" else "BUTİK SEÇİM"
                if len(raw_b) > 14:
                    raw_b = raw_b[:13] + "."
                price = item_d["price"]
                pill_w = S(215)
                pill_h = S(68)
                draw.rounded_rectangle(
                    (lx - pill_w // 2, ly_anim - S(22), lx + pill_w // 2, ly_anim - S(22) + pill_h),
                    radius=S(18),
                    fill=(255, 255, 255, 242),
                    outline=(210, 206, 198, 255),
                    width=S(2),
                )
                if raw_b:
                    draw.text((lx, ly_anim - S(2)), raw_b, fill=(14, 14, 18, 255), font=font_brand, anchor="mm")
                    draw.text((lx, ly_anim + S(27)), price, fill=(175, 58, 24, 255), font=font_price, anchor="mm")
                else:
                    draw.text((lx, ly_anim + S(12)), price, fill=(14, 14, 18, 255), font=font_brand, anchor="mm")

            # Alt Toplam Kombin & Link Bilgisi Bandı (True OLED Black)
            if t > 3.55:
                b_prog = ease_out_back(min(1.0, (t - 3.55) / 0.48))
                by = int(S(1720) - b_prog * S(160))
                draw.rounded_rectangle((S(75), by, W - S(75), by + S(142)), radius=S(44), fill=(10, 10, 14, 252))
                draw.text(
                    (W // 2, by + S(36)),
                    f"TOPLAM: {total_price_str} • KAYBOLMADAN KAYDET!",
                    fill=(255, 255, 255, 255),
                    font=font_badge,
                    anchor="mm",
                )
                draw.text(
                    (W // 2, by + S(78)),
                    "» LİNKLER AÇIKLAMADA, YORUMDA & GUZELAI.COM'DA «",
                    fill=(242, 218, 178, 255),
                    font=font_sub,
                    anchor="mm",
                )
                draw.text(
                    (W // 2, by + S(116)),
                    "Reklam / iş birliği içermez • Kombin önerisidir (zorunlu #reklam)",
                    fill=(195, 195, 202, 245),
                    font=font_legal,
                    anchor="mm",
                )

            if abs(t - 4.8) < (0.5 / FPS):
                canvas.convert("RGB").save(os.path.join(out_dir, "kombin_collage.png"), compress_level=1)

        # 2. BÖLÜM: Tesla Eğimli Pist (Sky-Ramp) 3 Aşamalı Fotogerçekçi Graph-Motion Kamera Takibi (5.2sn - 11.0sn)
        # ÇİFT POZLAMA (Image.blend) VE 2B YAPIŞTIRMA HALESİ TAMAMEN KALDIRILDI (%100 DOĞAL SİNEMATİK GEÇİŞ)
        if t >= collage_end_sec:
            walk_t = t - collage_end_sec
            walk_dur = total_duration - collage_end_sec  # 5.8s toplam (5.2s -> 11.0s)

            if len(model_frames) >= 3:
                if walk_t < 1.9:
                    # Aşama 1 (5.2s - 7.1s): Pistin dik üst virajından iniş (Dinamik Graph-Motion dikey kamera takibi)
                    active_model = model_frames[0]
                    local_u = max(0.0, min(1.0, walk_t / 1.9))
                    eased_u = ease_in_out_cubic(local_u)
                    zoom = 1.26 - 0.22 * eased_u
                    crop_w = int(W / zoom)
                    crop_h = int(H / zoom)
                    cx = int((W - crop_w) * (0.54 - 0.04 * eased_u))
                    cy = int((H - crop_h) * (0.18 + 0.32 * eased_u))
                elif walk_t < 3.8:
                    # Aşama 2 (7.1s - 9.0s): Pistin alt virajında güçlü yürüyüş adımı (Yakın plan sinematik takip)
                    active_model = model_frames[1]
                    local_u = max(0.0, min(1.0, (walk_t - 1.9) / 1.9))
                    eased_u = ease_in_out_cubic(local_u)
                    zoom = 1.01 + 0.06 * eased_u
                    crop_w = int(W / zoom)
                    crop_h = int(H / zoom)
                    cx = (W - crop_w) // 2
                    cy = int((H - crop_h) * (0.35 + 0.25 * eased_u))
                else:
                    # Aşama 3 (9.0s - 11.0s): Pist sonu Cadılar Bayramı balkabağı sahnesinde final duruşu ("Detaylar güzelai nokta com'da")
                    active_model = model_frames[2]
                    local_u = max(0.0, min(1.0, (walk_t - 3.8) / 2.0))
                    eased_u = ease_in_out_cubic(local_u)
                    zoom = 1.01 + 0.05 * eased_u
                    crop_w = int(W / zoom)
                    crop_h = int(H / zoom)
                    cx = (W - crop_w) // 2
                    cy = (H - crop_h) // 2

                walk_frame = (
                    active_model.crop((cx, cy, cx + crop_w, cy + crop_h))
                    .resize((W, H), Image.Resampling.LANCZOS)
                    .convert("RGBA")
                )
            elif len(model_frames) > 0:
                idx_m = min(len(model_frames) - 1, int((walk_t / walk_dur) * len(model_frames)))
                active_model = model_frames[idx_m]
                local_u = (walk_t % 1.9) / 1.9
                zoom = 1.01 + 0.045 * ease_in_out_cubic(local_u)
                crop_w = int(W / zoom)
                crop_h = int(H / zoom)
                cx = (W - crop_w) // 2
                cy = (H - crop_h) // 2
                walk_frame = (
                    active_model.crop((cx, cy, cx + crop_w, cy + crop_h))
                    .resize((W, H), Image.Resampling.LANCZOS)
                    .convert("RGBA")
                )
            else:
                walk_frame = bg_base.copy()

            walk_badge = (
                outfit.get("video_badge_walk", "» DÜŞMEDEN PİSTTEN İNİŞ ŞOVU «")
                .replace("🔥", "★")
                .replace("✨", "★")
                .replace("🎃", "★")
            )
            mini_draw = ImageDraw.Draw(walk_frame)
            _draw_auto_pill_badge(
                draw=mini_draw,
                center_x=W // 2,
                center_y=S(122),
                text=walk_badge,
                font=font_badge,
                fill_rgba=(10, 10, 14, 232),
                text_rgba=(255, 255, 255, 255),
                pad_x=S(38),
                pad_y=S(20),
                radius=S(34),
                outline_rgba=(255, 110, 30, 210),
                outline_width=S(2),
            )

            mini_draw.rounded_rectangle(
                (S(48), S(1595), W - S(48), S(1755)),
                radius=S(30),
                fill=(255, 255, 255, 244),
                outline=(25, 25, 30, 255),
                width=S(2),
            )
            mini_draw.text(
                (W // 2, S(1632)),
                walk_summary_line,
                fill=(12, 12, 16, 255),
                font=font_price,
                anchor="mm",
            )
            mini_draw.text(
                (W // 2, S(1680)),
                "» Ürün linkleri açıklamada, ilk yorumda & guzelai.com'da! «",
                fill=(165, 52, 20, 255),
                font=font_sub,
                anchor="mm",
            )
            mini_draw.text(
                (W // 2, S(1724)),
                "Reklam / iş birliği içermez • Kombin önerisidir (zorunlu #reklam)",
                fill=(95, 95, 102, 255),
                font=font_legal,
                anchor="mm",
            )

            if t < collage_end_sec + 0.12:
                tr = (t - collage_end_sec) / 0.12
                final_frame = Image.blend(canvas.convert("RGB"), walk_frame.convert("RGB"), ease_in_out_cubic(tr))
            else:
                final_frame = walk_frame.convert("RGB")
        else:
            final_frame = canvas.convert("RGB")

        # 4:4:4 Tam Chroma (subsampling=0) ve %98 Kalite ile Kayıpsız Ara Kare Kaydı
        final_frame.save(os.path.join(frames_dir, f"frame_{f_idx:04d}.jpg"), quality=98, subsampling=0)

    # Viral Moda / Kombin Reels Çoklu-Enstrüman Müziği + İki Kişilik Doğal Türkçe Sesli Hook Üret
    wav_path = os.path.join(out_dir, "viral_fashion_track.wav")
    pop_times = [c["t_in"] for c in items_cfg]
    music_info = generate_viral_fashion_audio(
        output_wav=wav_path,
        duration=total_duration,
        seed_key=outfit.get("timestamp", "default"),
        item_pop_times=pop_times,
        transition_sec=collage_end_sec,
        outfit=outfit,
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
        "-crf", "14",
        "-b:v", "18M",
        "-maxrate", "24M",
        "-bufsize", "36M",
        "-pix_fmt", "yuv420p",
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-colorspace", "bt709",
        "-color_range", "tv",
        "-movflags", "+faststart",
        "-metadata", "encoder=Apple QuickTime",
        "-metadata", "comment=guzelai.com",
        "-c:a", "aac", "-b:a", "256k", "-ar", "44100", "-ac", "2",
        "-shortest",
        output_mp4,
    ]
    subprocess.run(cmd, check=True)
    print(f"[BAŞARILI] Graph-Motion Master Reels videosu üretildi: {output_mp4}")

    # WhatsApp Kanalı, GuzelAI.com Web Vitrini, Facebook ve X için hızlı yüklenen Evrensel Graph-Motion Video (720x1280)
    gm_short_mp4 = os.path.join(out_dir, "graphmotion_short.mp4")
    cmd_short = [
        ffmpeg_bin, "-y",
        "-i", output_mp4,
        "-vf", "scale=720:1280",
        "-c:v", "libx264",
        "-preset", "fast",
        "-profile:v", "main",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "128k",
        gm_short_mp4,
    ]
    subprocess.run(cmd_short, check=False)
    print(f"[BAŞARILI] Tüm kanallar (WhatsApp & Web dahil) için Kısa Graph-Motion Video hazırlandı: {gm_short_mp4}")
    return music_info
