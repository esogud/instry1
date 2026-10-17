import os
import sys
import json
import argparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from outfit_generator import select_daily_outfit
from render_reels import render_kombin_reel
from threads_publisher import (
    TR_LEGAL_NOTICE_FULL,
    TR_LEGAL_NOTICE_SHORT,
    save_threads_outputs,
)
from telegram_publisher import save_telegram_outputs
from pinterest_publisher import save_pinterest_outputs
from youtube_publisher import save_youtube_outputs
from x_publisher import save_x_outputs
from whatsapp_publisher import save_whatsapp_outputs
from facebook_publisher import save_facebook_outputs
from tiktok_uploader import save_tiktok_outputs
from website_publisher import publish_to_guzelai_website


from quality_checker import inspect_rendered_reel_quality


def build_caption(outfit: dict) -> str:
    items = outfit["items"]
    total_str = outfit.get("total_price_str", "")
    music_name = outfit.get("music_info", {}).get("name", "Veor Uranis – Da Da Da Dadada (Viral Edit)")
    hook_title = (
        outfit.get("hook_title")
        or outfit.get("archetype_title")
        or "Bordo & Koyu Kahve Peluş Deri Mont: Sonbaharın En Viral 2K Kapsül Kombini 🔥🍂✨"
    )
    viral_hook = outfit.get(
        "viral_hook",
        "🛑 Önce guzelai.com'da doğrulanan 6 parçalık 2K kapsül kombin! 👇🔥",
    )
    seo_note = outfit.get(
        "seo_note",
        "📌 Not: Videodaki %100 Kadın kombin parçaları önce guzelai.com üzerinde görsel ve renk olarak doğrulanmış olup tüm ürün linkleri guzelai.com/go/ üzerinden doğrudan ilgili mağazaya yönlendirilmektedir:",
    )

    c_out = items["outerwear"].get("category_label", "Mont / Ceket")
    c_cap = items["cap"].get("category_label", "Gözlük / Aksesuar")
    c_top = items["top"].get("category_label", "Kazak / Üst")
    c_bot = items["bottom"].get("category_label", "Pantolon / Alt")
    c_bag = items["bag"].get("category_label", "Çanta")
    c_sho = items["shoes"].get("category_label", "Ayakkabı")

    u_out = items["outerwear"].get("guzelai_url") or items["outerwear"]["product_url"]
    u_cap = items["cap"].get("guzelai_url") or items["cap"]["product_url"]
    u_top = items["top"].get("guzelai_url") or items["top"]["product_url"]
    u_bot = items["bottom"].get("guzelai_url") or items["bottom"]["product_url"]
    u_bag = items["bag"].get("guzelai_url") or items["bag"]["product_url"]
    u_sho = items["shoes"].get("guzelai_url") or items["shoes"]["product_url"]

    cal = outfit.get("calendar_concept", {})
    cal_title = cal.get("concept_title", "17 Ekim Altın Sonbahar & Pinterest 'Old Money / Quiet Luxury' Hafta Sonu Zarafeti")
    cal_date = cal.get("date_label", "17 Ekim 2026 Cumartesi")
    palette_note = outfit.get(
        "color_palette_note",
        "Pinterest 'Old Money / Quiet Luxury' Sonbahar Renk Kurgusu: Camel Kruvaze Trençkot (#C8A98E) + Buz Mavisi Çizgili Gömlek (#A8C3D4) + Taba Kemerli Ekru Pantolon (#F3EFEA) + Acı Kahve & Gold Deri Detaylar (#4A2E1B)",
    )

    lines = [
        f"🔥 {hook_title}",
        "📌 'Bugün ne giysem?' krizinde saniyeler içinde kurtulmak için bu 2K Old Money kapsül kombini hemen KAYDET ve stil sahibi arkadaşına GÖNDER! 🤍✨",
        "",
        f"📅 TARİH & KONSEPT OTOMASYONU ({cal_date}): {cal_title}",
        f"🎨 PINTEREST RENK KURGUSU: {palette_note}",
        "",
        viral_hook,
        "",
        f"💬 STİL ANKETİ: Bu Old Money kombinde senin favori parçan {items['outerwear']['name']} mi yoksa {items['top']['name']} mu? Yorumlarda buluşalım 👇✨",
        "",
        "🌐 TÜM ÖRNEK KOMBİNLER & DOĞRULANMIŞ VİTRİN (Tek Tıkla İncele):",
        "👉 https://guzelai.com/#kombinler",
        "",
        seo_note,
        "",
        "🛍️ KOMBİN FİYAT, MARKA & ÜRÜN KODU DETAYLARI (%100 KADIN OLD MONEY KOLEKSİYONU):",
        f"1️⃣ 🧥 {c_out}: {items['outerwear']['brand']} – {items['outerwear']['name']} | Fiyat: {items['outerwear']['price']} | Ürün Kodu: {items['outerwear'].get('sku', '-')}",
        f"2️⃣ 🕶️ {c_cap}: {items['cap']['brand']} – {items['cap']['name']} | Fiyat: {items['cap']['price']} | Ürün Kodu: {items['cap'].get('sku', '-')}",
        f"3️⃣ 👚 {c_top}: {items['top']['brand']} – {items['top']['name']} | Fiyat: {items['top']['price']} | Ürün Kodu: {items['top'].get('sku', '-')}",
        f"4️⃣ 👖 {c_bot}: {items['bottom']['brand']} – {items['bottom']['name']} | Fiyat: {items['bottom']['price']} | Ürün Kodu: {items['bottom'].get('sku', '-')}",
        f"5️⃣ 👜 {c_bag}: {items['bag']['brand']} – {items['bag']['name']} | Fiyat: {items['bag']['price']} | Ürün Kodu: {items['bag'].get('sku', '-')}",
        f"6️⃣ 👠 {c_sho}: {items['shoes']['brand']} – {items['shoes']['name']} | Fiyat: {items['shoes']['price']} | Ürün Kodu: {items['shoes'].get('sku', '-')}",
        "",
        f"💰 TOPLAM 6 PARÇA KOMBİN BÜTÇESİ: {total_str}",
        "",
        "🔗 GÜZELAİ.COM DOĞRULANMIŞ MAĞAZA YÖNLENDİRME LİNKLERİ (100% Aktif & Doğrulanmış):",
        f"🧥 {c_out}: {u_out}",
        f"🕶️ {c_cap}: {u_cap}",
        f"👚 {c_top}: {u_top}",
        f"👖 {c_bot}: {u_bot}",
        f"👜 {c_bag}: {u_bag}",
        f"👠 {c_sho}: {u_sho}",
        "",
        "🔎 INSTAGRAM ARAMA & STİL REHBERİ (SEO):",
        "Pinterest Old Money sonbahar kadın kombin önerileri • Camel bej kruvaze kısa trençkot nasıl kombinlenir? • Buz mavisi çizgili gömlek ve taba kemerli ekru yüksek bel pileli bol paça kumaş pantolon kombinleri • Gold tokalı kahverengi deri çanta ve slingback topuklu ayakkabı ile sessiz lüks (Quiet Luxury) zarafeti.",
        "",
        f"🎵 Müzik: {music_name}",
        f"🎙️ Sesli Hook: \"{outfit.get('music_info', {}).get('dialogue_q', '')} — Detaylar guzelai.com'da!\"",
        "",
        TR_LEGAL_NOTICE_FULL,
        "",
        "#oldmoney #oldmoneystil #quietluxury #sonbaharkombini #kadınkombin #kombinönerileri #pinterestkombin #trençkotkombini #zarafet #şıklık #kapsülgardırop #negiysem #kesfet #reelsinstagram #guzelai",
    ]
    return "\n".join(lines)


