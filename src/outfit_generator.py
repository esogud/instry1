import os
import re
import json
import random
import hashlib
from io import BytesIO
from datetime import datetime
import requests
from PIL import Image, ImageChops

try:
    from rembg import remove as rembg_remove
    HAS_REMBG = True
except ImportError:
    HAS_REMBG = False


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Canlı Trendyol Kategori Kaynakları (JSON-LD ItemList üzerinden anlık güncel ürün, fiyat, SKU ve link çeker)
LIVE_TRENDYOL_FEEDS = {
    "outerwear": [
        "https://www.trendyol.com/kadin-ceket-x-g1-c1030",
        "https://www.trendyol.com/kadin-trenckot-x-g1-c79",
    ],
    "cap": [
        "https://www.trendyol.com/kadin-gunes-gozlugu-x-g1-c105",
    ],
    "top": [
        "https://www.trendyol.com/kadin-sweatshirt-x-g1-c1179",
        "https://www.trendyol.com/kadin-kazak-x-g1-c1092",
    ],
    "bottom": [
        "https://www.trendyol.com/kadin-pantolon-x-g1-c70",
        "https://www.trendyol.com/kadin-tayt-x-g1-c121",
    ],
    "bag": [
        "https://www.trendyol.com/kadin-omuz-cantasi-x-g1-c101465",
        "https://www.trendyol.com/kadin-canta-x-g1-c117",
    ],
    "shoes": [
        "https://www.trendyol.com/adidas-kadin-sneaker-x-b33-g1-c1172",
        "https://www.trendyol.com/kadin-sneaker-x-g1-c1172",
    ],
}

# Görsel Stil Arketipleri (Her arketip için temiz dekupe kıyafet yedekleri + sokakta yürüyen model kareleri)
OUTFIT_ARCHETYPES = [
    {
        "id": "chic_black_biker_denim",
        "title": "Siyah Ceket & Palazzo Jean Sokak Stili",
        "keywords": {
            "outerwear": ["siyah", "deri", "kaşe", "bomber", "ceket"],
            "cap": ["siyah", "kahve", "oval", "cat", "vintage", "gözlük", "şapka"],
            "top": ["ekru", "krem", "beyaz", "gri", "taş", "sweatshirt", "kazak"],
            "bottom": ["mavi", "buz", "kot", "jean", "palazzo", "antrasit"],
            "bag": ["siyah", "kahve", "baget", "omuz", "deri"],
            "shoes": ["beyaz", "court", "spezial", "retro", "adidas", "sneaker"],
        },
        "cutout_assets": {
            "outerwear": "assets/items/outfit2_01_jacket.png",
            "cap": "assets/items/outfit2_02_cap.png",
            "top": "assets/items/outfit2_03_top.png",
            "bottom": "assets/items/outfit2_04_bottom.png",
            "bag": "assets/items/outfit2_05_bag.png",
            "shoes": "assets/items/outfit2_06_shoes.png",
        },
        "fallback_cutout_assets": {
            "outerwear": "assets/items/01_jacket.png",
            "cap": "assets/items/02_cap.png",
            "top": "assets/items/03_sweatshirt.png",
            "bottom": "assets/items/04_leggings.png",
            "bag": "assets/items/05_bag.png",
            "shoes": "assets/items/06_sneakers.png",
        },
        "model_frames": [
            "assets/outfit2_model_step1.jpg",
            "assets/outfit2_model_step2.jpg",
            "assets/outfit2_model_step3.jpg",
        ],
    },
    {
        "id": "casual_denim_sherpa_grey",
        "title": "Denim Ceket & Gri Athleisure Kombin",
        "keywords": {
            "outerwear": ["mavi", "jean", "kot", "kürklü", "peluş", "bomber", "ceket"],
            "cap": ["lacivert", "gri", "mavi", "siyah", "şapka", "gözlük"],
            "top": ["gri", "füme", "baskılı", "crop", "sweatshirt"],
            "bottom": ["gri", "füme", "antrasit", "tayt", "palazzo", "pantolon"],
            "bag": ["bej", "krem", "vizon", "taba", "omuz"],
            "shoes": ["gri", "beyaz", "yeşil", "sneaker", "spor"],
        },
        "cutout_assets": {
            "outerwear": "assets/items/01_jacket.png",
            "cap": "assets/items/02_cap.png",
            "top": "assets/items/03_sweatshirt.png",
            "bottom": "assets/items/04_leggings.png",
            "bag": "assets/items/05_bag.png",
            "shoes": "assets/items/06_sneakers.png",
        },
        "fallback_cutout_assets": {
            "outerwear": "assets/items/01_jacket.png",
            "cap": "assets/items/02_cap.png",
            "top": "assets/items/03_sweatshirt.png",
            "bottom": "assets/items/04_leggings.png",
            "bag": "assets/items/05_bag.png",
            "shoes": "assets/items/06_sneakers.png",
        },
        "model_frames": [
            "assets/trial1_model_street.jpg",
            "assets/trial1_model_step2.jpg",
            "assets/trial1_model_step3.jpg",
        ],
    },
]


