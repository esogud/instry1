import os
import random
import hashlib
from io import BytesIO
from datetime import datetime
import requests
from PIL import Image

try:
    from rembg import remove as rembg_remove
    HAS_REMBG = True
except ImportError:
    HAS_REMBG = False


CATALOG = {
    "outerwear": [
        {
            "id": "hm_sherpa_denim",
            "brand": "H&M",
            "price": "379₺",
            "name": "Kürk Yakalı Açık Mavi Jean Ceket",
            "prompt_desc": "light-wash blue oversized denim jacket with a cream sherpa fleece shawl collar worn open",
            "local_asset": "assets/items/01_jacket.png",
            "image_url": "https://images.unsplash.com/photo-1544441893-675973e31985?w=800&q=80"
        },
        {
            "id": "zara_biker_leather",
            "brand": "ZARA",
            "price": "1.290₺",
            "name": "Oversize Siyah Deri Biker Ceket",
            "prompt_desc": "oversized black faux-leather moto biker jacket with silver zippers worn open",
            "local_asset": "assets/items/01_jacket.png",
            "image_url": "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=800&q=80"
        },
        {
            "id": "bershka_trench_beige",
            "brand": "BERSHKA",
            "price": "1.450₺",
            "name": "Kemerli Bej Crop Trençkot",
            "prompt_desc": "stylish beige cropped trench coat worn open over street outfit",
            "local_asset": "assets/items/01_jacket.png",
            "image_url": "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=800&q=80"
        }
    ],
    "cap": [
        {
            "id": "ucla_cap_blue_grey",
            "brand": "UCLA",
            "price": "59,97₺",
            "name": "UCLA Nakışlı Çift Renk Kep Şapka",
            "prompt_desc": "two-tone light grey and navy blue baseball cap with UCLA varsity lettering",
            "local_asset": "assets/items/02_cap.png",
            "image_url": "https://images.unsplash.com/photo-1588850561407-ed78c282e89b?w=600&q=80"
        },
        {
            "id": "ny_cap_beige",
            "brand": "NEW ERA",
            "price": "499₺",
            "name": "Ekru NY Nakışlı Baseball Şapka",
            "prompt_desc": "cream beige baseball cap with minimal varsity embroidery",
            "local_asset": "assets/items/02_cap.png",
            "image_url": "https://images.unsplash.com/photo-1576871337622-98d48d1cf531?w=600&q=80"
        }
    ],
    "top": [
        {
            "id": "fifty_grey_crop_sweat",
            "brand": "",
            "price": "279₺",
            "name": "Gri 'fifty' Nakışlı Crop Sweatshirt",
            "prompt_desc": "heather-grey cropped crewneck sweatshirt with subtle black script lettering on the chest",
            "local_asset": "assets/items/03_sweatshirt.png",
            "image_url": "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=800&q=80"
        },
        {
            "id": "pullandbear_white_rib_top",
            "brand": "PULL&BEAR",
            "price": "349₺",
            "name": "Fitilli Beyaz Uzun Kollu Crop Top",
            "prompt_desc": "fitted white ribbed cropped long-sleeve top",
            "local_asset": "assets/items/03_sweatshirt.png",
            "image_url": "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=800&q=80"
        }
    ],
    "bottom": [
        {
            "id": "zara_grey_rib_leggings",
            "brand": "ZARA",
            "price": "139,95₺",
            "name": "Yüksek Bel Fitilli Gri Tayt Pantolon",
            "prompt_desc": "high-waisted heather-grey ribbed fitted flare leggings",
            "local_asset": "assets/items/04_leggings.png",
            "image_url": "https://images.unsplash.com/photo-1506629082955-511b1aa562c8?w=800&q=80"
        },
        {
            "id": "stradivarius_wide_jean",
            "brand": "STRADIVARIUS",
            "price": "890₺",
            "name": "Yüksek Bel Açık Mavi Wide Leg Jean",
            "prompt_desc": "high-waisted light blue wide-leg baggy denim jeans",
            "local_asset": "assets/items/04_leggings.png",
            "image_url": "https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=800&q=80"
        }
    ],
    "bag": [
        {
            "id": "housebags_beige_baguette",
            "brand": "HOUSEBAGS",
            "price": "55,24₺",
            "name": "Bej Minimal Baget Omuz Çantası",
            "prompt_desc": "small beige minimal nylon baguette shoulder bag held on her arm",
            "local_asset": "assets/items/05_bag.png",
            "image_url": "https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=600&q=80"
        },
        {
            "id": "mango_black_shoulder_bag",
            "brand": "MANGO",
            "price": "699,99₺",
            "name": "Tokalı Siyah Mini Omuz Çantası",
            "prompt_desc": "sleek mini black leather baguette shoulder bag",
            "local_asset": "assets/items/05_bag.png",
            "image_url": "https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=600&q=80"
        }
    ],
    "shoes": [
        {
            "id": "nb_997h_grey_mint",
            "brand": "NEW BALANCE",
            "price": "469,99₺",
            "name": "Gri & Mint Yeşili 997H Sneaker",
            "prompt_desc": "grey and white New Balance retro running sneakers with pastel mint-green accents",
            "local_asset": "assets/items/06_sneakers.png",
            "image_url": "https://images.unsplash.com/photo-1539185441755-769473a23570?w=700&q=80"
        },
        {
            "id": "adidas_samba_white",
            "brand": "ADIDAS",
            "price": "3.499₺",
            "name": "Beyaz & Gri Çizgili Retro Sneaker",
            "prompt_desc": "classic white leather low-top retro sneakers with grey suede toe",
            "local_asset": "assets/items/06_sneakers.png",
            "image_url": "https://images.unsplash.com/photo-1560769629-975ec94e6a86?w=700&q=80"
        }
    ]
}


