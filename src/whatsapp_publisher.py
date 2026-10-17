"""
WhatsApp Channel Publisher & Integration for GuzelAI Medya
----------------------------------------------------------
Channel URL: https://whatsapp.com/channel/0029VbDetYc3mFYDwZSry016
Website Showcase URL: https://guzelai.com/#kombinler

Features:
1. Builds formatted WhatsApp Channel broadcast text (with bold *...* formatting,
   direct guzelai.com/#kombinler verified link showcase, 6 e-commerce store links,
   video links, and mandatory Turkish #reklam #işbirliğideğil legal disclosure).
2. Saves output/whatsapp_channel_post.txt and output/whatsapp_channel_post.json.
3. Supports automated posting via persistent local Chrome CDP (port 9235) if
   WhatsApp Web is paired on this trusted local machine.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

WHATSAPP_CHANNEL_URL = "https://whatsapp.com/channel/0029VbDetYc3mFYDwZSry016"
GUZELAI_SHOWCASE_URL = "https://guzelai.com/#kombinler"

ITEM_ORDER = [
    ("outerwear", "⌚ Saat/Üst"),
    ("cap", "✨ Küpe/Aksesuar"),
    ("top", "👚 Gömlek/Üst"),
    ("bottom", "👖 Pantolon"),
    ("bag", "👜 Çanta"),
    ("shoes", "👠 Ayakkabı"),
]

TR_WHATSAPP_LEGAL_NOTICE = (
    "⚖️ _Yasal Uyarı: Bu paylaşım reklam veya sponsorlu iş birliği içermez; "
    "tamamen kombin önerisi ve bilgilendirme amaçlıdır (zorunlu #reklam #işbirliğideğil)._"
)


def build_whatsapp_channel_message(
    outfit: Dict[str, Any],
    ig_reel_url: str = "",
    showcase_url: str = GUZELAI_SHOWCASE_URL,
) -> Dict[str, Any]:
    """Builds a WhatsApp Channel broadcast message with high-curiosity viral hooks and WhatsApp formatting."""
    title = (
        outfit.get("hook_title")
        or outfit.get("archetype_title")
        or outfit.get("title")
        or "5.000₺ Bütçeyle 50.000₺'lik 'Old Money' Görünmenin Sırrı! (4. Parçaya Dikkat) 🔥"
    )
    total_str = outfit.get("total_price_str", "")
    reel_link = ig_reel_url.strip() or outfit.get("reel_url", "") or "https://www.instagram.com/guzelaicom/"
    viral_hook = outfit.get(
        "viral_hook",
        "🛑 SAKIN GEÇME! Girdiğin her ortamda 'Üzerindekileri hangi lüks markadan aldın?' dedirten, boyu 10 cm daha uzun gösteren o 6 parçalık Old Money sırrı çözüldü! 👇✨",
    )
    seo_note = outfit.get(
        "seo_note",
        "📌 _Not: Görseldeki kadın kombin parçalarının stokta olan birebir veya en yakın %100 Kadın mağaza muadil (benzer) ürün linkleri doğrulanarak aşağıda listelenmiştir:_",
    )

    lines = [
        f"🔥 *{title}*",
        "",
        f"{viral_hook}",
        "",
        "🎃 _Ekim Sonbahar & Cadılar Bayramı (Halloween) Gece/Gündüz Şıklığı | %100 Kadın Old Money Kombin_",
        f"💰 *Toplam Kombin:* {total_str} — Sizce 10 üzerinden kaç? ❤️🔥👍 tepkilerinizi bırakın! 👇",
        "",
        f"🌐 *Görselli & Videolu Doğrulanmış E-Ticaret Link Vitrini:*",
        f"👉 {showcase_url}",
        "",
        seo_note,
        "",
        "🛍️ *GÖRSELLİ ÜRÜN DETAYLARI VE DOĞRUDAN MAĞAZA LİNKLERİ:*",
    ]

    items = outfit.get("items", {})
    if isinstance(items, dict):
        for key, label in ITEM_ORDER:
            it = items.get(key)
            if not isinstance(it, dict):
                continue
            brand = it.get("brand", "Mağaza")
            name = it.get("name", "Ürün")
            price = it.get("price", "")
            sku = it.get("sku") or it.get("code") or "-"
            url = it.get("product_url") or it.get("url") or ""
            lines.append(f"{label}: *{brand}* {name} — *{price}* (`Kod: {sku}`)")
            if url:
                lines.append(f"🔗 {url}")

    lines.extend([
        "",
        f"🎬 *Instagram Reels:* {reel_link}",
        "🎵 *TikTok:* https://www.tiktok.com/@guzelaicom",
        "▶️ *YouTube Shorts:* https://www.youtube.com/@guzelaicom/shorts",
        f"💬 *WhatsApp Kanalımız:* {WHATSAPP_CHANNEL_URL}",
        "",
        TR_WHATSAPP_LEGAL_NOTICE,
    ])

    message_text = "\n".join(lines)
    return {
        "channel_url": WHATSAPP_CHANNEL_URL,
        "showcase_url": showcase_url,
        "title": title,
        "total_price_str": total_str,
        "ig_reel_url": reel_link,
        "message": message_text,
    }


def save_whatsapp_outputs(
    outfit: Dict[str, Any],
    out_dir: str = "output",
    ig_reel_url: str = "",
) -> Dict[str, Any]:
    os.makedirs(out_dir, exist_ok=True)
    payload = build_whatsapp_channel_message(outfit, ig_reel_url=ig_reel_url)

    json_path = os.path.join(out_dir, "whatsapp_channel_post.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    txt_path = os.path.join(out_dir, "whatsapp_channel_post.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(payload["message"] + "\n")

    print(f"💬 [WhatsApp Kanalı] Yayın metni ve doğrulanmış linkler hazırlandı: {txt_path}")
    return payload


def publish_to_whatsapp_cdp(
    outfit: Dict[str, Any],
    media_path: Optional[Path] = None,
    ig_reel_url: str = "",
    cdp_port: int = 9230,
) -> Dict[str, Any]:
    """Publishes the Short Graph-Motion Video, Visual Product Link Cards, and Kombin broadcast to the WhatsApp Channel via active WhatsApp Web CDP."""
    import base64
    import time
    import requests
    import websocket

    payload = build_whatsapp_channel_message(outfit, ig_reel_url=ig_reel_url)
    message_text = payload["message"]
    title = payload["title"]

    try:
        tabs = requests.get(f"http://127.0.0.1:{cdp_port}/json", timeout=3).json()
    except Exception as e:
        return {"status": "cdp_unavailable", "error": str(e)}

    wa_tab = next((t for t in tabs if "web.whatsapp.com" in t.get("url", "")), None)
    if not wa_tab:
        try:
            wa_tab = requests.put(f"http://127.0.0.1:{cdp_port}/json/new?https://web.whatsapp.com/", timeout=5).json()
            time.sleep(10)
        except Exception as e:
            return {"status": "no_whatsapp_tab", "error": str(e)}

    ws = websocket.create_connection(wa_tab["webSocketDebuggerUrl"], timeout=60)
    msg_id = 0

    def cdp(method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        nonlocal msg_id
        msg_id += 1
        ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        while True:
            resp = json.loads(ws.recv())
            if resp.get("id") == msg_id:
                return resp.get("result", {})

    def pump(sec: float) -> None:
        end_t = time.time() + sec
        while time.time() < end_t:
            try:
                cdp("Page.captureScreenshot", {"format": "jpeg", "quality": 20})
            except Exception:
                pass
            time.sleep(0.5)

    def _paste_and_send_media(file_path: Path, mime_type: str, caption_str: str) -> bool:
        """Pastes an image or video file into the active WhatsApp Channel composer, attaches caption, and clicks Send."""
        if not file_path.exists():
            return False
        try:
            b64_data = base64.b64encode(file_path.read_bytes()).decode("ascii")
            fname = file_path.name
            paste_js = f"""(() => {{
                const b64 = "{b64_data}";
                const bin = atob(b64);
                const arr = new Uint8Array(bin.length);
                for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
                const file = new File([arr], "{fname}", {{ type: "{mime_type}" }});
                const dt = new DataTransfer();
                dt.items.add(file);
                const eds = Array.from(document.querySelectorAll('div[contenteditable="true"]'));
                const target = eds.filter(e => e.getBoundingClientRect().y > 300).pop() || document.querySelector('#main') || document.body;
                target.focus();
                const pasteEvt = new ClipboardEvent('paste', {{ bubbles: true, cancelable: true, clipboardData: dt }});
                target.dispatchEvent(pasteEvt);
                return true;
            }})()"""
            cdp("Runtime.evaluate", {"expression": paste_js, "returnByValue": True})
            pump(3.5)

            # Find caption input in media preview modal and insert caption_str
            cap_res = json.loads(cdp("Runtime.evaluate", {
                "expression": """JSON.stringify((() => {
                    const eds = Array.from(document.querySelectorAll('div[contenteditable="true"]'));
                    const cap = eds.filter(e => e.getBoundingClientRect().y > 250).pop();
                    if (!cap) return {found: false};
                    cap.focus();
                    const r = cap.getBoundingClientRect();
                    return {found: true, x: r.x + r.width/2, y: r.y + r.height/2};
                })())""",
                "returnByValue": True,
            }).get("result", {}).get("value", "{}") or "{}")

            if cap_res.get("found"):
                cdp("Input.dispatchMouseEvent", {"type": "mousePressed", "x": cap_res["x"], "y": cap_res["y"], "button": "left", "clickCount": 1})
                cdp("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": cap_res["x"], "y": cap_res["y"], "button": "left", "clickCount": 1})
                time.sleep(0.3)
                for idx, line in enumerate(caption_str.split("\n")):
                    if idx > 0:
                        cdp("Input.dispatchKeyEvent", {"type": "keyDown", "modifiers": 8, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
                        cdp("Input.dispatchKeyEvent", {"type": "keyUp", "modifiers": 8, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
                    if line:
                        cdp("Input.insertText", {"text": line})
                time.sleep(1.0)

            # Click the Send button or press Enter
            cdp("Runtime.evaluate", {
                "expression": """(() => {
                    const sendIcon = document.querySelector('span[data-icon="send"], span[data-icon="wds-ic-send-filled"], [aria-label="Gönder"], [aria-label="Send"]');
                    const sendBtn = sendIcon ? (sendIcon.closest('div[role="button"]') || sendIcon.closest('button') || sendIcon) : null;
                    if (sendBtn) sendBtn.click();
                })()"""
            })
            cdp("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
            cdp("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
            pump(4.0)
            return True
        except Exception as me:
            print(f"[WhatsApp Medya Gönderim Uyarısı] {file_path}: {me}")
            return False

    try:
        cdp("Page.enable")
        cdp("Runtime.enable")
        cdp("Input.enable")
        cdp("Page.bringToFront")
        cdp("Emulation.setPageScaleFactor", {"pageScaleFactor": 1.0})

        # 1. Click 'Kanallar' (Channels) icon in left sidebar
        cdp("Runtime.evaluate", {
            "expression": """(() => {
                const btn = document.querySelector('[aria-label="Kanallar"], [aria-label="Channels"], [title="Kanallar"]');
                if (btn) btn.click();
            })()"""
        })
        pump(3.0)

        # 2. Find 'guzelai.com' channel in the Channels drawer and click it
        ch_res = json.loads(cdp("Runtime.evaluate", {
            "expression": """JSON.stringify((() => {
                const spans = Array.from(document.querySelectorAll('span[dir="auto"], span[title]'));
                const exact = spans.find(e => /^guzelai\\.com$/i.test((e.innerText || e.getAttribute('title') || '').trim()));
                const target = exact ? (exact.closest('div[role="listitem"]') || exact.closest('div[role="button"]') || exact) : null;
                if (target) {
                    target.click();
                    const r = target.getBoundingClientRect();
                    return {clicked: true, name: 'guzelai.com', x: r.x + r.width/2, y: r.y + r.height/2};
                }
                return {clicked: false};
            })())""",
            "returnByValue": True,
        }).get("result", {}).get("value", "{}") or "{}")

        if ch_res.get("clicked") and ch_res.get("x") and ch_res.get("y"):
            cdp("Input.dispatchMouseEvent", {"type": "mousePressed", "x": ch_res["x"], "y": ch_res["y"], "button": "left", "clickCount": 1})
            cdp("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": ch_res["x"], "y": ch_res["y"], "button": "left", "clickCount": 1})
            pump(2.5)

        # 3. Focus the channel message composer (contenteditable)
        comp_res = json.loads(cdp("Runtime.evaluate", {
            "expression": """JSON.stringify((() => {
                const eds = Array.from(document.querySelectorAll('div[contenteditable="true"]'));
                const comp = eds.filter(e => e.getBoundingClientRect().y > 300).pop() || eds.pop();
                if (!comp) return {found: false, count: eds.length};
                comp.focus();
                const r = comp.getBoundingClientRect();
                return {found: true, x: r.x + r.width/2, y: r.y + r.height/2};
            })())""",
            "returnByValue": True,
        }).get("result", {}).get("value", "{}") or "{}")

        if not comp_res.get("found"):
            return {"status": "composer_not_found", "channel_scan": ch_res}

        cx, cy = comp_res["x"], comp_res["y"]
        cdp("Input.dispatchMouseEvent", {"type": "mousePressed", "x": cx, "y": cy, "button": "left", "clickCount": 1})
        cdp("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": cx, "y": cy, "button": "left", "clickCount": 1})
        time.sleep(0.4)

        # 3A. Send Short Graph-Motion Video (output/graphmotion_short.mp4) with Viral Hook & Website Link
        gm_video = Path("output/graphmotion_short.mp4")
        video_sent = False
        if gm_video.exists():
            video_caption = (
                f"🔥 *{title}*\n"
                f"🎬 Kısa Graph-Motion Kombin Videosu & Üzerindeki Duruşu!\n"
                f"🌐 *Görselli & Doğrulanmış Mağaza Linkleri:* {GUZELAI_SHOWCASE_URL}\n"
                f"{TR_WHATSAPP_LEGAL_NOTICE}"
            )
            video_sent = _paste_and_send_media(gm_video, "video/mp4", video_caption)

        # 3B. Send Visual Product Collage + Master Product Links (output/kombin_collage.png)
        collage_img = Path("output/kombin_collage.png")
        collage_sent = False
        if collage_img.exists():
            collage_sent = _paste_and_send_media(collage_img, "image/png", message_text)

        # 3C. Also send Individual Visual Product Cards (output/item_card_{key}.jpg) with each product's direct link!
        items_dict = outfit.get("items", {})
        cards_sent = 0
        if isinstance(items_dict, dict):
            for key, label in ITEM_ORDER:
                it = items_dict.get(key)
                if not isinstance(it, dict):
                    continue
                card_file = Path(f"output/item_card_{key}.jpg")
                p_url = it.get("product_url") or it.get("url") or ""
                if card_file.exists() and p_url:
                    card_cap = (
                        f"{label}: *{it.get('brand', '')}* — {it.get('name', '')}\n"
                        f"💰 *Fiyat:* {it.get('price', '')} (`Kod: {it.get('sku', '-')}`)\n"
                        f"🔗 *Doğrudan Ürün Linki:* {p_url}\n"
                        f"🌐 *Tüm Kombin:* {GUZELAI_SHOWCASE_URL}"
                    )
                    if _paste_and_send_media(card_file, "image/jpeg", card_cap):
                        cards_sent += 1

        # 3D. If collage wasn't sent as media caption, send the full text message directly
        if not collage_sent:
            for idx, line in enumerate(message_text.split("\n")):
                if idx > 0:
                    cdp("Input.dispatchKeyEvent", {"type": "keyDown", "modifiers": 8, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
                    cdp("Input.dispatchKeyEvent", {"type": "keyUp", "modifiers": 8, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
                if line:
                    cdp("Input.insertText", {"text": line})
            time.sleep(1.5)
            cdp("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
            cdp("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
            pump(3.0)

        return {
            "status": "published",
            "channel_name": ch_res.get("name", "WhatsApp Channel"),
            "channel_url": WHATSAPP_CHANNEL_URL,
            "graphmotion_video_sent": video_sent,
            "collage_sent": collage_sent,
            "visual_product_cards_sent": cards_sent,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        try:
            ws.close()
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outfit-json", default="output/outfit_links.json")
    parser.add_argument("--ig-reel-url", default="")
    parser.add_argument("--publish", action="store_true", help="WhatsApp Web üzerinden kanala canlı gönder")
    args = parser.parse_args()

    if not os.path.exists(args.outfit_json):
        print(f"[HATA] Kombin JSON bulunamadı: {args.outfit_json}")
        sys.exit(1)

    with open(args.outfit_json, "r", encoding="utf-8") as f:
        outfit = json.load(f)

    out_dir = os.path.dirname(args.outfit_json) or "output"
    ig_url = args.ig_reel_url or outfit.get("reel_url", "")
    res = save_whatsapp_outputs(outfit, out_dir=out_dir, ig_reel_url=ig_url)
    if args.publish:
        pub = publish_to_whatsapp_cdp(outfit, ig_reel_url=ig_url)
        print(json.dumps(pub, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": "ready", "channel_url": res["channel_url"], "showcase_url": res["showcase_url"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
