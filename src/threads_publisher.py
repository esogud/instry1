import os
import sys
import re
import json
import time
import random
import argparse
from urllib.parse import unquote
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"

TR_LEGAL_NOTICE_FULL = (
    "⚠️ YASAL UYARI: Reklam veya sponsorlu iş birliği içermez. "
    "Paylaşılan marka, fiyat ve mağaza linkleri tamamen kombin önerisi ve bilgilendirme amaçlıdır; "
    "Türkiye sosyal medya ve Ticaret Bakanlığı reklam mevzuatı gereği zorunlu #reklam #işbirliğiDeğildir"
)

TR_LEGAL_NOTICE_SHORT = (
    "⚠️ Yasal Uyarı: Reklam veya iş birliği içermez, tamamen kombin önerisidir (zorunlu #reklam)."
)


def media_id_to_shortcode(media_id: int | str) -> str:
    mid = int(str(media_id).split("_")[0])
    shortcode = ""
    while mid > 0:
        rem = mid % 64
        shortcode = ALPHABET[rem] + shortcode
        mid = mid // 64
    return shortcode


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


def publish_via_threads_session(chain: dict, session_str: str) -> str:
    """
    Instagram sessionid çerezini kullanarak (ayrı bir şifreye gerek kalmadan)
    www.threads.net/api/v1/media/configure_text_only_post/ üzerinden
    ana gönderiyi ve altındaki tıklanabilir ürün linki zincirini otomatik paylaşır.
    """
    if not session_str:
        return ""

    raw = session_str.strip()
    if raw.startswith("{"):
        try:
            data = json.loads(raw)
            sid = data.get("cookies", {}).get("sessionid") or data.get("authorization_data", {}).get("sessionid") or ""
        except Exception:
            sid = ""
    else:
        sid = raw
    sid = unquote(sid.strip())
    if not sid:
        return ""

    user_match = re.search(r"^\d+", sid)
    viewer_id = user_match.group(0) if user_match else "46394512287"
    csrf = "gs7Zz2Zor02UJBDhPeDdrL6KUCvcT6zF"
    lsd = "AVqw_XEyRAI"
    cookie_str = f"sessionid={sid}; ds_user_id={viewer_id}; csrftoken={csrf}"

    headers = {
        "authority": "www.threads.net",
        "origin": "https://www.threads.net",
        "referer": "https://www.threads.net/",
        "content-type": "application/x-www-form-urlencoded",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "x-asbd-id": "129477",
        "x-ig-app-id": "238260118697367",
        "x-fb-lsd": lsd,
        "x-csrftoken": csrf,
        "cookie": cookie_str,
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    }

    parent_pk = None
    root_url = ""

    for idx, p in enumerate(chain.get("posts", [])):
        if idx > 0:
            time.sleep(random.uniform(3.2, 4.8))

        app_info = {"reply_control": 0}
        if parent_pk:
            app_info["reply_id"] = str(parent_pk)
        if p.get("link_attachment"):
            app_info["link_attachment_url"] = p["link_attachment"]

        payload = {
            "publish_mode": "text_post",
            "caption": p["text"][:500],
            "upload_id": str(int(time.time() * 1000)),
            "text_post_app_info": json.dumps(app_info),
        }

        r = requests.post(
            "https://www.threads.net/api/v1/media/configure_text_only_post/",
            headers=headers,
            data=payload,
            timeout=25,
        )
        if r.status_code == 200 and "media" in r.text:
            m = r.json().get("media", {})
            pk = str(m.get("pk", ""))
            code = m.get("code") or (media_id_to_shortcode(pk) if pk else "")
            post_url = f"https://www.threads.net/@guzelaicom/post/{code}"
            print(f"[BAŞARILI - Threads] Adım {p['step']} paylaşıldı! PK: {pk} | Link: {post_url}")
            if idx == 0:
                root_url = post_url
            if pk:
                parent_pk = pk
        else:
            print(f"[Threads Uyarısı] Adım {p['step']} ({r.status_code}): {r.text[:250]}")
            break

    return root_url


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
    parser.add_argument("--publish", action="store_true", help="Threads'te canlı yayınla")
    args = parser.parse_args()

    out_dir = os.path.dirname(args.outfit_json) or "output"
    with open(args.outfit_json, "r", encoding="utf-8") as f:
        outfit = json.load(f)

    reel_url = args.reel_url.strip() or outfit.get("reel_url", "")
    chain = save_threads_outputs(outfit, out_dir=out_dir, reel_url=reel_url)

    if args.publish:
        session_json = os.environ.get("IG_SESSION_JSON", "").strip()
        th_token = os.environ.get("THREADS_ACCESS_TOKEN", "").strip()
        th_user = os.environ.get("THREADS_USER_ID", "").strip()
        if session_json:
            publish_via_threads_session(chain, session_json)
        elif th_token and th_user:
            publish_to_threads_api(chain, th_token, th_user)


if __name__ == "__main__":
    main()