def build_links_comment(outfit: dict) -> str:
    items = outfit["items"]
    viral_hook = outfit.get(
        "viral_hook",
        "🛑 Bu 6'lı kadın kombinini kaybetmemek için hemen kaydet! 👇✨",
    )
    lines = [
        "📌 KOMBİNDEKİ 6 KADIN PARÇASININ GÜZELAİ.COM DOĞRULANMIŞ LİNKLERİ & KODLARI 👇",
        viral_hook,
        "🌐 Tüm Örnek Kombinler & Görselli Alışveriş Vitrini: https://guzelai.com/#kombinler",
        "",
        f"1️⃣ 🧥 {items['outerwear']['name']} ({items['outerwear']['price']} | Kod: {items['outerwear'].get('sku', '-')}): {items['outerwear'].get('guzelai_url') or items['outerwear']['product_url']}",
        f"2️⃣ 🕶️ {items['cap']['name']} ({items['cap']['price']} | Kod: {items['cap'].get('sku', '-')}): {items['cap'].get('guzelai_url') or items['cap']['product_url']}",
        f"3️⃣ 👚 {items['top']['name']} ({items['top']['price']} | Kod: {items['top'].get('sku', '-')}): {items['top'].get('guzelai_url') or items['top']['product_url']}",
        f"4️⃣ 👖 {items['bottom']['name']} ({items['bottom']['price']} | Kod: {items['bottom'].get('sku', '-')}): {items['bottom'].get('guzelai_url') or items['bottom']['product_url']}",
        f"5️⃣ 👜 {items['bag']['name']} ({items['bag']['price']} | Kod: {items['bag'].get('sku', '-')}): {items['bag'].get('guzelai_url') or items['bag']['product_url']}",
        f"6️⃣ 👟 {items['shoes']['name']} ({items['shoes']['price']} | Kod: {items['shoes'].get('sku', '-')}): {items['shoes'].get('guzelai_url') or items['shoes']['product_url']}",
        "",
        "💬 Senin favorin kaç numaralı parça? (1-6 arası yoruma yaz 👇)",
        TR_LEGAL_NOTICE_SHORT,
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="output/daily_kombin_reel.mp4")
    args = parser.parse_args()

    out_dir = os.path.dirname(args.output) or "output"
    os.makedirs(out_dir, exist_ok=True)

    slot = os.environ.get("SLOT_NAME", "otomatik")
    watermark = os.environ.get("IG_WATERMARK", "@guzelaicom")

    outfit = select_daily_outfit(slot_name=slot)
    render_kombin_reel(outfit, args.output, watermark=watermark)

    # Otomatik Video & Ses Yapaylık / Kalite Kontrolü (Quality Gate)
    qc_report = inspect_rendered_reel_quality(
        outfit=outfit,
        frames_dir=os.path.join(out_dir, "_frames"),
        wav_path=os.path.join(out_dir, "viral_fashion_track.wav"),
        out_report_path=os.path.join(out_dir, "quality_check_report.json"),
    )
    outfit["quality_report"] = qc_report

    caption_path = os.path.join(out_dir, "caption.txt")
    with open(caption_path, "w", encoding="utf-8") as f:
        f.write(build_caption(outfit))

    comment_path = os.path.join(out_dir, "comment_links.txt")
    with open(comment_path, "w", encoding="utf-8") as f:
        f.write(build_links_comment(outfit))

    meta_path = os.path.join(out_dir, "outfit_links.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(outfit, f, ensure_ascii=False, indent=2)

    save_threads_outputs(outfit, out_dir=out_dir)
    save_telegram_outputs(outfit, out_dir=out_dir)
    save_pinterest_outputs(outfit, out_dir=out_dir)
    save_youtube_outputs(outfit, out_dir=out_dir)
    save_x_outputs(outfit, out_dir=out_dir)
    save_whatsapp_outputs(outfit, out_dir=out_dir)
    save_facebook_outputs(outfit, out_dir=out_dir)
    save_tiktok_outputs(outfit, out_dir=out_dir)
    publish_to_guzelai_website(outfit, out_dir=out_dir)

    print(f"[BAŞARILI] Açıklama, yasal uyarı ve doğrudan ürün linkleri hazırlandı: {caption_path}")


if __name__ == "__main__":
    main()