def _format_price_tr(val: float) -> str:
    """Sayısal fiyatı Türkçe para birimi formatına (örn: 1.424,99₺) çevirir."""
    s = f"{val:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    if s.endswith(",00"):
        s = s[:-3]
    return f"{s}₺"


def _clean_product_title(raw_name: str, brand: str) -> str:
    """Uzun e-ticaret başlıklarını şık ve okunaklı kombin açıklamasına kısaltır."""
    name = raw_name.strip()
    if brand and name.lower().startswith(brand.lower()):
        name = name[len(brand):].strip(" -–|")
    name = re.sub(r"\b(KOPYA\s*-\s*|DAR KALIP.*|BİR BEDEN.*|Unisex Erkek/Kadın)\b", "", name, flags=re.I).strip()
    words = name.split()
    if len(words) > 6:
        name = " ".join(words[:6])
    return name or raw_name


def fetch_live_trendyol_items(category_key: str) -> list:
    """Trendyol kategori sayfasındaki JSON-LD verisinden canlı ürünleri, fiyatları ve doğrudan linkleri çeker."""
    urls = LIVE_TRENDYOL_FEEDS.get(category_key, [])
    collected = []
    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                continue
            lds = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', resp.text, re.S)
            for ld in lds:
                if "ItemList" not in ld:
                    continue
                data = json.loads(ld)
                for elem in data.get("itemListElement", []):
                    it = elem.get("item", {})
                    if it.get("@type") != "Product":
                        continue
                    raw_brand = it.get("brand", {}).get("name", "").strip()
                    brand = "" if raw_brand.lower() in ("genel markalar", "diğer") else raw_brand.upper()
                    price_str_raw = str(it.get("offers", {}).get("price", "0"))
                    try:
                        price_val = float(price_str_raw)
                    except ValueError:
                        continue
                    if price_val <= 0:
                        continue
                    prod_url = it.get("url") or it.get("offers", {}).get("url") or ""
                    images = it.get("image") or []
                    if isinstance(images, str):
                        images = [images]
                    if not prod_url or not images:
                        continue
                    clean_name = _clean_product_title(it.get("name", ""), raw_brand)
                    sku = str(it.get("sku") or "")
                    if not sku:
                        m_sku = re.search(r"-p-(\d+)", prod_url)
                        sku = m_sku.group(1) if m_sku else ""
                    collected.append({
                        "id": f"ty_{sku or len(collected)}",
                        "brand": brand or "TRENDYOL",
                        "price": _format_price_tr(price_val),
                        "price_val": price_val,
                        "name": clean_name,
                        "full_name": it.get("name", clean_name),
                        "sku": sku,
                        "product_url": prod_url,
                        "image_url": images[0],
                        "image_urls": images,
                        "color": str(it.get("color") or ""),
                    })
        except Exception as e:
            print(f"[Canlı Ürün Tarama Uyarısı] {category_key} ({url}): {e}")
    return collected


