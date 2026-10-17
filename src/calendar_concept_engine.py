"""
Date-Aware Calendar Concept & Pinterest "Old Money / Quiet Luxury" Color Harmony Engine
---------------------------------------------------------------------------------------
1. Automatically detects the active date, month, season, day-of-week, and special calendar
   events (e.g., Mid-October Old Money Autumn Elegance, Oct 29 Republic Day, Halloween,
   November Trench/Wool Coat Capsule, New Year, Valentine's Day, Spring/Summer Linen).
2. Provides curated Pinterest high-save ("Çok Kaydedilen") Old Money color palettes so every
   new post has a distinct, ultra-elegant color story.
3. Scores and filters online e-commerce products (Trendyol / Bagmori) according to the active
   date concept, season, and Pinterest Old Money color harmony.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional


PINTEREST_OLD_MONEY_PALETTES: List[Dict[str, Any]] = [
    {
        "palette_id": "pinterest_camel_iceblue_ecru_tan",
        "palette_name": "Pinterest Old Money: Camel & Buz Mavisi & Ekru & Taba Zarafeti",
        "inspiration": "Pinterest 2026 Sonbahar En Çok Kaydedilen 'Quiet Luxury / Milano & Nişantaşı' Renk Kurgusu",
        "slot_colors": {
            "outerwear": ["camel", "bej", "vizon", "taba", "kahve", "trençkot", "kaşe", "kaban"],
            "top": ["mavi", "buz mavisi", "bebe mavisi", "çizgili", "ekru", "beyaz", "gömlek", "triko"],
            "bottom": ["ekru", "krem", "bej", "taş", "fildişi", "palazzo", "kumaş pantolon"],
            "bag": ["taba", "kahve", "vizon", "camel", "krem", "tokalı", "deri"],
            "shoes": ["taba", "kahve", "bej", "krem", "loafer", "topuklu", "babet", "süet"],
            "cap": ["kahve", "gold", "altın", "kemik", "oval", "gözlük"],
        },
        "style_pillars": [
            "Camel / Vizon Trençkot veya Kaşe Kaban",
            "Mavi-Beyaz Çizgili Oxford Gömlek",
            "Ekru / Krem Yüksek Bel Pileli Palazzo Kumaş Pantolon",
            "Taba / Kahve Gold Tokalı Deri Çanta & Loafer/Stiletto",
        ],
    },
    {
        "palette_id": "pinterest_champagne_chocolate_gold",
        "palette_name": "Pinterest Old Money: Şampanya Saten & Çikolata Kahve & Gold Zarafeti",
        "inspiration": "Pinterest 'Quiet Luxury Evening & Autumn Chic' En Çok Kaydedilen Sıcak Ton Kurgusu",
        "slot_colors": {
            "outerwear": ["kahve", "çikolata", "camel", "bej", "kaşe", "blazer"],
            "top": ["şampanya", "ekru", "krem", "saten", "ipek", "gömlek", "bluz"],
            "bottom": ["kahve", "çikolata", "acı kahve", "pileli", "palazzo"],
            "bag": ["krem", "ekru", "bej", "gold", "el çantası"],
            "shoes": ["krem", "bej", "taba", "stiletto", "loafer"],
            "cap": ["gold", "altın", "kahve", "saat", "küpe", "gözlük"],
        },
        "style_pillars": [
            "Şampanya / Ekru Saten Gömlek",
            "Çikolata Kahve Yüksek Bel Pileli Palazzo Pantolon",
            "Krem Gold Tokalı El Çantası & Stiletto",
        ],
    },
    {
        "palette_id": "pinterest_olive_camel_cream",
        "palette_name": "Pinterest Old Money: Zeytin Yeşili (Haki) & Ekru & Camel Sonbahar Kurgusu",
        "inspiration": "Pinterest 'Heritage Countryside & City Old Money' Toprak Tonları Kurgusu",
        "slot_colors": {
            "outerwear": ["haki", "zeytin", "yeşil", "süet", "kaşe", "ceket", "trençkot"],
            "top": ["ekru", "krem", "bej", "triko", "kazak", "gömlek"],
            "bottom": ["ekru", "krem", "antrasit", "bej", "palazzo"],
            "bag": ["kahve", "taba", "siyah", "deri"],
            "shoes": ["beyaz", "krem", "taba", "loafer", "sneaker"],
            "cap": ["kahve", "siyah", "gold", "oval", "gözlük"],
        },
        "style_pillars": [
            "Haki / Zeytin Yeşili Süet veya Kaşe Ceket",
            "Ekru Yumuşak Dokulu Triko Kazak",
            "Yüksek Bel Kemerli Palazzo Pantolon",
        ],
    },
    {
        "palette_id": "pinterest_burgundy_chocolate_anthracite",
        "palette_name": "Pinterest Sonbahar Kapsül: Koyu Kahve Peluş & Bordo & Antrasit",
        "inspiration": "Pinterest 'Autumn Street Editorial' Bordo & Kahve Kontrast Kurgusu",
        "slot_colors": {
            "outerwear": ["kahve", "peluş", "deri", "mont", "kaban"],
            "top": ["bordo", "şarap", "triko", "kazak"],
            "bottom": ["antrasit", "füme", "gri", "palazzo"],
            "bag": ["siyah", "kahve", "bordo", "deri"],
            "shoes": ["bordo", "siyah", "süet", "sneaker", "loafer"],
            "cap": ["siyah", "kahve", "vogue", "gözlük"],
        },
        "style_pillars": [
            "Koyu Kahve İçi Peluş Deri Mont",
            "Bordo Fitilli Triko Kazak",
            "Kemerli Antrasit Palazzo Pantolon",
        ],
    },
]

OLD_MONEY_QUALITY_KEYWORDS = [
    "kaşe",
    "trençkot",
    "kaban",
    "blazer",
    "tüvit",
    "süet",
    "ipek",
    "saten",
    "oxford",
    "çizgili",
    "poplin",
    "kaşmir",
    "triko",
    "pileli",
    "palazzo",
    "kumaş pantolon",
    "yüksek bel",
    "kemerli",
    "loafer",
    "stiletto",
    "babet",
    "tokalı",
    "deri",
    "gold",
    "incili",
    "vogue",
]

MONTH_NAMES_TR = {
    1: "Ocak",
    2: "Şubat",
    3: "Mart",
    4: "Nisan",
    5: "Mayıs",
    6: "Haziran",
    7: "Temmuz",
    8: "Ağustos",
    9: "Eylül",
    10: "Ekim",
    11: "Kasım",
    12: "Aralık",
}

WEEKDAY_NAMES_TR = {
    0: "Pazartesi",
    1: "Salı",
    2: "Çarşamba",
    3: "Perşembe",
    4: "Cuma",
    5: "Cumartesi",
    6: "Pazar",
}


def get_active_calendar_concept(now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Determines the exact seasonal, cultural, and day-of-week fashion concept
    for the current date, along with the recommended Pinterest Old Money palette.
    """
    dt = now or datetime.now()
    month = dt.month
    day = dt.day
    weekday = dt.weekday()
    month_tr = MONTH_NAMES_TR.get(month, "Ekim")
    weekday_tr = WEEKDAY_NAMES_TR.get(weekday, "Cumartesi")
    date_label_tr = f"{day} {month_tr} {dt.year} {weekday_tr}"

    # 1. Mevsim Tespiti
    if month in (9, 10, 11):
        season = "Sonbahar"
        season_fabrics = ["trençkot", "kaşe", "triko", "oxford gömlek", "süet", "palazzo", "loafer"]
    elif month in (12, 1, 2):
        season = "Kış"
        season_fabrics = ["kaşe kaban", "manto", "peluş", "yün kazak", "balıkçı yaka", "çizme", "deri"]
    elif month in (3, 4, 5):
        season = "İlkbahar"
        season_fabrics = ["trençkot", "blazer", "tüvit", "gömlek", "kumaş pantolon", "loafer", "babet"]
    else:
        season = "Yaz"
        season_fabrics = ["keten", "ipek", "saten", "elbise", "yelek", "sandalet", "espadril"]

    # 2. Haftanın Günü Ruhu
    if weekday in (5, 6):
        day_mood = f"{weekday_tr} Hafta Sonu Old Money Zarafeti & Şehir Yürüyüşü"
    elif weekday == 4:
        day_mood = "Cuma Prestiji & Akşamüstü Zarafeti"
    else:
        day_mood = f"{weekday_tr} Şehir & Ofis Old Money Zarafeti"

    # 3. Tarihe Özel Konsept & Önerilen Arketip / Renk Kurgusu
    special_event = None
    preferred_archetype_id = "pinterest_oldmoney_camel_iceblue_ecru"
    preferred_palette = PINTEREST_OLD_MONEY_PALETTES[0]

    if month == 10 and day == 29:
        special_event = "29 Ekim Cumhuriyet Bayramı Özel Zarafet & Şıklık Konsepti"
    elif month == 10 and 25 <= day <= 31:
        special_event = "Ekim Sonu & Cadılar Bayramı (Halloween) Old Money Gece Şıklığı"
    elif month == 10:
        special_event = f"{day} Ekim Altın Sonbahar & Pinterest 'Old Money / Quiet Luxury' Hafta Sonu Zarafeti"
        preferred_archetype_id = "pinterest_oldmoney_camel_iceblue_ecru"
        preferred_palette = PINTEREST_OLD_MONEY_PALETTES[0]
    elif month == 11:
        special_event = f"{day} Kasım Sonbahar Kapsül Gardırop & Trençkot/Kaşe Kaban Zamanı"
        preferred_archetype_id = "pinterest_oldmoney_camel_iceblue_ecru"
    elif month == 12 and day >= 20:
        special_event = "Yılbaşı (New Year) Işıltılı Old Money Davet & Kış Zarafeti"
    elif month == 2 and 10 <= day <= 14:
        special_event = "14 Şubat Sevgililer Günü Romantik Old Money Zarafeti"
    elif month == 3 and day == 8:
        special_event = "8 Mart Dünya Kadınlar Günü Özel Zarafet & Güçlü Stil Konsepti"
    else:
        special_event = f"{date_label_tr} • {season} Old Money & Quiet Luxury Kombin Kurgusu"

    return {
        "date_iso": dt.strftime("%Y-%m-%d"),
        "date_label_tr": date_label_tr,
        "season": season,
        "weekday_tr": weekday_tr,
        "day_mood": day_mood,
        "concept_title": special_event,
        "season_fabrics": season_fabrics,
        "preferred_archetype_id": preferred_archetype_id,
        "pinterest_palette": preferred_palette,
    }


def score_online_item_for_concept(
    item: Dict[str, Any],
    slot_key: str,
    concept: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Scores an online store product (Trendyol / Bagmori) according to:
    1. Active Pinterest Old Money Color Palette for `slot_key`
    2. Old Money / Quiet Luxury fabric & tailoring keywords
    3. Active Date & Season appropriateness
    """
    active = concept or get_active_calendar_concept()
    palette = active.get("pinterest_palette") or PINTEREST_OLD_MONEY_PALETTES[0]
    slot_keywords = palette.get("slot_colors", {}).get(slot_key, [])
    season_fabrics = active.get("season_fabrics", [])

    haystack = f"{item.get('name', '')} {item.get('full_name', '')} {item.get('color', '')} {item.get('brand', '')}".lower()
    score = 0

    for kw in slot_keywords:
        if kw.lower() in haystack:
            score += 4

    for om_kw in OLD_MONEY_QUALITY_KEYWORDS:
        if om_kw.lower() in haystack:
            score += 2

    for sf in season_fabrics:
        if sf.lower() in haystack:
            score += 2

    return score
