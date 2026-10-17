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
        "id": "veor_uranis_bordo_kapsul_2k",
        "preferred_music_id": "veor_uranis_da_da_da_2026",
        "title": "Sokağa çıkarken herkesin dönüp baktığı o bordo & antrasit kapsül kombin 🔥✨",
        "spoken_hook_text": "Sokağa çıkarken herkesin dönüp baktığı o kusursuz sonbahar kombinim!",
        "viral_hook": "🛑 İçi peluş kemerli deri mont, bordo fitilli triko kazak, yüksek bel kemerli antrasit palazzo pantolon ve bordo Adidas Handball Spezial uyumu! Önce guzelai.com'da görselleri ve renkleri tek tek doğrulanmış 6 kadın parçası! 👇🔥",
        "seo_note": "📌 Not: Videodaki %100 Kadın kombin parçaları önce guzelai.com vitrininde görsel/renk/stok kontrolünden geçirilmiş olup aşağıdaki guzelai.com/go linklerinden doğrudan ilgili mağaza sayfasına yönlenir:",
        "verified_exact_items": {
            "outerwear": {
                "id": "ty_1099303505",
                "category_label": "Mont & Ceket",
                "brand": "TRENDYOL KOLEKSİYON",
                "price": "1.399₺",
                "price_val": 1399.0,
                "name": "İçi Peluş Detaylı Kemerli Koyu Kahve Deri Mont & Ceket",
                "full_name": "Kadın İçi Peluş (Shearling) Detaylı Kemerli Koyu Kahve Deri Mont & Ceket",
                "sku": "1099303505",
                "color": "Kahve / Krem Peluş",
                "store_url": "https://www.trendyol.com/genel-markalar/ici-pelus-detayli-kemerli-deri-ceket-p-1099303505",
                "product_url": "https://guzelai.com/go/1099303505",
                "guzelai_url": "https://guzelai.com/go/1099303505",
                "image_url": "https://cdn.dsmcdn.com/ty1799/prod/QC_PREP/20251208/17/87612bea-c651-3510-86e1-9223384152ea/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1799/prod/QC_PREP/20251208/17/87612bea-c651-3510-86e1-9223384152ea/1_org_zoom.jpg"],
            },
            "cap": {
                "id": "ty_835985416",
                "category_label": "Gözlük & Aksesuar",
                "brand": "VOGUE EYEWEAR",
                "price": "2.150₺",
                "price_val": 2150.0,
                "name": "Vogue VO5586S W44 87 53 Siyah Kadın Güneş Gözlüğü",
                "full_name": "Vogue VO5586S W44 87 53 Siyah Çerçeveli Kadın Güneş Gözlüğü",
                "sku": "835985416",
                "color": "Siyah",
                "store_url": "https://www.trendyol.com/vogue/vo5586s-w44-87-53-kadin-gunes-gozlugu-p-835985416",
                "product_url": "https://guzelai.com/go/835985416",
                "guzelai_url": "https://guzelai.com/go/835985416",
                "image_url": "https://cdn.dsmcdn.com/ty1740/prod/QC_ENRICHMENT/20250901/13/0df06205-e313-38d9-9c4f-16867a222bf1/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1740/prod/QC_ENRICHMENT/20250901/13/0df06205-e313-38d9-9c4f-16867a222bf1/1_org_zoom.jpg"],
            },
            "top": {
                "id": "ty_903567167",
                "category_label": "Kazak & Triko",
                "brand": "MODASPARK",
                "price": "309,05₺",
                "price_val": 309.05,
                "name": "Kadın Bordo Bisiklet Yaka Fitilli Oversize Triko Kazak",
                "full_name": "MODASPARK Bordo Bisiklet Yaka Fitilli Oversize Kadın Triko Kazak",
                "sku": "903567167",
                "color": "Bordo",
                "store_url": "https://www.trendyol.com/modaspark/bordo-bisiklet-yaka-oversize-kadin-triko-kazak-p-903567167",
                "product_url": "https://guzelai.com/go/903567167",
                "guzelai_url": "https://guzelai.com/go/903567167",
                "image_url": "https://cdn.dsmcdn.com/ty1632/prod/QC/20250202/15/9830164e-8f57-3365-952e-d77fd145269c/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1632/prod/QC/20250202/15/9830164e-8f57-3365-952e-d77fd145269c/1_org_zoom.jpg"],
            },
            "bottom": {
                "id": "ty_866458994",
                "category_label": "Pantolon",
                "brand": "RITNICE",
                "price": "789₺",
                "price_val": 789.0,
                "name": "Kadın Rena Kemerli Likralı Yüksek Bel Antrasit Palazzo Pantolon",
                "full_name": "Ritnice Kadın Rena Kemerli Likralı Yüksek Bel Pileli Antrasit Palazzo Pantolon",
                "sku": "866458994",
                "color": "Antrasit",
                "store_url": "https://www.trendyol.com/ritnice/kadin-rena-kemerli-likrali-antrasit-palazzo-pantolon-p-866458994",
                "product_url": "https://guzelai.com/go/866458994",
                "guzelai_url": "https://guzelai.com/go/866458994",
                "image_url": "https://cdn.dsmcdn.com/ty1590/prod/QC/20241023/12/4dc22706-3140-3522-8f6d-be4bc517e649/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1590/prod/QC/20241023/12/4dc22706-3140-3522-8f6d-be4bc517e649/1_org_zoom.jpg"],
            },
            "bag": {
                "id": "bagmori_8682166106158",
                "category_label": "Çanta",
                "brand": "BAGMORI",
                "price": "799,90₺",
                "price_val": 799.90,
                "name": "Siyah Kemer Toka Aksesuarlı Deri El & Omuz Çantası",
                "full_name": "Bagmori Siyah Kemer Toka Aksesuarlı Askılı Kadın Deri Çanta",
                "sku": "8682166106158",
                "color": "Siyah",
                "store_url": "https://www.bagmori.com/products/siyah-aksesuarli-askili-mini-canta",
                "product_url": "https://guzelai.com/go/8682166106158",
                "guzelai_url": "https://guzelai.com/go/8682166106158",
                "image_url": "https://cdn.shopify.com/s/files/1/0023/2138/3537/files/8682166106158-1_e433841d-5e61-4178-b279-b69075a8dec9.jpg?v=1784880657",
                "image_urls": ["https://cdn.shopify.com/s/files/1/0023/2138/3537/files/8682166106158-1_e433841d-5e61-4178-b279-b69075a8dec9.jpg?v=1784880657"],
            },
            "shoes": {
                "id": "ty_994497307",
                "category_label": "Ayakkabı",
                "brand": "ADIDAS",
                "price": "4.499,40₺",
                "price_val": 4499.40,
                "name": "Adidas Handball Spezial Kadın Bordo Süet Sneaker",
                "full_name": "adidas Handball Spezial Kadın Bordo Süet Sneaker Spor Ayakkabı",
                "sku": "994497307",
                "color": "Bordo / Beyaz / Gum",
                "store_url": "https://www.trendyol.com/adidas/handball-spezial-kadin-bordo-ayakkabi-p-994497307",
                "product_url": "https://guzelai.com/go/994497307",
                "guzelai_url": "https://guzelai.com/go/994497307",
                "image_url": "https://cdn.dsmcdn.com/ty1773/prod/QC_PREP/20251015/15/79e6780b-45ee-3203-93e2-d72ac87fab56/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1773/prod/QC_PREP/20251015/15/79e6780b-45ee-3203-93e2-d72ac87fab56/1_org_zoom.jpg"],
            },
        },
        "keywords": {
            "outerwear": ["peluş", "deri", "kemerli", "kadın", "mont", "ceket"],
            "cap": ["vogue", "siyah", "kadın", "gözlük"],
            "top": ["bordo", "fitilli", "oversize", "kadın", "kazak", "triko"],
            "bottom": ["antrasit", "kemerli", "pileli", "palazzo", "kadın", "pantolon"],
            "bag": ["siyah", "deri", "kemer", "kadın", "çanta"],
            "shoes": ["spezial", "adidas", "bordo", "kadın", "sneaker"],
        },
        "cutout_assets": {
            "outerwear": "assets/items/veor_01_jacket.png",
            "cap": "assets/items/veor_02_cap.png",
            "top": "assets/items/veor_03_top.png",
            "bottom": "assets/items/veor_04_bottom.png",
            "bag": "assets/items/veor_05_bag.png",
            "shoes": "assets/items/veor_06_shoes.png",
        },
        "fallback_cutout_assets": {
            "outerwear": "assets/items/veor_01_jacket.png",
            "cap": "assets/items/veor_02_cap.png",
            "top": "assets/items/veor_03_top.png",
            "bottom": "assets/items/veor_04_bottom.png",
            "bag": "assets/items/veor_05_bag.png",
            "shoes": "assets/items/veor_06_shoes.png",
        },
        "model_frames": [
            "assets/veor_model_step1.jpg",
            "assets/veor_model_step2.jpg",
            "assets/veor_model_step3.jpg",
        ],
    },
    {
        "id": "tesla_halloween_ramp_curly",
        "title": "Tesla'nın dik pistinden bile düşmeden indiren o Cadılar Bayramı kombini 🎃🔥✨",
        "spoken_hook_text": "Cadılar Bayramı gecesi bu dik pistten bile düşmeden kombinimle iniyorum!",
        "viral_hook": "🛑 Kahvelerin ve pizzaların bile uçmadan indiği o meşhur dik pistte Cadılar Bayramı şovumuz! Siyah oversize deri ceket, bordo triko kazak ve antrasit palazzo pantolonla yerçekimine meydan okuyan 6 kadın parçası! 👇🎃🔥",
        "seo_note": "📌 Not: Videodaki %100 Kadın kombin parçaları önce guzelai.com vitrininde doğrulanmış olup aşağıdaki guzelai.com/go linklerinden mağazaya yönlenir:",
        "ramp_empty_bg": "assets/tesla_halloween_empty_ramp.jpg",
        "ramp_model_cutout": "assets/tesla_ramp_model_cutout.png",
        "verified_exact_items": {
            "outerwear": {
                "id": "ty_1075561987",
                "brand": "GENEL MARKALAR",
                "price": "850₺",
                "price_val": 850.0,
                "name": "Kadın Oversize Deri Ceket – Kemer Detaylı Siyah Ceket",
                "full_name": "Genel Markalar Kadın Oversize Deri Ceket – Fermuarlı Kemer Detaylı Siyah Kadın Ceket",
                "sku": "1075561987",
                "color": "Siyah",
                "store_url": "https://www.trendyol.com/genel-markalar/kadin-oversize-deri-ceket-oversize-relax-fit-fermuarli-kemer-detayli-gunluk-kadin-ceket-p-1075561987",
                "product_url": "https://guzelai.com/go/1075561987",
                "image_url": "https://cdn.dsmcdn.com/ty1807/prod/QC_PREP/20251228/14/8e144cb4-03f2-35aa-8ef8-fa7ef4b099f2/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1807/prod/QC_PREP/20251228/14/8e144cb4-03f2-35aa-8ef8-fa7ef4b099f2/1_org_zoom.jpg"],
            },
            "cap": {
                "id": "ty_697446548",
                "brand": "VOGUE",
                "price": "1.400₺",
                "price_val": 1400.0,
                "name": "Vogue 5496SI W65613 54 Kadın Güneş Gözlüğü",
                "full_name": "Vogue 5496SI W65613 54 Kadın Güneş Gözlüğü",
                "sku": "697446548",
                "color": "Koyu Kahve / Siyah",
                "store_url": "https://www.trendyol.com/vogue/5496si-w65613-54-kadin-p-697446548",
                "product_url": "https://guzelai.com/go/697446548",
                "image_url": "https://cdn.dsmcdn.com/ty871/product/media/images/20230509/17/343728268/932211145/1/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty871/product/media/images/20230509/17/343728268/932211145/1/1_org_zoom.jpg"],
            },
            "top": {
                "id": "ty_903567167",
                "brand": "MODASPARK",
                "price": "309,05₺",
                "price_val": 309.05,
                "name": "Kadın Bordo Bisiklet Yaka Fitilli Oversize Triko Kazak",
                "full_name": "MODASPARK Bordo Bisiklet Yaka Fitilli Oversize Kadın Triko Kazak",
                "sku": "903567167",
                "color": "Bordo",
                "store_url": "https://www.trendyol.com/modaspark/bordo-bisiklet-yaka-oversize-kadin-triko-kazak-p-903567167",
                "product_url": "https://guzelai.com/go/903567167",
                "image_url": "https://cdn.dsmcdn.com/ty1632/prod/QC/20250202/15/9830164e-8f57-3365-952e-d77fd145269c/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1632/prod/QC/20250202/15/9830164e-8f57-3365-952e-d77fd145269c/1_org_zoom.jpg"],
            },
            "bottom": {
                "id": "ty_866458994",
                "brand": "RITNICE",
                "price": "789₺",
                "price_val": 789.0,
                "name": "Kadın Rena Kemerli Likralı Yüksek Bel Antrasit Palazzo Pantolon",
                "full_name": "Ritnice Kadın Rena Kemerli Likralı Yüksek Bel Pileli Antrasit Palazzo Pantolon",
                "sku": "866458994",
                "color": "Antrasit",
                "store_url": "https://www.trendyol.com/ritnice/kadin-rena-kemerli-likrali-antrasit-palazzo-pantolon-p-866458994",
                "product_url": "https://guzelai.com/go/866458994",
                "image_url": "https://cdn.dsmcdn.com/ty1590/prod/QC/20241023/12/4dc22706-3140-3522-8f6d-be4bc517e649/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1590/prod/QC/20241023/12/4dc22706-3140-3522-8f6d-be4bc517e649/1_org_zoom.jpg"],
            },
            "bag": {
                "id": "ty_988558235",
                "brand": "NEVNIHAL",
                "price": "489₺",
                "price_val": 489.0,
                "name": "Kadın Fermuarlı Yumuşak Deri Siyah Omuz Çantası",
                "full_name": "Nevnihal Fermuarlı ve Astarlı Yumuşak Deri Günlük Geniş Kadın Siyah Çanta",
                "sku": "988558235",
                "color": "Siyah",
                "store_url": "https://www.trendyol.com/nevnihal/fermuarli-ve-astarli-yumusak-deri-gunluk-genis-kadin-canta-p-988558235",
                "product_url": "https://guzelai.com/go/988558235",
                "image_url": "https://cdn.dsmcdn.com/ty1756/prod/QC_ENRICHMENT/20250923/12/b99749b8-5bd2-3d13-b122-ab543866c963/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1756/prod/QC_ENRICHMENT/20250923/12/b99749b8-5bd2-3d13-b122-ab543866c963/1_org_zoom.jpg"],
            },
            "shoes": {
                "id": "ty_893278946",
                "brand": "ADIDAS",
                "price": "3.999,50₺",
                "price_val": 3999.50,
                "name": "Samba OG W Kadın Sneaker Ayakkabı IE5836",
                "full_name": "adidas Samba OG W Kadın Sneaker Spor Ayakkabı IE5836",
                "sku": "893278946",
                "color": "Siyah / Beyaz / Gum",
                "store_url": "https://www.trendyol.com/adidas/samba-og-w-kadin-sneaker-ie5836-p-893278946",
                "product_url": "https://guzelai.com/go/893278946",
                "image_url": "https://cdn.dsmcdn.com/ty1627/prod/QC/20250120/05/b5a2ef4e-77c7-3029-9f21-6c8f3eb8a8ab/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1627/prod/QC/20250120/05/b5a2ef4e-77c7-3029-9f21-6c8f3eb8a8ab/1_org_zoom.jpg"],
            },
        },
        "keywords": {
            "outerwear": ["siyah", "deri", "oversize", "kadın", "ceket"],
            "cap": ["vogue", "siyah", "kahve", "kadın", "gözlük"],
            "top": ["bordo", "dik yaka", "boğazlı", "kadın", "kazak", "triko"],
            "bottom": ["antrasit", "siyah", "pileli", "palazzo", "kadın", "pantolon"],
            "bag": ["siyah", "deri", "kadın", "omuz", "çanta"],
            "shoes": ["samba", "adidas", "kadın", "sneaker"],
        },
        "cutout_assets": {
            "outerwear": "assets/items/th_01_jacket.png",
            "cap": "assets/items/th_02_cap.png",
            "top": "assets/items/th_03_top.png",
            "bottom": "assets/items/th_04_bottom.png",
            "bag": "assets/items/th_05_bag.png",
            "shoes": "assets/items/th_06_shoes.png",
        },
        "fallback_cutout_assets": {
            "outerwear": "assets/items/th_01_jacket.png",
            "cap": "assets/items/th_02_cap.png",
            "top": "assets/items/th_03_top.png",
            "bottom": "assets/items/th_04_bottom.png",
            "bag": "assets/items/th_05_bag.png",
            "shoes": "assets/items/th_06_shoes.png",
        },
        "model_frames": [
            "assets/tesla_halloween_step1.jpg",
            "assets/tesla_halloween_step2.jpg",
            "assets/tesla_halloween_step3.jpg",
        ],
    },
    {
        "id": "inner_voice_black_bomber_stone_palazzo",
        "title": "İç sesim bir dakika bile susmadığı için gün boyu böyleyim 😭✨ (Ama kombinimden asla ödün vermem)",
        "viral_hook": "🛑 Kafamın içinde 40 tilki dönerken dışarıya verdiğim 'Her şey kontrol altında' imajı! Siyah kaşe bomber ceket ve taş rengi palazzo jean uyumuyla gün boyu kurtarıcı 6 kadın parçası! 👇🔥",
        "seo_note": "📌 Not: Videodaki %100 Kadın kombin parçalarının canlı taranmış mağaza ve benzer muadil ürün linkleri aşağıda doğrulanarak listelenmiştir:",
        "verified_exact_items": {
            "outerwear": {
                "id": "ty_1194463658",
                "brand": "LACASE",
                "price": "852,24₺",
                "price_val": 852.24,
                "name": "Kadın Kaşe Bomber Siyah Ceket (Benzer Muadil)",
                "full_name": "LACASE Kadın Kaşe Bomber Siyah Ceket (Görseldeki Ürünün Birebir/Benzer Muadili)",
                "sku": "1194463658",
                "color": "Siyah",
                "product_url": "https://www.trendyol.com/lacase/kadin-kase-bomber-siyah-ceket-p-1194463658",
                "image_url": "https://cdn.dsmcdn.com/ty1950/prod/QC_PREP/20260901/17/b79dd0f6-c1a3-35af-b780-11ba074fdb25/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1950/prod/QC_PREP/20260901/17/b79dd0f6-c1a3-35af-b780-11ba074fdb25/1_org_zoom.jpg"],
            },
            "cap": {
                "id": "ty_1107126267",
                "brand": "NILU MODA",
                "price": "264,28₺",
                "price_val": 264.28,
                "name": "Lüks Kristal Gold Detaylı Siyah Kadın Güneş Gözlüğü",
                "full_name": "Nilu Moda Lüks Kristal Gold Örme Detaylı Siyah Kadın Güneş Gözlüğü",
                "sku": "1107126267",
                "color": "Siyah / Gold",
                "product_url": "https://www.trendyol.com/nilu-moda/lux-kristal-gold-orme-detayli-siyah-kadin-gunes-gozlugu-p-1107126267",
                "image_url": "https://cdn.dsmcdn.com/ty1857/prod/QC_ENRICHMENT/20260424/17/eb63b57a-4da8-3818-ae45-9cd0c858a7cd/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1857/prod/QC_ENRICHMENT/20260424/17/eb63b57a-4da8-3818-ae45-9cd0c858a7cd/1_org_zoom.jpg"],
            },
            "top": {
                "id": "ty_855800408",
                "brand": "DEFACTO",
                "price": "297,49₺",
                "price_val": 297.49,
                "name": "Kadın Oversize Bisiklet Yaka Triko/Sweatshirt (Benzer Muadil)",
                "full_name": "DeFacto Kadın Oversize Bisiklet Yaka Basic Sweatshirt A4177AX24WN (Benzer Muadil)",
                "sku": "855800408",
                "color": "Açık Gri / Ekru",
                "product_url": "https://www.trendyol.com/defacto/oversize-bisiklet-yaka-basic-sweatshirt-a4177ax24wn-p-855800408",
                "image_url": "https://cdn.dsmcdn.com/ty1836/prod/QC_ENRICHMENT/20260312/12/a4bcf387-1412-33c8-8f0a-524aa0542fe2/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1836/prod/QC_ENRICHMENT/20260312/12/a4bcf387-1412-33c8-8f0a-524aa0542fe2/1_org_zoom.jpg"],
            },
            "bottom": {
                "id": "ty_776397345",
                "brand": "LAMİRAMOOD",
                "price": "647,03₺",
                "price_val": 647.03,
                "name": "Kadın Taş Rengi Palazzo Bol Paça Yüksek Bel Jean Pantolon",
                "full_name": "LAMİRAMOOD Taş Palazzo Bol Paça Yüksek Bel Kadın Kot Pantolon",
                "sku": "776397345",
                "color": "Taş / Açık Gri",
                "product_url": "https://www.trendyol.com/lamiramood/tas-palazzo-bol-paca-yuksek-bel-kot-pantolon-p-776397345",
                "image_url": "https://cdn.dsmcdn.com/ty1443/product/media/images/prod/QC/20240726/20/eea924c7-2c97-37ad-a143-60e543c3536d/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1443/product/media/images/prod/QC/20240726/20/eea924c7-2c97-37ad-a143-60e543c3536d/1_org_zoom.jpg"],
            },
            "bag": {
                "id": "ty_990568843",
                "brand": "JUDOUR BAGS",
                "price": "199₺",
                "price_val": 199.0,
                "name": "Kadın Siyah Fularlı Fermuarlı Deri El ve Omuz Çantası",
                "full_name": "Judour Bags Siyah Kadın Fularlı Fermuarlı Kapamalı Shopper El ve Omuz Çantası",
                "sku": "990568843",
                "color": "Siyah",
                "product_url": "https://www.trendyol.com/judour-bags/siyah-kadin-fularli-fermuarli-kapamali-shopper-el-ve-omuz-cantasi-p-990568843",
                "image_url": "https://cdn.dsmcdn.com/ty1963/prod/QC_ENRICHMENT/20260925/16/24a9554e-13de-3977-87c3-71282050156c/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1963/prod/QC_ENRICHMENT/20260925/16/24a9554e-13de-3977-87c3-71282050156c/1_org_zoom.jpg"],
            },
            "shoes": {
                "id": "ty_822317202",
                "brand": "ADIDAS",
                "price": "2.312,02₺",
                "price_val": 2312.02,
                "name": "VL Court Base Kadın Sneaker Ayakkabı ID3715",
                "full_name": "adidas VL Court Base Kadın Sneaker Spor Ayakkabı ID3715",
                "sku": "822317202",
                "color": "Beyaz / Siyah",
                "product_url": "https://www.trendyol.com/adidas/vl-court-base-kadin-sneaker-id3715-p-822317202",
                "image_url": "https://cdn.dsmcdn.com/ty1841/prod/QC_ENRICHMENT/20260316/15/b8e1af12-82dc-33ef-86bd-924539c7e7b1/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1841/prod/QC_ENRICHMENT/20260316/15/b8e1af12-82dc-33ef-86bd-924539c7e7b1/1_org_zoom.jpg"],
            },
        },
        "keywords": {
            "outerwear": ["siyah", "kaşe", "bomber", "kadın", "ceket"],
            "cap": ["siyah", "gold", "kadın", "gözlük"],
            "top": ["gri", "ekru", "bisiklet", "kadın", "kazak", "sweatshirt"],
            "bottom": ["taş", "gri", "yüksek bel", "palazzo", "kadın", "kot", "pantolon"],
            "bag": ["siyah", "fularlı", "kadın", "omuz", "çanta"],
            "shoes": ["beyaz", "court", "adidas", "kadın", "sneaker"],
        },
        "cutout_assets": {
            "outerwear": "assets/items/iv_01_jacket.png",
            "cap": "assets/items/iv_02_cap.png",
            "top": "assets/items/iv_03_top.png",
            "bottom": "assets/items/iv_04_bottom.png",
            "bag": "assets/items/iv_05_bag.png",
            "shoes": "assets/items/iv_06_shoes.png",
        },
        "fallback_cutout_assets": {
            "outerwear": "assets/items/iv_01_jacket.png",
            "cap": "assets/items/iv_02_cap.png",
            "top": "assets/items/iv_03_top.png",
            "bottom": "assets/items/iv_04_bottom.png",
            "bag": "assets/items/iv_05_bag.png",
            "shoes": "assets/items/iv_06_shoes.png",
        },
        "model_frames": [
            "assets/inner_voice_curly_step1.jpg",
            "assets/inner_voice_curly_step2.jpg",
            "assets/inner_voice_curly_step3.jpg",
        ],
    },
    {
        "id": "telegram_curly_champagne_palazzo",
        "title": "5.000₺ Bütçeyle 50.000₺'lik 'Old Money' Görünmenin Sırrı! (4. Parçaya Dikkat) 🔥",
        "viral_hook": "🛑 SAKIN GEÇME! Girdiğin her ortamda 'Üzerindekileri hangi lüks markadan aldın?' dedirten, boyu 10 cm daha uzun gösteren o 6 parçalık Old Money kadın kombin sırrı çözüldü! 👇✨",
        "seo_note": "📌 Not: Görseldeki kadın kombin parçalarının stokta olan birebir veya en yakın %100 Kadın mağaza muadil (benzer) ürün linkleri doğrulanarak aşağıya eklenmiştir:",
        "verified_exact_items": {
            "outerwear": {
                "id": "ty_959328122",
                "brand": "FERRUCCI",
                "price": "2.473,45₺",
                "price_val": 2473.45,
                "name": "Kadın Gold Çelik Kordon Kol Saati (Benzer Muadil)",
                "full_name": "Ferrucci Çelik Kordon Çelik Kasa Kadın Kol Saati 3 ATM Su Geçirmez Gold (Görseldeki Ürünün Birebir/Benzer Muadili)",
                "sku": "959328122",
                "color": "Altın / Gold",
                "product_url": "https://www.trendyol.com/ferrucci/celik-kordon-celik-kasa-kadin-kol-saati-3-atm-su-gecirmez-gumus-gold-zmfer190-p-959328122",
                "image_url": "https://cdn.dsmcdn.com/ty1713/prod/QC_PREP/20250721/23/d1929c87-d600-32e5-990d-94ce553396d7/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1713/prod/QC_PREP/20250721/23/d1929c87-d600-32e5-990d-94ce553396d7/1_org_zoom.jpg"],
            },
            "cap": {
                "id": "ty_1120763550",
                "brand": "BYC POLO",
                "price": "118₺",
                "price_val": 118.0,
                "name": "Kadın Gold & Kahve Zarif Aksesuar Gözlük (Benzer Muadil)",
                "full_name": "BYC POLO Kahve & Gold Zarif Şık Kadın Güneş Gözlüğü Aksesuar (Görseldeki Takı/Aksesuarın Muadili)",
                "sku": "1120763550",
                "color": "Gold / Kahve",
                "product_url": "https://www.trendyol.com/byc-polo/cbp064-gcc-kahve-zarif-sik-kadin-gunes-gozlugu-p-1120763550",
                "image_url": "https://cdn.dsmcdn.com/ty1848/prod/QC_ENRICHMENT/20260403/22/47e91a8f-ee4b-3ac4-a180-c91099f8d6e0/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1848/prod/QC_ENRICHMENT/20260403/22/47e91a8f-ee4b-3ac4-a180-c91099f8d6e0/1_org_zoom.jpg"],
            },
            "top": {
                "id": "ty_1059088919",
                "brand": "ETOS",
                "price": "863,10₺",
                "price_val": 863.10,
                "name": "Kadın Saten Kumaş Gizli Düğmeli Gömlek (Benzer Muadil)",
                "full_name": "Etos Kadın Gömlek Saten Kumaş Gizli Düğmeli Kırışmaz Şık Kadın Gömlek (Görseldeki Ürünün Birebir/Benzer Muadili)",
                "sku": "1059088919",
                "color": "Şampanya / Ekru",
                "product_url": "https://www.trendyol.com/etos/kadin-gomlek-saten-kumas-yeni-trend-model-nakisli-gizli-dugme-kirismaz-kumas-p-1059088919",
                "image_url": "https://cdn.dsmcdn.com/ty1797/prod/QC_ENRICHMENT/20251208/18/df37804e-e30c-392c-99e6-d1ab12938109/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1797/prod/QC_ENRICHMENT/20251208/18/df37804e-e30c-392c-99e6-d1ab12938109/1_org_zoom.jpg"],
            },
            "bottom": {
                "id": "ty_652719507",
                "brand": "LAVİNİM",
                "price": "550,05₺",
                "price_val": 550.05,
                "name": "Kadın Yüksek Bel Pensli Kumaş Palazzo Pantolon (Benzer Muadil)",
                "full_name": "LAVİNİM Kadın Yüksek Bel Pensli Bol Paça Kumaş Palazzo Pantolon (Görseldeki Ürünün Birebir/Benzer Muadili)",
                "sku": "652719507",
                "color": "Acı Kahve",
                "product_url": "https://www.trendyol.com/lavinim/palazzo-pantolon-oversize-orjinal-kesim-p-652719507",
                "image_url": "https://cdn.dsmcdn.com/ty1000057/product/media/images/prod/PIM/20260106/07/dfcdaed6-81a7-4e40-b99f-844894f475c4/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1000057/product/media/images/prod/PIM/20260106/07/dfcdaed6-81a7-4e40-b99f-844894f475c4/1_org_zoom.jpg"],
            },
            "bag": {
                "id": "ty_1206721873",
                "brand": "NWR BAGS",
                "price": "501,90₺",
                "price_val": 501.90,
                "name": "Kadın Krem & Kahve Deri El ve Omuz Çantası (Benzer Muadil)",
                "full_name": "NWR BAGS Kadın Krem ve Kahverengi Detaylı Omuz ve El Çantası (Görseldeki Ürünün Birebir/Benzer Muadili)",
                "sku": "1206721873",
                "color": "Krem / Kahve",
                "product_url": "https://www.trendyol.com/nwr-bags/3-lu-set-fular-detayli-kadin-omuz-ve-kol-cantasi-siyah-krem-kahverengi-p-1206721873",
                "image_url": "https://cdn.dsmcdn.com/ty1965/prod/QC_PREP/20260929/17/b5ffd1b8-5227-3a8e-836d-fed1fc28e822/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1965/prod/QC_PREP/20260929/17/b5ffd1b8-5227-3a8e-836d-fed1fc28e822/1_org_zoom.jpg"],
            },
            "shoes": {
                "id": "ty_938465141",
                "brand": "SAVVES",
                "price": "678,94₺",
                "price_val": 678.94,
                "name": "Kadın Bantlı Klasik Sivri Burun Topuklu Ayakkabı (Benzer Muadil)",
                "full_name": "Savves Kadın Bantlı Yeni Sezon Klasik Sivri Burun Topuklu Ayakkabı (Görseldeki Ürünün Birebir/Benzer Muadili)",
                "sku": "938465141",
                "color": "Krem / Rugan",
                "product_url": "https://www.trendyol.com/savves/kadin-siyah-rugan-bantli-yeni-sezon-kisa-topuklu-ayakkabi-p-938465141",
                "image_url": "https://cdn.dsmcdn.com/ty1688/prod/QC_ENRICHMENT/20250601/18/3a70ca83-a221-3c05-adf7-1fb355c4a31c/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1688/prod/QC_ENRICHMENT/20250601/18/3a70ca83-a221-3c05-adf7-1fb355c4a31c/1_org_zoom.jpg"],
            },
        },
        "keywords": {
            "outerwear": ["gold", "altın", "kadın", "saat"],
            "cap": ["gold", "kahve", "kadın", "gözlük", "küpe"],
            "top": ["ekru", "krem", "saten", "kadın", "gömlek"],
            "bottom": ["kahve", "yüksek bel", "palazzo", "kadın", "pantolon"],
            "bag": ["krem", "bej", "kadın", "el", "omuz", "çanta"],
            "shoes": ["krem", "bantlı", "sivri", "kadın", "topuklu"],
        },
        "cutout_assets": {
            "outerwear": "assets/items/tg_01_watch.png",
            "cap": "assets/items/tg_02_earrings.png",
            "top": "assets/items/tg_03_shirt.png",
            "bottom": "assets/items/tg_04_pants.png",
            "bag": "assets/items/tg_05_bag.png",
            "shoes": "assets/items/tg_06_heels.png",
        },
        "fallback_cutout_assets": {
            "outerwear": "assets/items/tg_01_watch.png",
            "cap": "assets/items/tg_02_earrings.png",
            "top": "assets/items/tg_03_shirt.png",
            "bottom": "assets/items/tg_04_pants.png",
            "bag": "assets/items/tg_05_bag.png",
            "shoes": "assets/items/tg_06_heels.png",
        },
        "model_frames": [
            "assets/telegram_curly_step1.jpg",
            "assets/telegram_curly_step2.jpg",
            "assets/telegram_curly_step3.jpg",
        ],
    },
    {
        "id": "curly_khaki_suede_palazzo",
        "title": "Haki Süet Bomber & Antrasit Palazzo Sonbahar Kadın Stili",
        "viral_hook": "🛑 BU SONBAHAR HERKESİN ÜZERİNDE GÖRECEĞİNİZ O KOMBİN! Ekim & Cadılar Bayramı haftasında hem gündüz hem gece kurtarıcı 6 parça! 👇🔥",
        "seo_note": "📌 Kombindeki %100 Kadın parçaların doğrulanmış mağaza ve benzer muadil linkleri aşağıdadır:",
        "verified_exact_items": {
            "outerwear": {
                "id": "ty_985362984",
                "brand": "NET OF NOT",
                "price": "1.424,99₺",
                "price_val": 1424.99,
                "name": "Oversize Kadın Bomber Haki Süet Deri Ceket",
                "full_name": "NET OF NOT Oversize Kadın Bomber Haki Süet Deri Ceket",
                "sku": "985362984",
                "color": "Haki",
                "product_url": "https://www.trendyol.com/net-of-not/oversize-kadin-bomber-haki-suet-deri-ceket-p-985362984",
                "image_url": "https://cdn.dsmcdn.com/ty1753/prod/QC_PREP/20250910/20/7dfc80a6-17a4-3901-a8c3-b461800247a7/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1753/prod/QC_PREP/20250910/20/7dfc80a6-17a4-3901-a8c3-b461800247a7/1_org_zoom.jpg"],
            },
            "cap": {
                "id": "ty_1160666803",
                "brand": "NILU MODA",
                "price": "130,29₺",
                "price_val": 130.29,
                "name": "Premium Siyah Kadın Oval Vintage Güneş Gözlüğü",
                "full_name": "NILU MODA Premium Siyah Kadın Güneş Gözlüğü UV400 Korumalı Oval Vintage Tasarım",
                "sku": "1160666803",
                "color": "Siyah",
                "product_url": "https://www.trendyol.com/nilu-moda/premium-siyah-kadin-gunes-gozlugu-uv400-korumali-oval-vintage-tasarim-p-1160666803",
                "image_url": "https://cdn.dsmcdn.com/ty1935/prod/QC_PREP/20260625/09/d21386fe-930a-3d8a-b762-8b7984913232/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1935/prod/QC_PREP/20260625/09/d21386fe-930a-3d8a-b762-8b7984913232/1_org_zoom.jpg"],
            },
            "top": {
                "id": "ty_963371271",
                "brand": "GÜLCE MODA",
                "price": "431,23₺",
                "price_val": 431.23,
                "name": "Kadın Bisiklet Yaka Yumuşak Dokulu Oversize Triko Kazak",
                "full_name": "GÜLCE MODA Kadın Bisiklet Yaka Yumuşak Dokulu Oversize Triko Kazak",
                "sku": "963371271",
                "color": "Ekru",
                "product_url": "https://www.trendyol.com/gulce-moda/kadin-bisiklet-yaka-yumusak-dokulu-oversize-triko-kazak-p-963371271",
                "image_url": "https://cdn.dsmcdn.com/ty1956/prod/QC_ENRICHMENT/20260913/00/a333cf9f-e2a1-333a-95c1-410ec6a7c513/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1956/prod/QC_ENRICHMENT/20260913/00/a333cf9f-e2a1-333a-95c1-410ec6a7c513/1_org_zoom.jpg"],
            },
            "bottom": {
                "id": "ty_866458994",
                "brand": "RITNICE",
                "price": "789₺",
                "price_val": 789.0,
                "name": "Kadın Rena Kemerli Likralı Antrasit Palazzo Pantolon",
                "full_name": "RITNICE Kadın Rena Kemerli Likralı Antrasit Palazzo Pantolon",
                "sku": "866458994",
                "color": "Antrasit",
                "product_url": "https://www.trendyol.com/ritnice/kadin-rena-kemerli-likrali-antrasit-palazzo-pantolon-p-866458994",
                "image_url": "https://cdn.dsmcdn.com/ty1945/prod/QC_ENRICHMENT/20260819/16/3d01e71d-545b-3160-b00e-91c7a8b4ec07/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1945/prod/QC_ENRICHMENT/20260819/16/3d01e71d-545b-3160-b00e-91c7a8b4ec07/1_org_zoom.jpg"],
            },
            "bag": {
                "id": "ty_826407400",
                "brand": "HAPBUY",
                "price": "449₺",
                "price_val": 449.0,
                "name": "Kadın Siyah Yumuşak Dokulu Deri Omuz Çantası",
                "full_name": "HAPBUY Kadın Siyah Omuz Çantası Yumuşak İç ve Dış Dokulu Suni Deri El Çantası",
                "sku": "826407400",
                "color": "Siyah",
                "product_url": "https://www.trendyol.com/hapbuy/kadin-siyah-omuz-cantasi-yumusak-ic-ve-dis-dokulu-kaliteli-iscilik-ve-yumusak-suni-deri-el-cantasi-p-826407400",
                "image_url": "https://cdn.dsmcdn.com/ty1723/prod/QC_ENRICHMENT/20250808/10/5f0408d2-bd1e-3652-abdc-2aa23cadf6f3/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1723/prod/QC_ENRICHMENT/20250808/10/5f0408d2-bd1e-3652-abdc-2aa23cadf6f3/1_org_zoom.jpg"],
            },
            "shoes": {
                "id": "ty_994497307",
                "brand": "ADIDAS",
                "price": "4.499,40₺",
                "price_val": 4499.40,
                "name": "Handball Spezial Kadın Sneaker Ayakkabı",
                "full_name": "ADIDAS Handball Spezial Kadın Sneaker Ayakkabı",
                "sku": "994497307",
                "color": "Bordo / Beyaz",
                "product_url": "https://www.trendyol.com/adidas/handball-spezial-kadin-bordo-ayakkabi-p-994497307",
                "image_url": "https://cdn.dsmcdn.com/ty1773/prod/QC_PREP/20251015/15/79e6780b-45ee-3203-93e2-d72ac87fab56/1_org_zoom.jpg",
                "image_urls": ["https://cdn.dsmcdn.com/ty1773/prod/QC_PREP/20251015/15/79e6780b-45ee-3203-93e2-d72ac87fab56/1_org_zoom.jpg"],
            },
        },
        "keywords": {
            "outerwear": ["haki", "süet", "deri", "bomber", "ceket"],
            "cap": ["siyah", "oval", "vintage", "gözlük"],
            "top": ["ekru", "krem", "bisiklet", "triko", "kazak"],
            "bottom": ["antrasit", "kemerli", "palazzo", "pantolon"],
            "bag": ["siyah", "omuz", "deri", "çanta"],
            "shoes": ["kadın", "spezial", "adidas", "sneaker"],
        },
        "cutout_assets": {
            "outerwear": "assets/items/curly_01_jacket.png",
            "cap": "assets/items/curly_02_cap.png",
            "top": "assets/items/curly_03_top.png",
            "bottom": "assets/items/curly_04_bottom.png",
            "bag": "assets/items/curly_05_bag.png",
            "shoes": "assets/items/curly_06_shoes.png",
        },
        "fallback_cutout_assets": {
            "outerwear": "assets/items/curly_01_jacket.png",
            "cap": "assets/items/curly_02_cap.png",
            "top": "assets/items/curly_03_top.png",
            "bottom": "assets/items/curly_04_bottom.png",
            "bag": "assets/items/curly_05_bag.png",
            "shoes": "assets/items/curly_06_shoes.png",
        },
        "model_frames": [
            "assets/curly_model_step1.jpg",
            "assets/curly_model_step2.jpg",
            "assets/curly_model_step3.jpg",
        ],
    },
    {
        "id": "pajama_morning_vibe",
        "title": "Pastel Mavi Pijama & Sabah Ev Stili",
        "category_map": {
            "outerwear": "pajama_set",
            "cap": "cap",
            "top": "camisole_top",
            "bottom": "pajama_shorts",
            "bag": "bag",
            "shoes": "house_slippers",
        },
        "keywords": {
            "outerwear": ["pijama", "gömlek", "saten", "pamuklu", "mavi", "penti", "takım"],
            "cap": ["uyku", "maske", "göz", "mavi", "saten", "aksesuar"],
            "top": ["beyaz", "ekru", "askılı", "büstiyer", "bralet", "crop", "pamuklu"],
            "bottom": ["şort", "mavi", "gri", "pamuklu", "penye", "rahat"],
            "bag": ["krem", "bej", "beyaz", "kapitone", "çanta"],
            "shoes": ["beyaz", "bej", "terlik", "ev", "rahat", "yumuşak", "babet"],
        },
        "cutout_assets": {
            "outerwear": "assets/items/outfit3_01_jacket.png",
            "cap": "assets/items/outfit3_02_cap.png",
            "top": "assets/items/outfit3_03_top.png",
            "bottom": "assets/items/outfit3_04_bottom.png",
            "bag": "assets/items/outfit3_05_bag.png",
            "shoes": "assets/items/outfit3_06_shoes.png",
        },
        "fallback_cutout_assets": {
            "outerwear": "assets/items/outfit3_01_jacket.png",
            "cap": "assets/items/outfit3_02_cap.png",
            "top": "assets/items/outfit3_03_top.png",
            "bottom": "assets/items/outfit3_04_bottom.png",
            "bag": "assets/items/outfit3_05_bag.png",
            "shoes": "assets/items/outfit3_06_shoes.png",
        },
        "model_frames": [
            "assets/outfit3_model_step1.jpg",
            "assets/outfit3_model_step2.jpg",
            "assets/outfit3_model_step3.jpg",
        ],
    },
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
                    raw_title = it.get("name", "")
                    if any(bad in raw_title.lower() for bad in ("erkek", "unisex", "bay ")):
                        continue
                    clean_name = _clean_product_title(raw_title, raw_brand)
                    if "(Benzer Muadil)" not in clean_name:
                        clean_name = f"{clean_name} (Benzer Muadil)"
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
        lum = (r + g + b) / 3.0
        spread = max(r, g, b) - min(r, g, b)
        if lum > 242 and spread < 15:
            new_data.append((r, g, b, 0))
        elif lum > 232 and spread < 19:
            alpha_w = int((242 - lum) / 10.0 * 255)
            new_data.append((r, g, b, min(a, max(0, min(255, alpha_w)))))
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
                if HAS_REMBG or is_clean_white_packshot(raw_im):
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


