import os
import argparse
from outfit_generator import select_daily_outfit
from render_reels import render_kombin_reel


def build_caption(outfit: dict) -> str:
    items = outfit["items"]
    lines = [
        "Günün Kombin Önerisi ✨ Sizce bu kombin 10 üzerinden kaç? Yorumlara yazın 👇🤍",
        "",
        "🛍️ KOMBİN DETAYLARI:",
        f"🧥 Ceket: {items['outerwear']['brand']} - {items['outerwear']['price']}",
        f"🧢 Şapka: {items['cap']['brand']} - {items['cap']['price']}",
        f"👕 Sweatshirt: {items['top']['name']} - {items['top']['price']}",
        f"👖 Tayt/Pantolon: {items['bottom']['brand']} - {items['bottom']['price']}",
        f"👜 Çanta: {items['bag']['brand']} - {items['bag']['price']}",
        f"👟 Ayakkabı: {items['shoes']['brand']} - {items['shoes']['price']}",
        "",
        "📌 Kaydetmeyi ve kombin arkadaşına göndermeyi unutma!",
        "",
        "#kombin #günlükkombin #kombinönerileri #negiysem #sokakmodası #zarakombin #hmkombin #kesfet #reelsinstagram #ootdtr"
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="output/daily_kombin_reel.mp4")
    args = parser.parse_args()

    slot = os.environ.get("SLOT_NAME", "otomatik")
    watermark = os.environ.get("IG_WATERMARK", "@guzelaicom")

    outfit = select_daily_outfit(slot_name=slot)
    render_kombin_reel(outfit, args.output, watermark=watermark)

    caption_path = os.path.join(os.path.dirname(args.output), "caption.txt")
    with open(caption_path, "w", encoding="utf-8") as f:
        f.write(build_caption(outfit))
    print(f"[BAŞARILI] Açıklama metni hazırlandı: {caption_path}")


if __name__ == "__main__":
    main()
