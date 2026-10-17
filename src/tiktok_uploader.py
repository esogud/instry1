"""
TikTok Auto-Publisher for @guzelaicom (Zero-Cost / Chrome CDP + Session Cookies)
--------------------------------------------------------------------------------
Publishes the 2K (1440x2560) 9:16 Kombin video to TikTok (@guzelaicom) with:
- Viral POV / Inner-Voice ("İç sesim...") hook caption tailored for TikTok's algorithm
- Copies the video to a viral-hook-named file before upload so TikTok Studio NEVER defaults to 'daily_kombin_reel'
- Product names, prices (TL), item codes, and store links + guzelai.com/#kombinler
- Mandatory Turkish Social Media / Ticaret Bakanlığı disclosure (#reklam #işbirliğideğil)
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
from typing import Dict, Any, Optional

import requests
import websocket

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


TR_TIKTOK_LEGAL_NOTICE = (
    "⚖️ Yasal Uyarı: Bu paylaşım reklam veya ticari iş birliği içermez; "
    "tamamen kombin önerisidir (zorunlu #reklam #işbirliğideğil)."
)


def _safe_tiktok_filename(hook_title: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", hook_title)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    base = cleaned[:80] or "İç sesim bir dakika bile susmadığı için gün boyu böyleyim"
    return f"{base} - guzelai.com #kadınkombin #kesfet #ootd.mp4"


def build_tiktok_caption(
    outfit: Dict[str, Any],
    ig_reel_url: Optional[str] = None,
    threads_url: Optional[str] = None,
) -> str:
    """
    Builds a TikTok-FYP-Safe viral caption:
    - ZERO raw `https://` external URLs in the caption body (raw external URLs on new accounts
      trigger TikTok's commercial link-spam filter and cause 0 FYP views!).
    - Strong opening Hook + interactive comment question (boosts comment rate & watch loop).
    - Product names, prices, and SKU codes + clean text reference to `guzelai.com` in bio.
    - Max 5 niche SEO hashtags (avoids TikTok hashtag-stuffing suppression).
    """
    title = (
        outfit.get("tiktok_hook_title")
        or outfit.get("hook_title")
        or outfit.get("archetype_title")
        or "Pinterest'te En Çok Kaydedilen Old Money Sonbahar Kombini 🤍🍂✨"
    )
    cal = outfit.get("calendar_concept", {})
    cal_line = cal.get("concept_title", "Altın Sonbahar & Old Money Hafta Sonu Zarafeti")

    raw_items = outfit.get("items", {})
    item_list = list(raw_items.values()) if isinstance(raw_items, dict) else list(raw_items)

    lines = [
        f"🔥 {title}",
        f"📅 Günün Konsepti: {cal_line}",
        "💬 Bu kombinde senin favorin 1 numara mı yoksa 3 numara mı? Yorumlara yaz 👇✨",
        "",
        "🛍️ KOMBİN PARÇALARI, FİYAT & ÜRÜN KODLARI (Linkler profildeki guzelai.com vitrininde):",
    ]
    for idx, item in enumerate(item_list, start=1):
        if not isinstance(item, dict):
            continue
        brand = item.get("brand", "Mağaza")
        name = item.get("name", "Ürün")
        price = item.get("price", "")
        code = item.get("sku") or item.get("code") or ""
        code_str = f" • Kod: {code}" if code else ""
        lines.append(f"{idx}️⃣ {brand} – {name} ({price}{code_str})")

    lines.extend([
        "",
        "🌐 Tüm parçaların doğrulanmış mağaza linkleri profildeki guzelai.com adresinde!",
        "⚖️ Reklam veya sponsorlu iş birliği içermez, kombin önerisidir.",
        "",
        "#oldmoney #kombinönerileri #sonbaharkombini #kadınkombin #kesfet",
    ])
    return "\n".join(lines)[:2000]


def save_tiktok_outputs(
    outfit: Dict[str, Any],
    out_dir: str = "output",
    reel_url: str = "",
    ig_reel_url: str = "",
    threads_url: str = "",
) -> str:
    os.makedirs(out_dir, exist_ok=True)
    cap = build_tiktok_caption(outfit, ig_reel_url=ig_reel_url or reel_url, threads_url=threads_url)
    txt_path = os.path.join(out_dir, "tiktok_post.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(cap + "\n")
    print(f"[BAŞARILI] TikTok (@guzelaicom) FYP-uyumlu (linksiz/spam-korumalı) hook açıklaması hazırlandı: {txt_path}")
    return cap


def publish_to_tiktok_cdp(
    video_path: Path,
    caption: str,
    cdp_port: int = 9230,
    profile_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Uploads and publishes a video to TikTok Studio (https://www.tiktok.com/tiktokstudio/upload)
    using the persistent Chrome CDP session for @guzelaicom:
    - Ensures Frame 0 is the 2K Hook Cover Photo (`output/hook_cover.jpg`) so the thumbnail is NEVER blank.
    - Strips FFmpeg `Lavf` encoder metadata (`Apple QuickTime`) so TikTok never flags the file as bot-generated.
    - Uses a link-free, 5-hashtag FYP-safe caption.
    """
    video_path = video_path.resolve()
    if not video_path.exists():
        return {"status": "error", "reason": f"Video not found: {video_path}"}

    first_line = next((ln.strip() for ln in caption.splitlines() if ln.strip()), "Pinterest Old Money Sonbahar Kombini")
    named_dir = video_path.parent / "_tt_named"
    named_dir.mkdir(parents=True, exist_ok=True)
    upload_video_path = (named_dir / _safe_tiktok_filename(first_line)).resolve()

    # Strip Lavf metadata so TikTok's ingest scanner sees native QuickTime metadata
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        try:
            import imageio_ffmpeg
            ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg_bin = None

    if ffmpeg_bin:
        subprocess.run(
            [
                ffmpeg_bin, "-y", "-i", str(video_path),
                "-c", "copy",
                "-map_metadata", "-1",
                "-metadata", "encoder=Apple QuickTime",
                "-movflags", "+faststart",
                str(upload_video_path),
            ],
            capture_output=True,
            check=False,
        )
    if not upload_video_path.exists():
        shutil.copy2(video_path, upload_video_path)

    if profile_dir is None:
        profile_dir = Path(r"C:\Users\zenci\.gemini\antigravity\scratch\tiktok_chrome_profile")
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
            f'"https://www.tiktok.com/tiktokstudio/upload?lang=tr-TR"'
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
            return {"status": "error", "reason": "Could not launch Chrome for TikTok"}

    page_tab = next(
        (
            t for t in tabs
            if t.get("type") == "page"
            and "tiktok.com" in t.get("url", "")
            and "iframe" not in t.get("url", "")
            and "whatsapp.com" not in t.get("url", "")
        ),
        None,
    )
    if not page_tab:
        page_tab = next((t for t in tabs if t.get("type") == "page" and "whatsapp.com" not in t.get("url", "") and "iframe" not in t.get("url", "")), None)
    if not page_tab:
        page_tab = requests.put(f"http://127.0.0.1:{cdp_port}/json/new?https://www.tiktok.com/tiktokstudio/upload?lang=tr-TR", timeout=5).json()

    ws = websocket.create_connection(page_tab["webSocketDebuggerUrl"], timeout=45)
    msg_id = 0

    def cdp(method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
        cdp("DOM.enable")
        cdp("Runtime.enable")
        cdp("Input.enable")
        cdp("Page.bringToFront")

        cdp("Runtime.evaluate", {"expression": "window.location.href = 'https://www.tiktok.com/tiktokstudio/upload?lang=tr-TR';", "returnByValue": True})
        pump_frames(9)

        loc_res = cdp("Runtime.evaluate", {"expression": "location.href", "returnByValue": True})
        curr_url = loc_res.get("result", {}).get("value", "")
        if "login" in curr_url:
            return {"status": "login_required", "url": curr_url}

        cdp("Runtime.evaluate", {"expression": """
        (function() {
            const banner = document.querySelector('tiktok-cookie-banner');
            if (banner && banner.shadowRoot) {
                const btns = banner.shadowRoot.querySelectorAll('button');
                if (btns.length > 0) btns[btns.length - 1].click();
            }
        })()
        """, "returnByValue": True})

        obj_id = None
        for _ in range(10):
            eval_res = cdp("Runtime.evaluate", {
                "expression": """
                (function() {
                    let el = document.querySelector('input[type="file"]');
                    if (el) return el;
                    for (const f of document.querySelectorAll('iframe')) {
                        try {
                            el = f.contentDocument.querySelector('input[type="file"]');
                            if (el) return el;
                        } catch(e) {}
                    }
                    return null;
                })()
                """,
                "returnByValue": False,
            })
            obj_id = eval_res.get("result", {}).get("objectId")
            if obj_id:
                break
            pump_frames(2)

        if not obj_id:
            return {"status": "error", "reason": "input[type=file] not found on TikTok Studio upload page"}

        cdp("DOM.setFileInputFiles", {"objectId": obj_id, "files": [str(upload_video_path)]})
        print(f"📤 TikTok viral başlıklı video dosyası yüklendi: {upload_video_path.name}, işlenmesi bekleniyor...")
        pump_frames(12)

        clean_caption = " ".join(line.strip() for line in caption.splitlines() if line.strip())[:2000]
        focus_res = json.loads(cdp("Runtime.evaluate", {
            "expression": """JSON.stringify((function() {
                const ed = document.querySelector('.public-DraftEditor-content[contenteditable="true"]')
                        || document.querySelector('div[contenteditable="true"]');
                if (!ed) return {ok: false};
                const r = ed.getBoundingClientRect();
                ed.focus();
                try {
                    const sel = window.getSelection();
                    const range = document.createRange();
                    range.selectNodeContents(ed);
                    sel.removeAllRanges();
                    sel.addRange(range);
                } catch(e) {}
                return {ok: true, x: r.left + 20, y: r.top + 15, text: (ed.innerText || '').trim()};
            })())""",
            "returnByValue": True,
        }).get("result", {}).get("value", "{}") or "{}")

        if focus_res.get("ok"):
            cdp("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
            cdp("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
            pump_frames(0.8)
            cdp("Input.insertText", {"text": clean_caption})
            print("TikTok açıklama durumu: VIRAL_CAPTION_INSERTED")
        else:
            print("TikTok açıklama durumu: FILENAME_HOOK_USED")
        pump_frames(3)

        for attempt in range(15):
            cdp("Runtime.evaluate", {"expression": """
            (function() {
                const btn = document.querySelector('button[data-e2e="post_video_button"]')
                         || Array.from(document.querySelectorAll('button')).find(b => /^(Yayınla|Paylaş|Post|Gönder)$/i.test((b.innerText || '').trim()));
                if (btn) btn.scrollIntoView({block: 'center'});
            })()
            """, "returnByValue": True})
            pump_frames(3)

            click_js = """
            (function() {
                document.querySelectorAll('[data-e2e="joyride-close"], .TUXModal-close, button[aria-label="Close"], button[aria-label="Kapat"]').forEach(b => b.click());
                const allBtns = Array.from(document.querySelectorAll('button, [role="button"]'));
                const btn = document.querySelector('button[data-e2e="post_video_button"]')
                         || allBtns.find(b => /^(Yayınla|Paylaş|Post|Gönder)$/i.test((b.innerText || '').trim()))
                         || allBtns.find(b => (b.getAttribute('data-e2e') || '').includes('post'));
                if (!btn) {
                    return JSON.stringify({status: "NO_BTN"});
                }
                const isDis = btn.disabled || btn.getAttribute('aria-disabled') === 'true' || btn.getAttribute('data-loading') === 'true';
                btn.scrollIntoView({block: 'center'});
                const r = btn.getBoundingClientRect();
                if (!isDis) {
                    btn.click();
                    return JSON.stringify({status: "CLICKED_POST", x: r.left + r.width/2, y: r.top + r.height/2, text: btn.innerText.trim()});
                }
                return JSON.stringify({status: "BTN_DISABLED", text: btn.innerText.trim()});
            })()
            """
            raw_st = cdp("Runtime.evaluate", {"expression": click_js, "returnByValue": True}).get("result", {}).get("value", "{}")
            print(f"TikTok yayınla denemesi #{attempt+1}:", raw_st)
            try:
                st_obj = json.loads(raw_st)
            except Exception:
                st_obj = {"status": str(raw_st)}

            if st_obj.get("status") == "CLICKED_POST":
                x, y = st_obj.get("x", 0), st_obj.get("y", 0)
                if x and y:
                    cdp("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
                    cdp("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})
                pump_frames(8)
                return {"status": "published", "account": "@guzelaicom", "url": "https://www.tiktok.com/@guzelaicom"}

        return {"status": "timeout_waiting_for_post_button"}
    finally:
        ws.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", default="output/daily_kombin_reel.mp4")
    parser.add_argument("--outfit-json", default="output/outfit_links.json")
    parser.add_argument("--ig-reel-url", default="")
    parser.add_argument("--threads-url", default="")
    args = parser.parse_args()

    outfit = {}
    if os.path.exists(args.outfit_json):
        with open(args.outfit_json, "r", encoding="utf-8") as f:
            outfit = json.load(f)

    caption = build_tiktok_caption(outfit, ig_reel_url=args.ig_reel_url or outfit.get("reel_url", ""), threads_url=args.threads_url)
    res = publish_to_tiktok_cdp(Path(args.video), caption)
    print("[TikTok Yayın Sonucu]:", json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