def _infer_slot_from_text(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["ceket", "mont", "kaban", "trençkot", "trenckot", "yağmurluk", "yagmurluk", "yelek", "blazer", "hırka", "hirka", "pijama"]):
        return "outerwear"
    if any(k in t for k in ["gözlük", "gozluk", "şapka", "sapka", "bere", "atkı", "atki", "fular", "kemer", "kolye", "küpe", "kupe", "bileklik", "saat", "toka"]):
        return "cap"
    if any(k in t for k in ["pantolon", "jean", "kot", "tayt", "etek", "şort", "sort", "eşofman altı", "palazzo", "jogger"]):
        return "bottom"
    if any(k in t for k in ["çanta", "canta", "cüzdan", "cuzdan", "baget", "omuz çantası", "kol çantası"]):
        return "bag"
    if any(k in t for k in ["ayakkabı", "ayakkabi", "sneaker", "spor ayakkabı", "bot", "çizme", "cizme", "terlik", "topuklu", "loafer", "babet", "sandalet"]):
        return "shoes"
    return "top"


def scrape_single_product_url(url: str, fallback_slot: str = "top") -> tuple[str, dict]:
    """Scrapes brand, title, price, SKU, and image from any e-commerce product URL (Trendyol, Zara, etc.)."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower().replace("www.", "")
    brand = host.split(".")[0].upper() if host else "MAĞAZA"
    title = "Özel Seçim Kombin Parçası"
    price_val = 750.0
    sku = ""
    img_url = ""

    m_sku = re.search(r"-p-(\d+)", url)
    if m_sku:
        sku = m_sku.group(1)

    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        html_text = r.text
        for block in _extract_json_ld_blocks(html_text):
            btype = block.get("@type")
            if btype in ("Product", "ProductGroup") or "offers" in block:
                title = block.get("name") or title
                b_obj = block.get("brand")
                if isinstance(b_obj, dict):
                    brand = b_obj.get("name") or brand
                elif isinstance(b_obj, str):
                    brand = b_obj
                offers = block.get("offers")
                if isinstance(offers, list) and offers:
                    offers = offers[0]
                if isinstance(offers, dict):
                    p_raw = offers.get("price") or offers.get("lowPrice")
                    if p_raw:
                        price_val = float(str(p_raw).replace(",", "."))
                imgs = block.get("image")
                if isinstance(imgs, list) and imgs:
                    img_url = imgs[0] if isinstance(imgs[0], str) else (imgs[0].get("url") or "")
                elif isinstance(imgs, dict):
                    img_url = imgs.get("url") or ""
                elif isinstance(imgs, str):
                    img_url = imgs
                sku = str(block.get("sku") or block.get("productID") or sku)
                break

        if title == "Özel Seçim Kombin Parçası":
            m_og_t = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
            if m_og_t:
                title = m_og_t.group(1).split("|")[0].strip()
        if not img_url:
            m_og_i = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
            if m_og_i:
                img_url = m_og_i.group(1).strip()
    except Exception as e:
        print(f"[Özel Link Tarama Uyarısı] {url}: {e}")

    slot = _infer_slot_from_text(f"{title} {url}") or fallback_slot
    local_cutout = None
    if img_url:
        try:
            os.makedirs("output", exist_ok=True)
            cut_path = f"output/custom_item_{slot}.png"
            ir = requests.get(img_url, headers=HEADERS, timeout=10)
            if ir.status_code == 200:
                pil_img = Image.open(BytesIO(ir.content))
                cut_img = _remove_white_bg_and_crop(pil_img)
                cut_img.save(cut_path, format="PNG")
                local_cutout = cut_path
        except Exception as e:
            print(f"[Özel Ürün Görsel Dekupe Uyarısı] {e}")

    clean_name = _clean_product_title(title, brand)
    item_dict = {
        "id": f"custom_{sku or int(datetime.utcnow().timestamp())}",
        "brand": brand.upper(),
        "price": _format_price_tr(price_val),
        "price_val": price_val,
        "name": clean_name,
        "full_name": title,
        "sku": sku or "OZEL",
        "product_url": url,
        "image_url": img_url,
        "image_urls": [img_url] if img_url else [],
        "color": "",
    }
    if local_cutout:
        item_dict["local_asset"] = local_cutout
    return slot, item_dict


def select_daily_outfit(slot_name: str = "otomatik") -> dict:
    """
    Canlı e-ticaret mağazalarından (Trendyol, Quzu, Bagmori vb.) güncel ürünleri, gerçek TL fiyatlarını,
    SKU ürün kodlarını ve doğrudan satın alma linklerini çekerek her seferinde ÖZGÜN bir 6'lı kadın kombini oluşturur.
    Daha önce paylaşılan kombinleri ve SKU kodlarını output/published_outfits_history.json dosyasında takip ederek
    aynı kombinin tekrar paylaşılmasını engeller.
    """
    seed_str = f"{datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S')}-{slot_name}"
    rng = random.Random(hashlib.md5(seed_str.encode()).hexdigest())

    history_path = "output/published_outfits_history.json"
    used_archetypes = ["telegram_curly_champagne_palazzo", "curly_khaki_suede_palazzo"]
    used_skus = {
        "959328122", "1120763550", "1059088919", "652719507", "1206721873", "938465141",
        "985362984", "1160666803", "963371271", "866458994", "826407400", "994497307",
    }
    if os.path.exists(history_path):
        try:
            with open(history_path, "r", encoding="utf-8") as hf:
                h_data = json.load(hf)
                used_archetypes.extend(h_data.get("used_archetypes", []))
                used_skus.update(str(s) for s in h_data.get("used_skus", []))
        except Exception:
            pass

    # Öncelikle daha önce paylaşılmamış ve model kareleri mevcut olan özgün arketipi seç
    available_archetypes = [
        a for a in OUTFIT_ARCHETYPES
        if a["id"] not in used_archetypes[-2:] and os.path.exists(a["model_frames"][0])
    ]
    if not available_archetypes:
        available_archetypes = [a for a in OUTFIT_ARCHETYPES if os.path.exists(a["model_frames"][0])] or [OUTFIT_ARCHETYPES[0]]

    archetype = available_archetypes[0]
    force_live_scrape = archetype["id"] in used_archetypes

    print(f"[Özgün Kombin Motoru] '{archetype['title']}' ({archetype['id']}) için canlı mağaza ürünleri taranıyor...")

    cached_catalog = {}
    if os.path.exists("assets/live_trendyol_catalog.json"):
        try:
            with open("assets/live_trendyol_catalog.json", "r", encoding="utf-8") as f:
                cached_catalog = json.load(f)
        except Exception:
            cached_catalog = {}

    items = {}
    total_price = 0.0

    exact_map = archetype.get("verified_exact_items", {})
    cat_map = archetype.get("category_map", {})
    for cat_key in ["outerwear", "cap", "top", "bottom", "bag", "shoes"]:
        chosen = None
        if not force_live_scrape and exact_map.get(cat_key):
            chosen = dict(exact_map[cat_key])

        if not chosen:
            mapped_cat = cat_map.get(cat_key, cat_key)
            live_pool = fetch_live_trendyol_items(cat_key)
            if cat_key == "bag":
                live_pool = fetch_live_bagmori_bags() + live_pool
            elif cat_key in ("outerwear", "top", "bottom"):
                live_pool = live_pool + fetch_live_quzu_items(cat_key)
            if cached_catalog.get(mapped_cat):
                live_pool.extend(cached_catalog[mapped_cat])
            elif cached_catalog.get(cat_key):
                live_pool.extend(cached_catalog[cat_key])

            fresh_pool = [it for it in live_pool if str(it.get("sku", "")) not in used_skus]
            chosen = _pick_matching_live_item(fresh_pool or live_pool, archetype["keywords"].get(cat_key, []), rng)

        if not chosen and exact_map.get(cat_key):
            chosen = dict(exact_map[cat_key])

        if not chosen:
            chosen = {
                "id": f"fallback_{cat_key}",
                "brand": "TRENDYOL",
                "price": "890₺",
                "price_val": 890.0,
                "name": f"Yeni Sezon Kadın {cat_key.title()}",
                "full_name": f"Yeni Sezon Kadın {cat_key.title()}",
                "sku": "202601",
                "store_url": "https://www.trendyol.com/butik/liste/1/kadin",
                "product_url": "https://guzelai.com/#kombinler",
                "image_url": "",
                "image_urls": [],
            }

        # Tüm linkleri guzelai.com/go/{sku} üzerinden yönlendir (trafik guzelai.com'a gelir, oradan mağazaya yönlenir)
        sku_str = str(chosen.get("sku", "")).strip()
        raw_url = chosen.get("store_url") or chosen.get("product_url") or ""
        if "guzelai.com/go/" not in raw_url and raw_url:
            chosen["store_url"] = raw_url
        if sku_str and sku_str != "-":
            chosen["guzelai_url"] = f"https://guzelai.com/go/{sku_str}"
            chosen["product_url"] = f"https://guzelai.com/go/{sku_str}"

        if not force_live_scrape:
            chosen["local_asset"] = archetype["cutout_assets"].get(cat_key)
        else:
            chosen["local_asset"] = None
        chosen["fallback_asset"] = archetype["fallback_cutout_assets"].get(cat_key)
        items[cat_key] = chosen
        if chosen.get("sku"):
            used_skus.add(str(chosen["sku"]))
        print(
            f"  ✓ [{cat_key.upper()}] {chosen['brand']} - {chosen['name']} ({chosen['price']}) "
            f"-> {chosen['product_url']} (Mağaza: {chosen.get('store_url', '')})"
        )

    # Paylaşılan kombin geçmişini kaydet (bir sonraki çalışmada aynı kombinin seçilmesini önler)
    try:
        os.makedirs("output", exist_ok=True)
        used_archetypes.append(archetype["id"])
        with open(history_path, "w", encoding="utf-8") as hf:
            json.dump(
                {
                    "used_archetypes": used_archetypes[-15:],
                    "used_skus": list(used_skus)[-180:],
                    "last_updated": datetime.utcnow().isoformat(),
                },
                hf,
                ensure_ascii=False,
                indent=2,
            )
    except Exception as he:
        print(f"[Kombin Geçmişi Kayıt Uyarısı] {he}")

    model_frames = list(archetype["model_frames"])
    archetype_title = archetype["title"]

    # Check if Telegram Bot triggered a custom link or image override
    override_path = "output/telegram_trigger_override.json"
    if os.path.exists(override_path):
        try:
            with open(override_path, "r", encoding="utf-8") as of:
                ov = json.load(of)
            print(f"[Telegram Tetikleme Override Algılandı]: {ov}")
            custom_urls = ov.get("custom_urls") or []
            slot_cycle = ["outerwear", "top", "bottom", "bag", "shoes", "cap"]
            for idx, c_url in enumerate(custom_urls):
                slot_k, c_item = scrape_single_product_url(c_url, fallback_slot=slot_cycle[idx % len(slot_cycle)])
                if not c_item.get("local_asset"):
                    c_item["local_asset"] = archetype["cutout_assets"].get(slot_k)
                c_item["fallback_asset"] = archetype["fallback_cutout_assets"].get(slot_k)
                items[slot_k] = c_item
                print(f"  ★ [TELEGRAM ÖZEL ÜRÜN -> {slot_k.upper()}] {c_item['brand']} - {c_item['name']} ({c_item['price']})")

            custom_img = ov.get("custom_image")
            if custom_img and os.path.exists(custom_img):
                try:
                    up_pil = Image.open(custom_img)
                    if is_clean_white_packshot(up_pil):
                        uw, uh = up_pil.size
                        grid_boxes = {
                            "outerwear": (0.04, 0.03, 0.36, 0.34),
                            "cap": (0.04, 0.35, 0.35, 0.56),
                            "bag": (0.02, 0.56, 0.45, 0.96),
                            "top": (0.36, 0.02, 0.98, 0.38),
                            "bottom": (0.44, 0.37, 0.95, 0.78),
                            "shoes": (0.45, 0.76, 0.96, 0.98),
                        }
                        for g_slot, (x0, y0, x1, y1) in grid_boxes.items():
                            sub_crop = up_pil.crop((int(uw * x0), int(uh * y0), int(uw * x1), int(uh * y1)))
                            cut_sub = _remove_white_bg_and_crop(sub_crop)
                            auto_cut_path = f"output/tg_auto_{g_slot}.png"
                            cut_sub.save(auto_cut_path, format="PNG")
                            if g_slot in items:
                                items[g_slot]["local_asset"] = auto_cut_path
                        print(f"  ★ [TELEGRAM FLAT-LAY GÖRSEL] 6 ürün otomatik dekupe edildi: {custom_img}")
                    else:
                        model_frames = [custom_img, custom_img, custom_img]
                        print(f"  ★ [TELEGRAM ÖZEL MODEL GÖRSELİ] Model karesi olarak ayarlandı: {custom_img}")
                except Exception as img_e:
                    print(f"[Telegram Görsel İşleme Uyarısı] {img_e}")

            if ov.get("custom_title"):
                archetype_title = ov["custom_title"]

            os.remove(override_path)
        except Exception as e:
            print(f"[Telegram Override Uyarısı] {e}")

    total_price = sum(float(v.get("price_val", 0.0)) for v in items.values())
    total_price_str = _format_price_tr(total_price)

    hook_packs = [
        {
            "hook_title": "Bordo & Koyu Kahve Peluş Deri Mont: Sonbaharın En Viral 2K Kapsül Kombini 🔥🍂✨",
            "spoken_hook_text": "Sonbaharda girdiğin her ortamda dönüp baktıracak o bordo ve kahve kapsül kombin!",
            "x_short_hook": "Bordo & Kahve Peluş Deri Mont: Sonbaharın en viral kombini 🔥🍂",
            "yt_short_title": "Bordo & Koyu Kahve Peluş Deri Mont: Sonbaharın En Viral 2K Kapsül Kombini 🔥🍂✨",
            "tiktok_hook_title": "POV: Sonbaharda girdiğin her ortamda dönüp baktıracak o bordo & kahve kombin 🔥🍂",
            "pinterest_title": "Koyu Kahve Peluş Deri Mont, Bordo Triko Kazak & Antrasit Palazzo Pantolon Kombini | GuzelAI.com",
            "viral_hook": "🛑 Bordo triko kazak, içi peluş koyu kahve deri mont, kemerli antrasit palazzo pantolon ve bordo Adidas Spezial uyumu! Önce guzelai.com'da doğrulanan 6 parçalık 2K kapsül kombin! 👇🔥",
            "video_badge_collage": "» GÜZELAİ.COM DOĞRULANMIŞ 2K KOMBİN «",
            "video_badge_walk": "» BORDO & KAHVE SOKAK STİLİ DURUŞU «",
        },
        {
            "hook_title": "Tesla'nın dik pistinden bile düşmeden indiren o Cadılar Bayramı kombini 🎃🔥✨",
            "spoken_hook_text": "Cadılar Bayramı gecesi bu dik pistten bile düşmeden kombinimle iniyorum!",
            "x_short_hook": "Bu dik pistten bile düşmeden indiren Cadılar Bayramı kombini 🎃🔥",
            "yt_short_title": "Tesla'nın dik pistinden bile düşmeden indiren o Cadılar Bayramı kombini 🎃🔥✨",
            "tiktok_hook_title": "POV: Kahvelerin uçmadığı o dik pistten Cadılar Bayramı kombinimle düşmeden iniyorum 🎃🔥",
            "pinterest_title": "Cadılar Bayramı Siyah Deri Ceket & Bordo Triko & Palazzo Pantolon Kadın Kombini | GuzelAI.com",
            "viral_hook": "🛑 Kahvelerin ve pizzaların bile uçmadan indiği o meşhur dik pistte Cadılar Bayramı şovumuz! Siyah oversize deri ceket, bordo dik yaka triko ve antrasit palazzo pantolonla yerçekimine meydan okuyan 6 kadın parçası! 👇🎃🔥",
            "video_badge_collage": "» CADILAR BAYRAMI PİST KOMBİNİM «",
            "video_badge_walk": "» DÜŞMEDEN PİSTTEN İNİŞ ŞOVU «",
        },
        {
            "hook_title": "İç sesim bir dakika bile susmadığı için gün boyu böyleyim 😭✨ (Ama kombinimden asla ödün vermem)",
            "spoken_hook_text": "İç sesim bir dakika bile susmadığı için gün boyu böyleyim ama kombinimden ödün vermem!",
            "x_short_hook": "İç sesim bir dk bile susmadığı için gün boyu böyleyim 😭✨",
            "yt_short_title": "İç sesim bir dakika bile susmadığı için gün boyu böyleyim 😭✨ Kombin Sırrı",
            "tiktok_hook_title": "POV: İç sesim bir dakika bile susmadığı için gün boyu sokakta böyle geziyorum 😭✨",
            "pinterest_title": "Siyah Kaşe Bomber Ceket & Taş Rengi Palazzo Jean Kadın Sonbahar Kombini | GuzelAI.com",
            "viral_hook": "🛑 Kafamın içinde 40 tilki dönerken dışarıya verdiğim 'Her şey kontrol altında' imajı! Siyah kaşe bomber ceket ve taş rengi yüksek bel palazzo jean ile gün boyu kurtarıcı 6 kadın parçası! 👇🔥",
            "video_badge_collage": "» İÇ SESİM HİÇ SUSMAZKEN BEN «",
            "video_badge_walk": "» AMA KOMBİNİM 10/10 OLMAK ZORUNDA «",
        },
        {
            "hook_title": "Kafamın içinde 40 tilki dönerken dışarıya verdiğim 'Her şey yolunda' kombini 🦊☕✨",
            "spoken_hook_text": "Kafamın içinde kırk tilki dönerken dışarıya verdiğim her şey yolunda kombini!",
            "x_short_hook": "Kafamda 40 tilki dönerken dışarıya verdiğim şıklık 🦊✨",
            "yt_short_title": "Kafamın içinde 40 tilki dönerken dışarıya verdiğim 'Her şey yolunda' kombini 🦊✨",
            "tiktok_hook_title": "POV: Kafamın içi kaosken dışarıya verdiğim 'Her şey kontrol altında' kombini 🦊☕",
            "pinterest_title": "Kadın Sonbahar Sokak Stili: Siyah Bomber Ceket & Bol Paça Jean Kombin Önerisi",
            "viral_hook": "🛑 'Giyecek hiçbir şeyim yok' krizinden 5 dakika sonra sokağa çıkarken ben! Boyu 10 cm uzun gösteren o 6 parçalık kurtarıcı kadın kombini! 👇🤍",
            "video_badge_collage": "» KAFAMIN İÇİ KAOSKEN KOMBİNİM «",
            "video_badge_walk": "» SOKAKTAKİ DURUŞU EFSANE «",
        },
    ]
    if archetype["id"] == "veor_uranis_bordo_kapsul_2k":
        chosen_hook_pack = hook_packs[0]
    elif archetype["id"] == "tesla_halloween_ramp_curly":
        chosen_hook_pack = hook_packs[1]
    elif archetype["id"] == "inner_voice_black_bomber_stone_palazzo":
        chosen_hook_pack = hook_packs[2]
    else:
        chosen_hook_pack = rng.choice(hook_packs)
    archetype_title = archetype.get("title") or chosen_hook_pack["hook_title"]

    return {
        "slot": slot_name,
        "is_trial": False,
        "archetype_id": archetype["id"],
        "archetype_title": archetype_title,
        "preferred_music_id": archetype.get("preferred_music_id", "veor_uranis_da_da_da_2026"),
        "hook_title": chosen_hook_pack["hook_title"],
        "spoken_hook_text": archetype.get("spoken_hook_text") or chosen_hook_pack.get("spoken_hook_text", ""),
        "x_short_hook": chosen_hook_pack["x_short_hook"],
        "yt_short_title": chosen_hook_pack["yt_short_title"],
        "tiktok_hook_title": chosen_hook_pack["tiktok_hook_title"],
        "pinterest_title": chosen_hook_pack["pinterest_title"],
        "viral_hook": chosen_hook_pack["viral_hook"],
        "video_badge_collage": chosen_hook_pack["video_badge_collage"],
        "video_badge_walk": chosen_hook_pack["video_badge_walk"],
        "ramp_empty_bg": archetype.get("ramp_empty_bg"),
        "ramp_model_cutout": archetype.get("ramp_model_cutout"),
        "seo_note": archetype.get(
            "seo_note",
            "📌 Not: Videodaki %100 Kadın kombin parçaları önce guzelai.com üzerinde görsel ve renk olarak doğrulanmış olup tüm ürün linkleri guzelai.com/go/ üzerinden doğrudan ilgili mağazaya yönlendirilmektedir:",
        ),
        "timestamp": datetime.utcnow().isoformat(),
        "items": items,
        "total_price_val": total_price,
        "total_price_str": total_price_str,
        "model_frames": model_frames,
    }