def fetch_live_bagmori_bags() -> list:
    """Bagmori mağazasından canlı çanta ürünlerini, fiyatlarını ve linklerini çeker."""
    collected = []
    try:
        r = requests.get("https://www.bagmori.com/products.json?limit=30", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            for p in r.json().get("products", []):
                variants = p.get("variants") or []
                images = p.get("images") or []
                if not variants or not images:
                    continue
                price_val = float(variants[0].get("price", 0))
                if price_val <= 0:
                    continue
                handle = p.get("handle", "")
                img_srcs = [im.get("src") for im in images if im.get("src")]
                collected.append({
                    "id": f"bagmori_{p.get('id')}",
                    "brand": "BAGMORI",
                    "price": _format_price_tr(price_val),
                    "price_val": price_val,
                    "name": _clean_product_title(p.get("title", ""), "Bagmori"),
                    "full_name": p.get("title", ""),
                    "sku": str(variants[0].get("sku") or p.get("id")),
                    "product_url": f"https://www.bagmori.com/products/{handle}",
                    "image_url": img_srcs[0],
                    "image_urls": img_srcs,
                    "color": "",
                })
    except Exception as e:
        print(f"[Bagmori Canlı Tarama Uyarısı] {e}")
    return collected


def is_clean_white_packshot(img: Image.Image) -> bool:
    """
    Görselin dört kenarının da temiz beyaz stüdyo fonu olup olmadığını kontrol eder.
    İnsan modeli içeren fotoğraflarda baş/bacak kenarlara değdiği için False döner;
    yalnızca tek başına duran ayakkabı/çanta/gözlük/kıyafet dekupe görsellerinde True döner.
    """
    rgb = img.convert("RGB").resize((200, 300))
    px = rgb.load()
    w, h = rgb.size

    def _edge_white_ratio(x_range, y_range):
        total = 0
        white = 0
        for y in y_range:
            for x in x_range:
                r, g, b = px[x, y]
                total += 1
                if r > 236 and g > 236 and b > 236:
                    white += 1
        return white / max(1, total)

    top_r = _edge_white_ratio(range(w), range(0, 22))
    bot_r = _edge_white_ratio(range(w), range(h - 18, h))
    left_r = _edge_white_ratio(range(0, 14), range(h))
    right_r = _edge_white_ratio(range(w - 14, w), range(h))
    return top_r > 0.95 and bot_r > 0.92 and left_r > 0.93 and right_r > 0.93


def _remove_white_bg_and_crop(img: Image.Image) -> Image.Image:
    """Beyaz stüdyo arka planını şeffaflaştırır ve nesnenin etrafındaki boşluğu kırpar."""
    if HAS_REMBG:
        buf = BytesIO()
        img.save(buf, format="PNG")
        out_bytes = rembg_remove(buf.getvalue())
        rgba = Image.open(BytesIO(out_bytes)).convert("RGBA")
    else:
        rgba = img.convert("RGBA")
        datas = rgba.getdata()
        new_data = []
        for r, g, b, a in datas:
            # Çok açık beyaz pikselleri yumuşak geçişle şeffaf yap
            lum = (r + g + b) / 3.0
            spread = max(r, g, b) - min(r, g, b)
            if lum > 244 and spread < 14:
                new_data.append((r, g, b, 0))
            elif lum > 234 and spread < 18:
                alpha = int((244 - lum) / 10.0 * 255)
                new_data.append((r, g, b, max(0, min(255, alpha))))
            else:
                new_data.append((r, g, b, a))
        rgba.putdata(new_data)

    # Şeffaf olmayan alanı (alpha > 20) bulup kenar boşluklarını kırp
    alpha = rgba.split()[3]
    mask = alpha.point(lambda p: 255 if p > 20 else 0)
    bbox = mask.getbbox()
    if bbox:
        rgba = rgba.crop(bbox)
    return rgba


def load_cutout_image(item: dict, use_local_first: bool = True) -> Image.Image:
    """
    1) Önce kombinin yürüyen model sahnesiyle birebir örtüşen temiz stüdyo dekupe görselini ('local_asset') kontrol eder,
    2) Yoksa canlı mağaza ürününün beyaz fonlu stüdyo fotoğrafını indirip arka planını silerek kullanır.
    """
    local_path = item.get("local_asset")
    fallback_path = item.get("fallback_asset")

    if use_local_first and local_path and os.path.exists(local_path):
        im = Image.open(local_path).convert("RGBA")
        alpha = im.split()[3]
        bbox = alpha.point(lambda v: 255 if v > 20 else 0).getbbox()
        return im.crop(bbox) if bbox else im

    candidate_urls = item.get("image_urls") or ([item["image_url"]] if item.get("image_url") else [])
    for url in candidate_urls[:3]:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=12)
            if resp.status_code == 200:
                raw_im = Image.open(BytesIO(resp.content))
                if is_clean_white_packshot(raw_im):
                    cutout = _remove_white_bg_and_crop(raw_im)
                    if cutout.width > 60 and cutout.height > 60:
                        print(f"[Canlı Dekupe] '{item.get('name')}' mağaza görseli dekupe edildi: {url}")
                        return cutout
        except Exception as e:
            print(f"[Canlı Görsel Kontrol] {url}: {e}")

    for p in (local_path, fallback_path):
        if p and os.path.exists(p):
            im = Image.open(p).convert("RGBA")
            alpha = im.split()[3]
            bbox = alpha.point(lambda v: 255 if v > 20 else 0).getbbox()
            return im.crop(bbox) if bbox else im

    raise RuntimeError(f"Ürün görseli yüklenemedi: {item.get('name')}")


