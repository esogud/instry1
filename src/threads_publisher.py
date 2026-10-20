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
    title = (
        outfit.get("hook_title")
        or outfit.get("archetype_title")
        or "5.000₺ Bütçeyle 50.000₺'lik 'Old Money' Görünmenin Sırrı! 🔥"
    )
    total_str = outfit.get("total_price_str", "")
    ig_link = reel_url.strip() or "https://www.instagram.com/guzelaicom/"

    post_1_lines = [
        f"🔥 {title} ({total_str})",
        "🎃 Sonbahar & Cadılar Bayramı Şıklığı | %100 Kadın (Benzer Muadil)",
        f"🌐 Görselli & Videolu Linkler: https://guzelai.com/#kombinler",
        f"💬 WhatsApp Kanalı: https://whatsapp.com/channel/0029VbDetYc3mFYDwZSry016",
        f"🎬 Reels: {ig_link}",
        "👇 Tüm ürün linkleri alt yanıtlarda!",
        TR_LEGAL_NOTICE_SHORT,
        "#kadınkombin #oldmoneystil #ootdtr",
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
            "link_attachment": "https://guzelai.com/#kombinler",
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


def publish_to_threads_cdp(chain: dict, cdp_port: int = 9228) -> str:
    """Publishes main Threads post via persistent local Chrome CDP session (ig_chrome_profile2)."""
    import subprocess
    from pathlib import Path
    from urllib.parse import quote
    import websocket

    profile_dir = Path(r"C:\Users\zenci\.gemini\antigravity\scratch\ig_chrome_profile2")
    profile_dir.mkdir(parents=True, exist_ok=True)
    try:
        tabs = requests.get(f"http://127.0.0.1:{cdp_port}/json", timeout=2).json()
    except Exception:
        chrome_cmd = (
            f'"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" '
            f'--remote-debugging-port={cdp_port} '
            f'--remote-allow-origins=* '
            f'--user-data-dir="{profile_dir}" '
            f'--no-first-run --no-default-browser-check '
            f'--disable-blink-features=AutomationControlled '
            f'--window-size=1200,900 "https://www.threads.com/"'
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"Invoke-WmiMethod -Class Win32_Process -Name Create -ArgumentList '{chrome_cmd}'"],
            capture_output=True,
        )
        for _ in range(15):
            time.sleep(1)
            try:
                tabs = requests.get(f"http://127.0.0.1:{cdp_port}/json", timeout=2).json()
                if any(t.get("type") == "page" for t in tabs):
                    break
            except Exception:
                pass
        else:
            return ""

    page_tab = next((t for t in tabs if t.get("type") == "page"), None)
    if not page_tab:
        return ""

    ws = websocket.create_connection(page_tab["webSocketDebuggerUrl"], timeout=25)
    msg_id = 0

    def cdp(method: str, params: dict | None = None) -> dict:
        nonlocal msg_id
        msg_id += 1
        ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        while True:
            resp = json.loads(ws.recv())
            if resp.get("id") == msg_id:
                return resp.get("result", {})

    def pump_frames(seconds: float) -> None:
        end_t = time.time() + seconds
        while time.time() < end_t:
            try:
                cdp("Page.captureScreenshot", {"format": "jpeg", "quality": 20})
            except Exception:
                pass
            time.sleep(0.5)

    try:
        cdp("Page.enable")
        cdp("Runtime.enable")
        cdp("Input.enable")
        cdp("Page.bringToFront")

        main_text = chain["posts"][0]["text"]
        intent_url = f"https://www.threads.com/intent/post?text={quote(main_text)}"
        cdp("Page.navigate", {"url": intent_url})
        pump_frames(6)

        # If Threads prompts "Instagram hesabını kullan" / "Instagram ile devam et" / "Continue with Instagram", click it
        sso_res = json.loads(cdp("Runtime.evaluate", {
            "expression": """JSON.stringify((() => {
                const btns = Array.from(document.querySelectorAll('div[role="button"], button, a, span'));
                const sso = btns.find(b => /Instagram hesab|Instagram ile|Continue with Instagram|guzelaicom/i.test((b.innerText || '').trim()));
                if (sso && !/Paylaş|Post/i.test(sso.innerText || '')) {
                    const r = sso.getBoundingClientRect();
                    sso.click();
                    return {clicked: true, x: r.left + r.width/2, y: r.top + r.height/2};
                }
                return {clicked: false};
            })())""",
            "returnByValue": True,
        }).get("result", {}).get("value", "{}") or "{}")
        if sso_res.get("clicked"):
            sx, sy = sso_res.get("x", 0), sso_res.get("y", 0)
            if sx and sy:
                cdp("Input.dispatchMouseEvent", {"type": "mousePressed", "x": sx, "y": sy, "button": "left", "clickCount": 1})
                cdp("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": sx, "y": sy, "button": "left", "clickCount": 1})
            pump_frames(8)
            cdp("Page.navigate", {"url": intent_url})
            pump_frames(6)

        post_res = json.loads(cdp("Runtime.evaluate", {
            "expression": """JSON.stringify((() => {
                const btns = Array.from(document.querySelectorAll('div[role="button"], button'));
                const p = btns.find(b => /^(Paylaş|Post)$/i.test((b.innerText || '').trim()));
                if (!p) return {clicked: false};
                const r = p.getBoundingClientRect();
                p.click();
                return {clicked: true, x: r.left + r.width/2, y: r.top + r.height/2};
            })())""",
            "returnByValue": True,
        }).get("result", {}).get("value", "{}") or "{}")

        if post_res.get("clicked"):
            x, y = post_res.get("x", 0), post_res.get("y", 0)
            if x and y:
                cdp("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
                cdp("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})
            pump_frames(5)
            print("[BAŞARILI - Threads CDP] @guzelaicom Threads paylaşımı tamamlandı.")
            return "https://www.threads.net/@guzelaicom"
        return ""
    finally:
        try:
            ws.close()
        except Exception:
            pass


def publish_via_threads_session(chain: dict, session_str: str) -> str:
    """
    Instagram sessionid çerezini kullanarak (veya yerel Chrome CDP yedeği ile)
    Threads üzerinde ana gönderiyi ve tıklanabilir ürün linki zincirini otomatik paylaşır.
    """
    if not session_str:
        return publish_to_threads_cdp(chain)

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
        return publish_to_threads_cdp(chain)

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

        try:
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
                break
        except Exception:
            break

    if not root_url:
        return publish_to_threads_cdp(chain)
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
        else:
            publish_to_threads_cdp(chain)


if __name__ == "__main__":
    main()
