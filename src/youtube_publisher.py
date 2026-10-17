"""
YouTube Shorts Auto-Publisher for @guzelaicom (https://www.youtube.com/@guzelaicom)
-----------------------------------------------------------------------------------
Features:
- Generates YouTube Shorts high-CTR viral hook title (<= 100 chars with #Shorts),
  never allowing generic filenames like 'daily kombin reel'.
- Copies the video to a sanitized viral-title filename before upload so YouTube Studio's
  automatic filename-to-title parser defaults directly to the viral hook title.
- Replaces title & description via CDP Input events + Range selection.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests
import websocket

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

YOUTUBE_CHANNEL_URL = "https://www.youtube.com/@guzelaicom"
YOUTUBE_EMAIL = os.environ.get("YOUTUBE_EMAIL", "mmehmetofficial@gmail.com")
YOUTUBE_PASSWORD = os.environ.get("YOUTUBE_PASSWORD", "V6R^!.-i-<-5K2t")
YOUTUBE_CDP_PORT = 9233
YOUTUBE_PROFILE_DIR = Path(r"C:\Users\zenci\.gemini\antigravity\scratch\youtube_chrome_profile")

TR_YOUTUBE_LEGAL_NOTICE = (
    "⚠️ YASAL UYARI: Bu video reklam veya sponsorlu iş birliği içermez. "
    "Paylaşılan marka, fiyat ve mağaza linkleri tamamen kombin önerisi ve bilgilendirme amaçlıdır; "
    "Türkiye sosyal medya ve Ticaret Bakanlığı reklam mevzuatı gereği zorunlu #reklam #işbirliğideğil"
)

ITEM_ORDER = [
    ("outerwear", "🧥 Dış Giyim / Üst"),
    ("cap", "🕶️ Gözlük / Aksesuar"),
    ("top", "👚 Triko / Üst"),
    ("bottom", "👖 Pantolon"),
    ("bag", "👜 Çanta"),
    ("shoes", "👟 Ayakkabı"),
]


def _safe_filename_from_title(title: str) -> str:
    """Converts a viral hook title into a valid Windows filename so YouTube never sees 'daily_kombin_reel'."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return (cleaned[:92] or "İç sesim bir dakika bile susmadığı için gün boyu böyleyim #Shorts") + ".mp4"