def _pick_matching_live_item(candidates: list, keywords: list, rng: random.Random) -> dict:
    """Canlı mağaza ürünleri arasından kombinin renk/stil anahtar kelimelerine en uygun olanı seçer."""
    if not candidates:
        return None
    scored = []
    for c in candidates:
        text = f"{c.get('full_name', '')} {c.get('color', '')} {c.get('brand', '')}".lower()
        score = sum(2 for kw in keywords if kw.lower() in text)
        # Gerçek markalı ürünlere ekstra puan
        if c.get("brand") not in ("", "TRENDYOL", "GENEL MARKALAR"):
            score += 3
        scored.append((score, rng.random(), c))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    top_pool = [x[2] for x in scored[: max(1, min(6, len(scored)))]]
    return rng.choice(top_pool)


def fetch_live_quzu_items(category_key: str) -> list:
    """Quzu mağazasından (ABD sunucularından da erişilebilen canlı JSON) ilgili kategorideki ürünleri çeker."""
    cat_keywords = {
        "outerwear": ["ceket", "trençkot", "kaban", "mont", "blazer"],
        "top": ["kazak", "triko", "sweatshirt", "bluz", "gömlek", "hırka"],
        "bottom": ["pantolon", "jean", "palazzo", "tayt"],
    }
    kws = cat_keywords.get(category_key, [])
    if not kws:
        return []
    collected = []
    try:
        r = requests.get("https://www.quzu.com.tr/products.json?limit=80", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            for p in r.json().get("products", []):
                title = p.get("title", "")
                if not any(k in title.lower() for k in kws):
                    continue
                variants = p.get("variants") or []
                images = p.get("images") or []
                if not variants or not images:
                    continue
                price_val = float(variants[0].get("price", 0))
                if price_val <= 0:
                    continue
                handle = p.get("handle", "")
                img_srcs = [im.get("src") for im in images if im.get("src")]
                collected.append({
                    "id": f"quzu_{p.get('id')}",
                    "brand": "QUZU",
                    "price": _format_price_tr(price_val),
                    "price_val": price_val,
                    "name": _clean_product_title(title, "Quzu"),
                    "full_name": title,
                    "sku": str(variants[0].get("sku") or p.get("id")),
                    "product_url": f"https://www.quzu.com.tr/products/{handle}",
                    "image_url": img_srcs[0],
                    "image_urls": img_srcs,
                    "color": "",
                })
    except Exception as e:
        print(f"[Quzu Canlı Tarama Uyarısı] {e}")
    return collected


def select_daily_outfit(slot_name: str = "otomatik") -> dict:
    """
    Canlı e-ticaret mağazalarından (Trendyol, Quzu, Bagmori vb.) güncel ürünleri, gerçek TL fiyatlarını,
    SKU ürün kodlarını ve doğrudan satın alma linklerini çekerek yeni bir 6'lı kombin oluşturur.
    """
    seed_str = f"{datetime.utcnow().strftime('%Y-%m-%d-%H-%M')}-{slot_name}"
    rng = random.Random(hashlib.md5(seed_str.encode()).hexdigest())

    archetype = OUTFIT_ARCHETYPES[0]
    if not os.path.exists(archetype["model_frames"][0]):
        archetype = OUTFIT_ARCHETYPES[1]
    elif slot_name not in ("deneme", "yeni_kombin"):
        archetype = rng.choice(OUTFIT_ARCHETYPES)

    print(f"[Kombin Motoru] '{archetype['title']}' teması için canlı mağaza linkleri taranıyor...")

    # GitHub Actions ABD sunucularında Trendyol Cloudflare kısıtlamasına takılmamak için
    # önceden taranmış 200+ gerçek Trendyol ürün havuzunu da yükle
    cached_catalog = {}
    if os.path.exists("assets/live_trendyol_catalog.json"):
        try:
            with open("assets/live_trendyol_catalog.json", "r", encoding="utf-8") as f:
                cached_catalog = json.load(f)
        except Exception:
            cached_catalog = {}

    items = {}
    total_price = 0.0

    for cat_key in ["outerwear", "cap", "top", "bottom", "bag", "shoes"]:
        live_pool = fetch_live_trendyol_items(cat_key)
        if cat_key == "bag":
            live_pool = fetch_live_bagmori_bags() + live_pool
        elif cat_key in ("outerwear", "top", "bottom"):
            live_pool = live_pool + fetch_live_quzu_items(cat_key)

        if cached_catalog.get(cat_key):
            live_pool = live_pool + cached_catalog[cat_key]

        chosen = _pick_matching_live_item(live_pool, archetype["keywords"].get(cat_key, []), rng)
        if not chosen:
            chosen = {
                "id": f"fallback_{cat_key}",
                "brand": "ZARA",
                "price": "890₺",
                "price_val": 890.0,
                "name": f"Yeni Sezon {cat_key.title()}",
                "full_name": f"Yeni Sezon {cat_key.title()}",
                "sku": "202601",
                "product_url": "https://www.trendyol.com/butik/liste/1/kadin",
                "image_url": "",
                "image_urls": [],
            }

        chosen["local_asset"] = archetype["cutout_assets"].get(cat_key)
        chosen["fallback_asset"] = archetype["fallback_cutout_assets"].get(cat_key)
        items[cat_key] = chosen
        total_price += float(chosen.get("price_val", 0.0))
        print(
            f"  ✓ [{cat_key.upper()}] {chosen['brand']} - {chosen['name']} ({chosen['price']}) "
            f"-> {chosen['product_url']}"
        )

    total_price_str = _format_price_tr(total_price)

    return {
        "slot": slot_name,
        "is_trial": False,
        "archetype_id": archetype["id"],
        "archetype_title": archetype["title"],
        "timestamp": datetime.utcnow().isoformat(),
        "items": items,
        "total_price_val": total_price,
        "total_price_str": total_price_str,
        "model_frames": archetype["model_frames"],
    }
