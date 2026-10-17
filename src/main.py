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


def build_caption(outfit: dict) -> str:
    items = outfit["items"]
    total_str = outfit.get("total_price_str", "")
    music_name = outfit.get("music_info", {}).get("name", "Runway Deep House Mix")
    hook_title = (
        outfit.get("hook_title")
        or outfit.get("archetype_title")
        or "5.000₺ Bütçeyle 50.000₺'lik 'Old Money' Görünmenin Sırrı! (4. Parçaya Dikkat) 🔥"
    )
    viral_hook = outfit.get(
        "viral_hook",
        "🛑 SAKIN GEÇME! Girdiğin her ortamda 'Üzerindekileri hangi lüks markadan aldın?' dedirten, boyu 10 cm daha uzun gösteren o 6 parçalık Old Money sırrı çözüldü! 👇✨",
    )
    seo_note = outfit.get(
        "seo_note",
        "📌 Not: Görseldeki kadın kombin parçalarının stokta olan birebir veya en yakın %100 Kadın mağaza muadil (benzer) ürün linkleri doğrulanarak aşağıda listelenmiştir:",
    )

    lines = [
        f"🔥 {hook_title}",
        "",
        viral_hook,
        "🎃 Ekim Sonbahar & Cadılar Bayramı (Halloween) Gece/Gündüz Davet Şıklığı | Old Money Kadın Stil Kodları",
        "Sizce bu kombin 10 üzerinden kaç? Yorumlara yazın 👇🤍",
        "",
        "🌐 GÖRSELLİ & DOĞRULANMIŞ E-TİCARET LİNK VİTRİNİ:",
        "👉 https://guzelai.com/#kombinler",
        "",
        seo_note,
        "",
        "🛍️ KOMBİN FİYAT & ÜRÜN DETAYLARI (%100 KADIN KOLEKSİYONU):",
        f"⌚ Saat/Üst: {items['outerwear']['brand']} - {items['outerwear']['name']} ({items['outerwear']['price']}) [Kod: {items['outerwear'].get('sku', '-')}]",
        f"✨ Küpe/Aksesuar: {items['cap']['brand']} - {items['cap']['name']} ({items['cap']['price']}) [Kod: {items['cap'].get('sku', '-')}]",
        f"👚 Gömlek/Üst: {items['top']['brand']} - {items['top']['name']} ({items['top']['price']}) [Kod: {items['top'].get('sku', '-')}]",
        f"👖 Pantolon/Alt: {items['bottom']['brand']} - {items['bottom']['name']} ({items['bottom']['price']}) [Kod: {items['bottom'].get('sku', '-')}]",
        f"👜 Çanta: {items['bag']['brand']} - {items['bag']['name']} ({items['bag']['price']}) [Kod: {items['bag'].get('sku', '-')}]",
        f"👠 Ayakkabı: {items['shoes']['brand']} - {items['shoes']['name']} ({items['shoes']['price']}) [Kod: {items['shoes'].get('sku', '-')}]",
        "",
        f"💰 TOPLAM KOMBİN: {total_str}",
        "",
        "🔗 DOĞRUDAN MAĞAZA ÜRÜN LİNKLERİ (BİREBİR / BENZER MUADİL):",
        f"⌚ Saat/Üst Linki: {items['outerwear']['product_url']}",
        f"✨ Aksesuar Linki: {items['cap']['product_url']}",
        f"👚 Gömlek/Üst Linki: {items['top']['product_url']}",
        f"👖 Pantolon Linki: {items['bottom']['product_url']}",
        f"👜 Çanta Linki: {items['bag']['product_url']}",
        f"👠 Ayakkabı Linki: {items['shoes']['product_url']}",
        "",
        "🌐 Görselli Doğrulanmış Mağaza Linkleri: https://guzelai.com/#kombinler",
        "💬 WhatsApp Kombin Kanalımız: https://whatsapp.com/channel/0029VbDetYc3mFYDwZSry016",
        "𝕏 X (Twitter) Kombin Zinciri: https://x.com/guzelaicom",
        "▶️ YouTube Shorts Kanalımız: https://www.youtube.com/@guzelaicom",
        f"🎵 Enstrüman & Müzik: {music_name} ({outfit.get('music_info', {}).get('instruments_desc', 'Çoklu Enstrüman Stüdyo Kaydı')})",
        f"🎙️ Sesli Hook: \"{outfit.get('music_info', {}).get('dialogue_q', '')} — {outfit.get('music_info', {}).get('dialogue_a', '')}\"",
        "📌 Kaydetmeyi ve kombin arkadaşına göndermeyi unutma!",
        "",
        TR_LEGAL_NOTICE_FULL,
        "",
        "#kadınkombin #kombinönerileri #oldmoneystil #sonbaharkombini #cadılarbayramı #halloweenkombin #ekimstili #palazzopantolon #satengömlek #trendyolkombin #ofisşıklığı #negiysem #kesfet #reelsinstagram #ootdtr",
    ]
    return "\n".join(lines)


def build_links_comment(outfit: dict) -> str:
    items = outfit["items"]
    viral_hook = outfit.get(
        "viral_hook",
        "🛑 Bu 6'lı kadın kombinini kaybetmemek için hemen kaydet! 👇✨",
    )
    seo_note = outfit.get(
        "seo_note",
        "📌 Görseldeki kombinin stokta olan birebir veya en yakın %100 Kadın mağaza muadil (benzer) ürün linkleri:",
    )
    lines = [
        viral_hook,
        "🛍️ KOMBİNDEKİ KADIN ÜRÜNLERİNİN DOĞRULANMIŞ MAĞAZA LİNKLERİ (BENZER MUADİL) 👇",
        "🌐 Görselli Doğrulanmış Mağaza Vitrini: https://guzelai.com/#kombinler",
        seo_note,
        "",
        f"⌚ Saat/Üst ({items['outerwear']['price']}): {items['outerwear']['product_url']}",
        f"✨ Aksesuar ({items['cap']['price']}): {items['cap']['product_url']}",
        f"👚 Gömlek/Üst ({items['top']['price']}): {items['top']['product_url']}",
        f"👖 Pantolon ({items['bottom']['price']}): {items['bottom']['product_url']}",
        f"👜 Çanta ({items['bag']['price']}): {items['bag']['product_url']}",
        f"👠 Ayakkabı ({items['shoes']['price']}): {items['shoes']['product_url']}",
        "",
        "💬 WhatsApp Kanalı: https://whatsapp.com/channel/0029VbDetYc3mFYDwZSry016",
        "𝕏 X (Twitter): https://x.com/guzelaicom",
        "▶️ YouTube Shorts: https://www.youtube.com/@guzelaicom",
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