def build_youtube_short_data(outfit: Dict[str, Any], reel_url: str = "", threads_url: str = "") -> Dict[str, Any]:
    """Builds YouTube Shorts high-CTR title (<= 100 chars) and SEO description with store links."""
    raw_title = (
        outfit.get("yt_short_title")
        or outfit.get("hook_title")
        or outfit.get("archetype_title")
        or "İç sesim bir dakika bile susmadığı için gün boyu böyleyim 😭✨ (Kombin Sırrı)"
    )
    total_str = outfit.get("total_price_str", "")
    music_name = outfit.get("music_info", {}).get("name", "Çoklu Enstrüman Stüdyo Kaydı")
    instruments_desc = outfit.get("music_info", {}).get("instruments_desc", "")
    viral_hook = outfit.get(
        "viral_hook",
        "🛑 Kafamın içi bir dakika bile susmazken dışarıya verdiğim 'Her şey kontrol altında' kombini! 👇✨",
    )
    seo_note = outfit.get(
        "seo_note",
        "📌 Not: Videodaki %100 Kadın kombin parçalarının doğrulanmış mağaza ve benzer muadil ürün linkleri aşağıdadır:",
    )

    base_clean = raw_title.replace("#Shorts", "").strip()
    if len(base_clean) > 82:
        base_clean = base_clean[:80].rstrip()
    short_title = f"{base_clean} #Shorts #kombin"[:100]

    items = outfit.get("items", {})
    desc_lines = [
        f"🔥 {raw_title}",
        "🌐 GÖRSELLİ & DOĞRULANMIŞ ÜRÜN LİNKLERİ: https://guzelai.com/#kombinler",
        "",
        viral_hook,
        "⏱️ VİDEO BÖLÜMLERİ:",
        "0:00 6 Parça Graph-Motion Kombin Dizilimi & İç Sesim Hook",
        "0:05 Kıvırcık Model Sokak Stili Duruşu & Ürün Fiyatları",
        "",
        f"💰 TOPLAM KOMBİN FİYATI: {total_str}",
        seo_note,
        "",
        "🛍️ KOMBİNDEKİ %100 KADIN PARÇALAR VE DOĞRUDAN MAĞAZA LİNKLERİ:",
    ]

    if isinstance(items, dict):
        for key, label in ITEM_ORDER:
            it = items.get(key)
            if not it:
                continue
            brand = it.get("brand", "")
            name = it.get("name", "")
            price = it.get("price", "")
            sku = it.get("sku", "-")
            url = it.get("product_url") or it.get("url") or ""
            desc_lines.append(f"{label}: {brand} - {name} ({price}) [Kod: {sku}]")
            if url:
                desc_lines.append(f"🔗 Link: {url}")
            desc_lines.append("")

    ig_link = reel_url.strip() or outfit.get("reel_url", "") or "https://www.instagram.com/guzelaicom/"

    desc_lines.extend([
        "🌐 TÜM KANALLARIMIZ (GUZELAI MEDYA):",
        "🌐 Görselli Doğrulanmış Mağaza Vitrini: https://guzelai.com/#kombinler",
        "💬 WhatsApp Kombin Kanalı: https://whatsapp.com/channel/0029VbDetYc3mFYDwZSry016",
        f"📸 Instagram Reels: {ig_link}",
        "𝕏 X (Twitter): https://x.com/guzelaicom",
        f"🎵 Enstrüman & Ses: {music_name} ({instruments_desc})",
        "",
        TR_YOUTUBE_LEGAL_NOTICE,
        "",
        "#Shorts #kadınkombin #kombinönerileri #içsesim #sonbaharkombini #sokakstili #palazzopantolon #trendyolkombin #ootd #moda #guzelaicom",
    ])

    description = "\n".join(desc_lines)[:4950]

    return {
        "channel_url": YOUTUBE_CHANNEL_URL,
        "account_email": YOUTUBE_EMAIL,
        "title": short_title,
        "description": description,
        "tags": ["kombin", "kadın kombin", "iç sesim", "kombin önerileri", "moda", "ootd", "shorts", "guzelaicom"],
        "privacy_status": "PUBLIC",
        "made_for_kids": False,
    }


def save_youtube_outputs(outfit: Dict[str, Any], out_dir: str = "output", reel_url: str = "", threads_url: str = "") -> Dict[str, Any]:
    os.makedirs(out_dir, exist_ok=True)
    yt_data = build_youtube_short_data(outfit, reel_url=reel_url, threads_url=threads_url)

    json_path = os.path.join(out_dir, "youtube_short.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(yt_data, f, ensure_ascii=False, indent=2)

    txt_path = os.path.join(out_dir, "youtube_short.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(
            f"KANAL: {yt_data['channel_url']}\n"
            f"BAŞLIK ({len(yt_data['title'])}/100): {yt_data['title']}\n\n"
            f"AÇIKLAMA:\n{yt_data['description']}\n"
        )

    print(f"[BAŞARILI] YouTube Shorts (@guzelaicom) profesyonel başlık ve açıklaması hazırlandı: {txt_path}")
    return yt_data


def ensure_youtube_chrome(port: int = YOUTUBE_CDP_PORT, profile_dir: Path = YOUTUBE_PROFILE_DIR) -> Optional[str]:
    profile_dir.mkdir(parents=True, exist_ok=True)
    try:
        tabs = requests.get(f"http://127.0.0.1:{port}/json", timeout=2).json()
    except Exception:
        chrome_cmd = (
            f'"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" '
            f'--remote-debugging-port={port} '
            f'--remote-allow-origins=* '
            f'--user-data-dir="{profile_dir}" '
            f'--no-first-run --no-default-browser-check '
            f'--disable-blink-features=AutomationControlled '
            f'--window-size=1240,920 "https://studio.youtube.com/"'
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"Invoke-WmiMethod -Class Win32_Process -Name Create -ArgumentList '{chrome_cmd}'"],
            capture_output=True,
        )
        for _ in range(15):
            time.sleep(1)
            try:
                tabs = requests.get(f"http://127.0.0.1:{port}/json", timeout=2).json()
                if any(t.get("type") == "page" for t in tabs):
                    break
            except Exception:
                pass
        else:
            return None

    page_tab = next((t for t in tabs if t.get("type") == "page"), None)
    return page_tab["webSocketDebuggerUrl"] if page_tab else None