def load_cutout_image(item: dict, use_local_first: bool = True) -> Image.Image:
    """Önce yerel şeffaf PNG kesimini kontrol eder, yoksa indirip rembg ile arka planı siler."""
    local_path = item.get("local_asset")
    if use_local_first and local_path and os.path.exists(local_path):
        return Image.open(local_path).convert("RGBA")

    url = item.get("image_url")
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        img_bytes = resp.content
        if HAS_REMBG:
            cutout_bytes = rembg_remove(img_bytes)
            return Image.open(BytesIO(cutout_bytes)).convert("RGBA")
        return Image.open(BytesIO(img_bytes)).convert("RGBA")
    except Exception as e:
        print(f"[Görsel İndirme Yedek] {e}, yerel şeffaf görsel kullanılıyor.")
        if local_path and os.path.exists(local_path):
            return Image.open(local_path).convert("RGBA")
        raise


def select_daily_outfit(slot_name: str = "otomatik") -> dict:
    """
    İlk denemede ('deneme') referans görseldeki birebir kombini seçer.
    Günlük otomatik çalışmalarda (10:00, 15:00, 20:00) tarih ve saate göre farklı kombin oluşturur.
    """
    is_trial = (slot_name == "deneme")
    if is_trial:
        items = {
            "outerwear": CATALOG["outerwear"][0],
            "cap": CATALOG["cap"][0],
            "top": CATALOG["top"][0],
            "bottom": CATALOG["bottom"][0],
            "bag": CATALOG["bag"][0],
            "shoes": CATALOG["shoes"][0],
        }
    else:
        seed_str = f"{datetime.utcnow().strftime('%Y-%m-%d-%H')}-{slot_name}"
        rng = random.Random(hashlib.md5(seed_str.encode()).hexdigest())
        items = {k: rng.choice(v) for k, v in CATALOG.items()}

    prompt = (
        "Full-body vertical 9:16 candid street style fashion photograph (head to toe including shoes on the sidewalk) "
        "of a gorgeous young female fashion model walking confidently towards the camera on a trendy city street "
        "with soft natural daylight and shallow depth of field. She is wearing: "
        f"1) {items['outerwear']['prompt_desc']}, "
        f"2) {items['top']['prompt_desc']}, "
        f"3) {items['bottom']['prompt_desc']}, "
        f"4) {items['cap']['prompt_desc']}, "
        f"5) {items['bag']['prompt_desc']}, "
        f"6) {items['shoes']['prompt_desc']}. "
        "Photorealistic 85mm street fashion photography, natural walking stride."
    )

    return {
        "slot": slot_name,
        "is_trial": is_trial,
        "timestamp": datetime.utcnow().isoformat(),
        "items": items,
        "model_prompt": prompt
    }
