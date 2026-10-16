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


def build_caption(outfit: dict) -> str:
    items = outfit["items"]
    total_str = outfit.get("total_price_str", "")
    music_name = outfit.get("music_info", {}).get("name", "Runway Deep House Mix")

    lines = [
        f"Günün Kombin Önerisi: {outfit.get('archetype_title', 'Sokak Stili')} ✨",
        "Sizce bu kombin 10 üzerinden kaç? Yorumlara yazın 👇🤍",
        "",
        "🛍️ KOMBİN FİYAT & ÜRÜN DETAYLARI:",
        f"🧥 Ceket: {items['outerwear']['brand']} - {items['outerwear']['name']} ({items['outerwear']['price']}) [Kod: {items['outerwear'].get('sku', '-')}]",
        f"🕶️ Aksesuar: {items['cap']['brand']} - {items['cap']['name']} ({items['cap']['price']}) [Kod: {items['cap'].get('sku', '-')}]",
        f"👕 Üst: {items['top']['brand']} - {items['top']['name']} ({items['top']['price']}) [Kod: {items['top'].get('sku', '-')}]",
        f"👖 Alt: {items['bottom']['brand']} - {items['bottom']['name']} ({items['bottom']['price']}) [Kod: {items['bottom'].get('sku', '-')}]",
        f"👜 Çanta: {items['bag']['brand']} - {items['bag']['name']} ({items['bag']['price']}) [Kod: {items['bag'].get('sku', '-')}]",
        f"👟 Ayakkabı: {items['shoes']['brand']} - {items['shoes']['name']} ({items['shoes']['price']}) [Kod: {items['shoes'].get('sku', '-')}]",
        "",
        f"💰 TOPLAM KOMBİN: {total_str}",
        "",
        "🔗 DOĞRUDAN ÜRÜN LİNKLERİ:",
        f"🧥 Ceket Linki: {items['outerwear']['product_url']}",
        f"🕶️ Aksesuar Linki: {items['cap']['product_url']}",
        f"👕 Üst Linki: {items['top']['product_url']}",
        f"👖 Pantolon Linki: {items['bottom']['product_url']}",
        f"👜 Çanta Linki: {items['bag']['product_url']}",
        f"👟 Ayakkabı Linki: {items['shoes']['product_url']}",
        "",
        f"🎵 Müzik: {music_name}",
        "📌 Kaydetmeyi ve kombin arkadaşına göndermeyi unutma!",
        "",
        "#kombin #günlükkombin #kombinönerileri #negiysem #sokakmodası #trendyolkombin #zarakombin #kesfet #reelsinstagram #ootdtr",
    ]
    return "\n".join(lines)


def build_links_comment(outfit: dict) -> str:
    items = outfit["items"]
    lines = [
        "🛍️ KOMBİNDEKİ ÜRÜNLERİN GÜNCEL LİNKLERİ VE KODLARI 👇",
        "",
        f"🧥 Ceket ({items['outerwear']['price']}): {items['outerwear']['product_url']}",
        f"🕶️ Aksesuar ({items['cap']['price']}): {items['cap']['product_url']}",
        f"👕 Üst ({items['top']['price']}): {items['top']['product_url']}",
        f"👖 Pantolon ({items['bottom']['price']}): {items['bottom']['product_url']}",
        f"👜 Çanta ({items['bag']['price']}): {items['bag']['product_url']}",
        f"👟 Ayakkabı ({items['shoes']['price']}): {items['shoes']['product_url']}",
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

    print(f"[BAŞARILI] Açıklama ve doğrudan ürün linkleri hazırlandı: {caption_path}")


if __name__ == "__main__":
    main()