def publish_to_youtube_cdp(
    outfit: Dict[str, Any],
    video_path: Path,
    reel_url: str = "",
    threads_url: str = "",
    port: int = YOUTUBE_CDP_PORT,
) -> Dict[str, Any]:
    """Uploads and publishes a YouTube Short with its exact viral hook title via YouTube Studio Chrome CDP."""
    video_path = video_path.resolve()
    if not video_path.exists():
        return {"status": "error", "reason": f"Video not found: {video_path}"}

    yt_data = build_youtube_short_data(outfit, reel_url=reel_url, threads_url=threads_url)

    # Copy video to a viral-hook-named file so YouTube Studio NEVER defaults to 'daily kombin reel'
    named_dir = video_path.parent / "_yt_named"
    named_dir.mkdir(parents=True, exist_ok=True)
    viral_filename = _safe_filename_from_title(yt_data["title"])
    upload_video_path = (named_dir / viral_filename).resolve()
    shutil.copy2(video_path, upload_video_path)

    ws_url = ensure_youtube_chrome(port=port)
    if not ws_url:
        return {"status": "error", "reason": "No Chrome tab available for YouTube Studio"}

    ws = websocket.create_connection(ws_url, timeout=30)
    msg_id = 0

    def cdp(method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        nonlocal msg_id
        msg_id += 1
        ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        while True:
            resp = json.loads(ws.recv())
            if resp.get("id") == msg_id:
                return resp.get("result", {})

    try:
        cdp("Page.enable")
        cdp("DOM.enable")
        cdp("Runtime.enable")
        cdp("Input.enable")

        cdp("Page.navigate", {"url": "https://www.youtube.com/upload"})
        time.sleep(7)

        curr_url = cdp("Runtime.evaluate", {"expression": "location.href", "returnByValue": True}).get("result", {}).get("value", "")
        if "accounts.google.com" in curr_url or "signin" in curr_url.lower():
            return {"status": "login_required", "url": curr_url}

        doc_root = cdp("DOM.getDocument", {"depth": -1})["root"]["nodeId"]
        q_res = cdp("DOM.querySelector", {"nodeId": doc_root, "selector": 'input[type="file"]'})
        node_id = q_res.get("nodeId", 0)
        if not node_id:
            cdp("Runtime.evaluate", {
                "expression": """(() => {
                    const b = document.querySelector('#create-icon, ytcp-button#create-icon, button[aria-label*="Oluştur"], button[aria-label*="Create"]');
                    if (b) b.click();
                })()"""
            })
            time.sleep(2)
            cdp("Runtime.evaluate", {
                "expression": """(() => {
                    const item = Array.from(document.querySelectorAll('tp-yt-paper-item, ytcp-ve')).find(e => /Video yükle|Upload videos/i.test(e.innerText || ''));
                    if (item) item.click();
                })()"""
            })
            time.sleep(3)
            doc_root = cdp("DOM.getDocument", {"depth": -1})["root"]["nodeId"]
            q_res = cdp("DOM.querySelector", {"nodeId": doc_root, "selector": 'input[type="file"]'})
            node_id = q_res.get("nodeId", 0)

        if not node_id:
            return {"status": "error", "reason": "input[type=file] not found on YouTube Studio"}

        cdp("DOM.setFileInputFiles", {"nodeId": node_id, "files": [str(upload_video_path)]})
        print(f"📤 YouTube Shorts viral başlıklı video dosyası yüklendi: {upload_video_path.name}")
        time.sleep(10)

        # Explicitly replace Title and Description using Range selection + CDP Input.insertText
        title_box_info = json.loads(cdp("Runtime.evaluate", {
            "expression": """JSON.stringify((() => {
                const boxes = Array.from(document.querySelectorAll('#textbox[contenteditable="true"]'));
                if (boxes.length < 1) return {count: 0};
                const tb = boxes[0];
                tb.focus();
                const sel = window.getSelection();
                const range = document.createRange();
                range.selectNodeContents(tb);
                sel.removeAllRanges();
                sel.addRange(range);
                return {count: boxes.length};
            })())""",
            "returnByValue": True
        }).get("result", {}).get("value", "{}") or "{}")

        if title_box_info.get("count", 0) >= 1:
            cdp("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
            cdp("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
            time.sleep(0.3)
            cdp("Input.insertText", {"text": yt_data["title"]})
            time.sleep(0.8)

        if title_box_info.get("count", 0) >= 2:
            cdp("Runtime.evaluate", {
                "expression": """(() => {
                    const boxes = Array.from(document.querySelectorAll('#textbox[contenteditable="true"]'));
                    if (boxes.length >= 2) {
                        const db = boxes[1];
                        db.focus();
                        const sel = window.getSelection();
                        const range = document.createRange();
                        range.selectNodeContents(db);
                        sel.removeAllRanges();
                        sel.addRange(range);
                    }
                })()"""
            })
            cdp("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
            cdp("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
            time.sleep(0.3)
            cdp("Input.insertText", {"text": yt_data["description"]})
            time.sleep(0.8)

        cdp("Runtime.evaluate", {
            "expression": """(() => {
                const notKids = document.querySelector('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]');
                if (notKids) notKids.click();
            })()"""
        })
        time.sleep(2)

        for _ in range(3):
            cdp("Runtime.evaluate", {
                "expression": """(() => {
                    const nextBtn = document.querySelector('#next-button');
                    if (nextBtn) nextBtn.click();
                })()"""
            })
            time.sleep(2.5)

        pub_js = """
        (function() {
            const pubRadio = document.querySelector('tp-yt-paper-radio-button[name="PUBLIC"]');
            if (pubRadio) pubRadio.click();
            const doneBtn = document.querySelector('#done-button');
            if (doneBtn) {
                doneBtn.click();
                return "CLICKED_DONE_PUBLISH";
            }
            return "NO_DONE_BTN";
        })()
        """
        pub_res = cdp("Runtime.evaluate", {"expression": pub_js, "returnByValue": True}).get("result", {}).get("value")
        time.sleep(6)
        return {"status": "published", "title": yt_data["title"], "action": pub_res, "channel": YOUTUBE_CHANNEL_URL}
    finally:
        try:
            ws.close()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outfit-json", default="output/outfit_links.json")
    parser.add_argument("--video", default="output/daily_kombin_reel.mp4")
    parser.add_argument("--publish", action="store_true", help="YouTube Shorts olarak yayınla")
    args = parser.parse_args()

    out_dir = os.path.dirname(args.outfit_json) or "output"
    if os.path.exists(args.outfit_json):
        with open(args.outfit_json, "r", encoding="utf-8") as f:
            outfit = json.load(f)
        save_youtube_outputs(outfit, out_dir=out_dir)
        if args.publish:
            res = publish_to_youtube_cdp(outfit, Path(args.video))
            print("[YouTube Shorts Yayın Sonucu]:", json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
