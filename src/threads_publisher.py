import os
import sys
import json
import time
import argparse
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TR_LEGAL_NOTICE_FULL = (
    "⚠️ YASAL UYARI: Reklam veya sponsorlu iş birliği içermez. "
    "Paylaşılan marka, fiyat ve mağaza linkleri tamamen kombin önerisi ve bilgilendirme amaçlıdır; "
    "Türkiye sosyal medya ve Ticaret Bakanlığı reklam mevzuatı gereği zorunlu #reklam #işbirliğiDeğildir"
)

TR_LEGAL_NOTICE_SHORT = (
    "⚠️ Yasal Uyarı: Reklam veya iş birliği içermez, tamamen kombin önerisidir (zorunlu #reklam)."
)


def _trim_to_threads_limit(text: str, limit: int = 495) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def build_threads_chain(outfit: dict, reel_url: str = "") -> dict:
    """
    Threads platformunun 500 karakter sınırına ve tıklanabilir link kartı (link_attachment)
    yapısına %100 uyumlu 3 parçalı zincir (flood) oluşturur.
    """
    items = outfit["items"]
    title = outfit.get("archetype_title", "Günün Kombin Önerisi")
    total_str = outfit.get("total_price_str", "")
    ig_link = reel_url.strip() or "https://www.instagram.com/guzelaicom/"

    post_1_lines = [
        f"✨ Günün Kombin Önerisi: {title} ({total_str})",
        "Sizce bu kombin 10 üzerinden kaç? 👇🤍",
        "",
        f"🎬 2K Reels Videosu & Detaylar: {ig_link}",
        "👇 Tüm parçaların doğrudan tıklanabilir mağaza linkleri alt yanıtlarda!",
        "",
        TR_LEGAL_NOTICE_SHORT,
        "#kombin #günlükkombin #ootdtr",
    ]
    post_1_text = _trim_to_threads_limit("\n".join(post_1_lines))

    post_2_lines = [
        "🛍️ Üst Giyim & Aksesuar Linkleri (1/2):",
        f"🧥 {items['outerwear']['brand']} ({items['outerwear']['price']}): {items['outerwear']['product_url']}",
        f"🕶️ {items['cap']['brand']} ({items['cap']['price']}): {items['cap']['product_url']}",
        f"👕 {items['top']['brand']} ({items['top']['price']}): {items['top']['product_url']}",
        "ℹ️ Reklam/iş birliği içermez, kombin önerisidir (zorunlu #reklam)",
    ]
    post_2_text = _trim_to_threads_limit("\n".join(post_2_lines))

    post_3_lines = [
        "🛍️ Alt Giyim, Çanta & Ayakkabı Linkleri (2/2):",
        f"👖 {items['bottom']['brand']} ({items['bottom']['price']}): {items['bottom']['product_url']}",
        f"👜 {items['bag']['brand']} ({items['bag']['price']}): {items['bag']['product_url']}",
        f"👟 {items['shoes']['brand']} ({items['shoes']['price']}): {items['shoes']['product_url']}",
        "ℹ️ Reklam/iş birliği içermez, kombin önerisidir (zorunlu #reklam)",
    ]
    post_3_text = _trim_to_threads_limit("\n".join(post_3_lines))

    posts = [
        {
            "step": 1,
            "role": "main_post",
            "text": post_1_text,
            "char_count": len(post_1_text),
            "link_attachment": ig_link,
        },
        {
            "step": 2,
            "role": "reply_top_items",
            "text": post_2_text,
            "char_count": len(post_2_text),
            "link_attachment": items["outerwear"]["product_url"],
        },
        {
            "step": 3,
            "role": "reply_bottom_items",
            "text": post_3_text,
            "char_count": len(post_3_text),
            "link_attachment": items["shoes"]["product_url"],
        },
    ]

    return {
        "account": "@guzelaicom",
        "reel_url": ig_link,
        "legal_disclosure": TR_LEGAL_NOTICE_FULL,
        "posts": posts,
    }


def save_threads_outputs(outfit: dict, out_dir: str = "output", reel_url: str = "") -> dict:
    os.makedirs(out_dir, exist_ok=True)
    chain = build_threads_chain(outfit, reel_url=reel_url)

    json_path = os.path.join(out_dir, "threads_thread.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(chain, f, ensure_ascii=False, indent=2)

    txt_path = os.path.join(out_dir, "threads_post.txt")
    blocks = []
    for p in chain["posts"]:
        blocks.append(
            f"=== THREADS ADIM {p['step']} ({p['char_count']}/500 karakter | Önizleme Linki: {p['link_attachment']}) ===\n"
            f"{p['text']}"
        )
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(blocks) + "\n")

    print(f"[BAŞARILI] Threads için optimize edilmiş tıklanabilir link zinciri hazırlandı: {txt_path}")
    return chain


def publish_to_threads_api(chain: dict, access_token: str, threads_user_id: str) -> bool:
    """
    Meta Threads Graph API (graph.threads.net) üzerinden ana gönderiyi ve altındaki
    tıklanabilir ürün linki yanıtlarını (zincir/flood) otomatik olarak yayınlar.
    """
    base_url = f"https://graph.threads.net/v1.0/{threads_user_id}"
    reply_to_id = None

    for p in chain["posts"]:
        payload = {
            "media_type": "TEXT",
            "text": p["text"],
            "link_attachment": p["link_attachment"],
            "access_token": access_token,
        }
        if reply_to_id:
            payload["reply_to_id"] = reply_to_id

        r = requests.post(f"{base_url}/threads", data=payload, timeout=30)
        r.raise_for_status()
        creation_id = r.json()["id"]
        time.sleep(3)

        pub = requests.post(
            f"{base_url}/threads_publish",
            data={"creation_id": creation_id, "access_token": access_token},
            timeout=30,
        )
        pub.raise_for_status()
        published_id = pub.json()["id"]
        print(f"[Threads API] Adım {p['step']} yayınlandı! Thread ID: {published_id}")
        reply_to_id = published_id
        time.sleep(2)

    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outfit-json", default="output/outfit_links.json")
    parser.add_argument("--reel-url", default="")
    args = parser.parse_args()

    out_dir = os.path.dirname(args.outfit_json) or "output"
    with open(args.outfit_json, "r", encoding="utf-8") as f:
        outfit = json.load(f)

    reel_url = args.reel_url.strip() or outfit.get("reel_url", "")
    chain = save_threads_outputs(outfit, out_dir=out_dir, reel_url=reel_url)

    th_token = os.environ.get("THREADS_ACCESS_TOKEN", "").strip()
    th_user = os.environ.get("THREADS_USER_ID", "").strip()
    if th_token and th_user:
        try:
            publish_to_threads_api(chain, th_token, th_user)
        except Exception as e:
            print(f"[Threads API Uyarısı] {e}")


if __name__ == "__main__":
    main()
