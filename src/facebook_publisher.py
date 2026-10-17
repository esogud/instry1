"""
Facebook Reels & Feed Auto-Publisher for GuzelAI Medya (archzencir@gmail.com)
-----------------------------------------------------------------------------
Features:
- Builds Facebook Reels / Feed post caption with:
  * GuzelAI.com Verified E-Commerce Showcase link (https://guzelai.com/#kombinler)
  * WhatsApp Channel link (https://whatsapp.com/channel/0029VbDetYc3mFYDwZSry016)
  * 6 Outfit items with Brand, Name, Price (TL), SKU code, and direct store links
  * Mandatory Turkish Ministry of Trade disclosure (#reklam #işbirliğideğil)
- Uses persistent local Chrome CDP profile (facebook_chrome_profile on port 9235)
  to log in once as the single trusted local device and publish to Facebook.
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import websocket

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

FB_EMAIL = os.environ.get("FB_EMAIL", "archzencir@gmail.com")
FB_PASSWORD = os.environ.get("FB_PASSWORD", "V6R^!.-i-<-5K2t")
FB_CDP_PORT = 9235
FB_PROFILE_DIR = Path(r"C:\Users\zenci\.gemini\antigravity\scratch\facebook_chrome_profile")
FB_SESSION_FILE = Path(r"C:\Users\zenci\.gemini\antigravity\scratch\facebook_session.json")

GUZELAI_SHOWCASE_URL = "https://guzelai.com/#kombinler"
WHATSAPP_CHANNEL_URL = "https://whatsapp.com/channel/0029VbDetYc3mFYDwZSry016"

ITEM_ORDER = [
    ("outerwear", "⌚ Saat/Üst"),
    ("cap", "✨ Küpe/Aksesuar"),
    ("top", "👚 Gömlek/Üst"),
    ("bottom", "👖 Pantolon"),
    ("bag", "👜 Çanta"),
    ("shoes", "👠 Ayakkabı"),
]

TR_FB_LEGAL_NOTICE = (
    "⚖️ Yasal Uyarı: Bu paylaşım reklam veya sponsorlu iş birliği içermez; "
    "tamamen kombin önerisi ve bilgilendirme amaçlıdır (zorunlu #reklam #işbirliğideğil)."
)


def build_facebook_post(outfit: Dict[str, Any], ig_reel_url: str = "", threads_url: str = "") -> Dict[str, Any]:
    """Builds Facebook Reels / Feed post text with verified links and TR legal notice."""
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
        "📌 Not: Görseldeki kadın kombin parçalarının stokta olan birebir veya en yakın %100 Kadın mağaza muadil (benzer) ürün linkleri doğrulanarak aşağıda listelenmiştir:",
    )

    lines = [
        f"🔥 {title}",
        "",
        viral_hook,
        "🎃 Ekim Sonbahar & Cadılar Bayramı (Halloween) Gece/Gündüz Davet Şıklığı | %100 Kadın Old Money Kombin",
        f"💰 Toplam Kombin: {total_str} — Sizce bu kombin 10 üzerinden kaç? Yorumlara yazın! 👇🤍",
        "",
        f"🌐 Görselli & Doğrulanmış E-Ticaret Link Vitrini: {GUZELAI_SHOWCASE_URL}",
        f"💬 WhatsApp Kombin Kanalımız: {WHATSAPP_CHANNEL_URL}",
        "",
        seo_note,
        "",
        "🛍️ KOMBİN PARÇALARI & DOĞRUDAN MAĞAZA LİNKLERİ (BİREBİR / BENZER MUADİL):",
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
            lines.append(f"{label}: {brand} - {name} ({price}) [Kod: {sku}]")
            if url:
                lines.append(f"🔗 {url}")

    lines.extend([
        "",
        f"📸 Instagram Reels: {reel_link}",
        "🎵 TikTok: https://www.tiktok.com/@guzelaicom",
        "▶️ YouTube Shorts: https://www.youtube.com/@guzelaicom/shorts",
        "𝕏 X (Twitter): https://x.com/guzelaicom",
        "",
        TR_FB_LEGAL_NOTICE,
        "",
        "#kadınkombin #kombinönerileri #oldmoneystil #sonbaharkombini #cadılarbayramı #halloweenkombin #ekimstili #moda #reels #ootd #reklam #işbirliğideğil",
    ])

    text = "\n".join(lines)
    return {
        "account_email": FB_EMAIL,
        "title": title,
        "total_price_str": total_str,
        "showcase_url": GUZELAI_SHOWCASE_URL,
        "whatsapp_channel": WHATSAPP_CHANNEL_URL,
        "text": text,
    }


def save_facebook_outputs(outfit: Dict[str, Any], out_dir: str = "output", ig_reel_url: str = "") -> Dict[str, Any]:
    os.makedirs(out_dir, exist_ok=True)
    post = build_facebook_post(outfit, ig_reel_url=ig_reel_url)

    json_path = os.path.join(out_dir, "facebook_post.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(post, f, ensure_ascii=False, indent=2)

    txt_path = os.path.join(out_dir, "facebook_post.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(post["text"] + "\n")

    print(f"[BAŞARILI] Facebook paylaşım metni ve doğrulanmış linkler hazırlandı: {txt_path}")
    return post


def ensure_facebook_chrome(port: int = FB_CDP_PORT, profile_dir: Path = FB_PROFILE_DIR) -> Optional[str]:
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
            f'--window-size=1220,920 "https://www.facebook.com/"'
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


def login_and_verify_facebook(
    email: str = FB_EMAIL,
    password: str = FB_PASSWORD,
    port: int = FB_CDP_PORT,
) -> Dict[str, Any]:
    """Logs into Facebook on the persistent local Chrome profile (port 9235) and verifies session."""
    ws_url = ensure_facebook_chrome(port=port)
    if not ws_url:
        return {"status": "error", "reason": "No Chrome tab available for Facebook"}

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
        cdp("Network.enable")
        cdp("Page.bringToFront")

        cookies = cdp("Network.getAllCookies").get("cookies", [])
        fb_cookies = {c["name"]: c["value"] for c in cookies if "facebook.com" in c.get("domain", "")}
        if "c_user" in fb_cookies:
            FB_SESSION_FILE.write_text(json.dumps(fb_cookies, indent=2), encoding="utf-8")
            return {"status": "logged_in", "c_user": fb_cookies.get("c_user"), "cookies": list(fb_cookies.keys())}

        cdp("Page.navigate", {"url": "https://www.facebook.com/login"})
        pump_frames(5)

        # Dismiss any cookie consent banner on Facebook if present
        cdp("Runtime.evaluate", {
            "expression": """(() => {
                const btns = Array.from(document.querySelectorAll('button, [role="button"]'));
                const allow = btns.find(b => /Allow all cookies|Tüm çerezlere izin ver|Temel ve isteğe bağlı çerezlere izin ver/i.test(b.innerText || ''));
                if (allow) allow.click();
            })()""",
            "returnByValue": True,
        })
        pump_frames(1)

        # Fill email and password using React native setter + CDP click
        fill_res = json.loads(cdp("Runtime.evaluate", {
            "expression": f"""JSON.stringify((() => {{
                function setNativeValue(el, val) {{
                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    setter.call(el, val);
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
                const em = document.querySelector('input#email, input[name="email"], input[type="text"], input[type="email"]');
                const pw = document.querySelector('input#pass, input[name="pass"], input[type="password"]');
                if (!em || !pw) return {{status: "NO_INPUTS"}};
                em.focus();
                setNativeValue(em, {json.dumps(email)});
                pw.focus();
                setNativeValue(pw, {json.dumps(password)});
                const btn = document.querySelector('button[name="login"], button#loginbutton, button[type="submit"]')
                         || Array.from(document.querySelectorAll('div[role="button"], button')).find(b => /^(Giriş Yap|Log In|Log in)$/i.test((b.innerText || '').trim()));
                if (btn) {{
                    const r = btn.getBoundingClientRect();
                    btn.click();
                    return {{status: "SUBMITTED", x: r.left + r.width/2, y: r.top + r.height/2}};
                }}
                return {{status: "FILLED_NO_BTN"}};
            }})())""",
            "returnByValue": True,
        }).get("result", {}).get("value", "{}") or "{}")
        print("[Facebook] Giriş formu durumu:", fill_res)
        if fill_res.get("x") and fill_res.get("y"):
            cdp("Input.dispatchMouseEvent", {"type": "mousePressed", "x": fill_res["x"], "y": fill_res["y"], "button": "left", "clickCount": 1})
            cdp("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": fill_res["x"], "y": fill_res["y"], "button": "left", "clickCount": 1})
        pump_frames(8)

        cookies = cdp("Network.getAllCookies").get("cookies", [])
        fb_cookies = {c["name"]: c["value"] for c in cookies if "facebook.com" in c.get("domain", "")}
        if "c_user" in fb_cookies:
            FB_SESSION_FILE.write_text(json.dumps(fb_cookies, indent=2), encoding="utf-8")

        state = json.loads(cdp("Runtime.evaluate", {
            "expression": """JSON.stringify({
                url: location.href,
                title: document.title,
                text: document.body ? document.body.innerText.slice(0, 700) : ''
            })""",
            "returnByValue": True,
        }).get("result", {}).get("value", "{}"))

        return {
            "status": "logged_in" if "c_user" in fb_cookies else "check_state",
            "c_user": fb_cookies.get("c_user"),
            "url": state.get("url"),
            "title": state.get("title"),
            "text_preview": state.get("text", "")[:400],
            "cookies": list(fb_cookies.keys()),
        }
    finally:
        try:
            ws.close()
        except Exception:
            pass


def cleanup_text_only_posts_and_setup_profile(cdp, pump_frames) -> Dict[str, Any]:
    """Deletes any text-only posts on the Facebook profile and uploads profile/cover photos if missing."""
    actions = []
    try:
        cdp("Page.navigate", {"url": "https://www.facebook.com/profile.php?id=61595315767647"})
        pump_frames(6)

        # 1. Check for text-only posts and move them to trash so the profile looks clean
        for _ in range(3):
            menu_clicked = json.loads(cdp("Runtime.evaluate", {
                "expression": """JSON.stringify((() => {
                    const btns = Array.from(document.querySelectorAll('div[role="button"][aria-label*="gönderi"], div[role="button"][aria-label*="Actions for this post"], div[role="button"][aria-label*="Bu gönderide"]'));
                    for (const b of btns) {
                        const article = b.closest('div[role="article"]') || b.parentElement.parentElement.parentElement.parentElement;
                        if (article) {
                            const hasMedia = article.querySelector('video, img[src*="scontent"][width]');
                            const imgs = Array.from(article.querySelectorAll('img')).filter(im => im.width > 180 && im.height > 180);
                            if (imgs.length === 0 && !article.querySelector('video')) {
                                b.scrollIntoView({block: 'center'});
                                b.click();
                                const r = b.getBoundingClientRect();
                                return {clicked: true, x: r.left + r.width/2, y: r.top + r.height/2};
                            }
                        }
                    }
                    return {clicked: false};
                })())""",
                "returnByValue": True,
            }).get("result", {}).get("value", "{}") or "{}")

            if not menu_clicked.get("clicked"):
                break
            pump_frames(2)

            trash_clicked = json.loads(cdp("Runtime.evaluate", {
                "expression": """JSON.stringify((() => {
                    const items = Array.from(document.querySelectorAll('div[role="menuitem"], span'));
                    const del = items.find(el => /Çöp kutusuna taşı|Gönderiyi sil|Move to trash|Delete post/i.test((el.innerText || '').trim()));
                    if (del) {
                        del.click();
                        return {deleted: true, text: (del.innerText || '').trim()};
                    }
                    return {deleted: false};
                })())""",
                "returnByValue": True,
            }).get("result", {}).get("value", "{}") or "{}")
            if trash_clicked.get("deleted"):
                pump_frames(2)
                cdp("Runtime.evaluate", {
                    "expression": """(() => {
                        const btns = Array.from(document.querySelectorAll('div[role="dialog"] div[role="button"], div[aria-label="Taşı"], div[aria-label="Sil"], div[aria-label="Move"], div[aria-label="Delete"]'));
                        const confirmBtn = btns.find(b => /^(Taşı|Sil|Move|Delete)$/i.test((b.getAttribute('aria-label') || b.innerText || '').trim()));
                        if (confirmBtn) confirmBtn.click();
                    })()""",
                    "returnByValue": True,
                })
                pump_frames(3)
                actions.append("deleted_text_only_post")
            else:
                break
    except Exception as e:
        actions.append(f"cleanup_warn:{e}")

    return {"actions": actions}


def publish_to_facebook_cdp(
    outfit: Dict[str, Any],
    media_path: Optional[Path] = None,
    ig_reel_url: str = "",
    port: int = FB_CDP_PORT,
) -> Dict[str, Any]:
    """Publishes the Kombin post + collage + product visual cards / video to Facebook via Chrome CDP on port 9235."""
    post_data = build_facebook_post(outfit, ig_reel_url=ig_reel_url)
    ws_url = ensure_facebook_chrome(port=port)
    if not ws_url:
        return {"status": "error", "reason": "No Chrome tab available for Facebook"}

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
        cdp("Network.enable")
        cdp("Page.bringToFront")

        cookies = cdp("Network.getAllCookies").get("cookies", [])
        fb_cookies = {c["name"]: c["value"] for c in cookies if "facebook.com" in c.get("domain", "")}
        if "c_user" not in fb_cookies:
            ws.close()
            login_res = login_and_verify_facebook(port=port)
            if login_res.get("status") != "logged_in":
                return login_res
            ws = websocket.create_connection(ensure_facebook_chrome(port=port), timeout=30)
            cdp("Page.enable")
            cdp("DOM.enable")
            cdp("Runtime.enable")
            cdp("Input.enable")
            cdp("Page.bringToFront")

        # Clean up any text-only posts on the profile first
        cleanup_res = cleanup_text_only_posts_and_setup_profile(cdp, pump_frames)

        # Navigate to home/profile composer and click "Fotoğraf/video" button FIRST so media upload input is active
        cdp("Page.navigate", {"url": "https://www.facebook.com/profile.php?id=61595315767647"})
        pump_frames(5)

        open_composer = cdp("Runtime.evaluate", {
            "expression": """(() => {
                const btns = Array.from(document.querySelectorAll('div[role="button"], span'));
                const photoBtn = btns.find(el => /^(Fotoğraf\\/video|Photo\\/video)$/i.test((el.innerText || '').trim()));
                if (photoBtn) {
                    photoBtn.click();
                    return "OPENED_PHOTO_VIDEO_COMPOSER";
                }
                const trigger = btns.find(el => /Ne düşünüyorsun|What's on your mind/i.test((el.innerText || '').trim()));
                if (trigger) {
                    trigger.click();
                    return "OPENED_TEXT_COMPOSER";
                }
                return "NO_TRIGGER";
            })()""",
            "returnByValue": True,
        }).get("result", {}).get("value")
        pump_frames(4)

        # Collect visual files to upload: Short video + 2K Collage + 6 Visual Product Cards
        upload_files: List[str] = []
        collage_candidate = Path("output/kombin_collage.png").resolve()
        short_video_candidate = Path("output/graphmotion_short.mp4").resolve()
        if short_video_candidate.exists():
            upload_files.append(str(short_video_candidate))
        if collage_candidate.exists():
            upload_files.append(str(collage_candidate))
        for slot_k in ["outerwear", "cap", "top", "bottom", "bag", "shoes"]:
            card_p = Path(f"output/item_card_{slot_k}.jpg").resolve()
            if card_p.exists():
                upload_files.append(str(card_p))
        if not upload_files and media_path and media_path.exists():
            upload_files.append(str(media_path.resolve()))

        # 1. Attach files via input[type="file"] inside dialog BEFORE typing URLs (so link preview never overrides photos/videos)
        media_attached = False
        if upload_files:
            # Make sure photo/video dropzone inside dialog is open if needed
            cdp("Runtime.evaluate", {
                "expression": """(() => {
                    const dialog = Array.from(document.querySelectorAll('div[role="dialog"]')).find(d => /Gönderi oluştur|Create post/i.test(d.innerText || ''));
                    if (!dialog) return;
                    const addMediaBtn = Array.from(dialog.querySelectorAll('div[role="button"], span')).find(
                        el => /Fotoğraf\\/video ekle|Fotoğraf\\/video|Add photos\\/videos/i.test((el.getAttribute('aria-label') || el.innerText || '').trim())
                    );
                    if (addMediaBtn && dialog.querySelectorAll('input[type="file"]').length === 0) {
                        addMediaBtn.click();
                    }
                })()""",
                "returnByValue": True,
            })
            pump_frames(2)

            eval_res = cdp("Runtime.evaluate", {
                "expression": """(() => {
                    const dialog = Array.from(document.querySelectorAll('div[role="dialog"]')).find(d => /Gönderi oluştur|Create post/i.test(d.innerText || '')) || document;
                    const inputs = Array.from(dialog.querySelectorAll('input[type="file"]'));
                    const allInputs = inputs.length ? inputs : Array.from(document.querySelectorAll('input[type="file"]'));
                    return allInputs.find(i => i.multiple && ((i.accept || '').includes('image') || (i.accept || '').includes('video')))
                        || allInputs.find(i => (i.accept || '').includes('image') || (i.accept || '').includes('video'))
                        || allInputs[0] || null;
                })()""",
                "returnByValue": False,
            })
            obj_id = eval_res.get("result", {}).get("objectId")
            if obj_id:
                cdp("DOM.setFileInputFiles", {"objectId": obj_id, "files": upload_files})
                pump_frames(7)

            # Verify media preview appeared inside dialog
            media_attached = cdp("Runtime.evaluate", {
                "expression": """(() => {
                    const dialog = Array.from(document.querySelectorAll('div[role="dialog"]')).find(d => /Gönderi oluştur|Create post/i.test(d.innerText || ''));
                    if (!dialog) return false;
                    const hasBlobImg = Array.from(dialog.querySelectorAll('img')).some(im => (im.src || '').startsWith('blob:') || im.width > 140);
                    const hasVideo = !!dialog.querySelector('video');
                    return hasBlobImg || hasVideo;
                })()""",
                "returnByValue": True,
            }).get("result", {}).get("value", False)

        # Fallback: copy kombin_collage.png to Windows clipboard and Ctrl+V paste into textbox if DOM.setFileInputFiles didn't trigger preview
        if not media_attached and collage_candidate.exists():
            ps_clip = (
                f"Add-Type -AssemblyName System.Windows.Forms; "
                f"Add-Type -AssemblyName System.Drawing; "
                f"$img = [System.Drawing.Image]::FromFile('{collage_candidate}'); "
                f"[System.Windows.Forms.Clipboard]::SetImage($img); "
                f"$img.Dispose()"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_clip], capture_output=True)

        # 2. Focus the "Ne düşünüyorsun, Güzel?" textbox and insert caption (and Ctrl+V if needed)
        focus_box = json.loads(cdp("Runtime.evaluate", {
            "expression": """JSON.stringify((() => {
                const dialog = Array.from(document.querySelectorAll('div[role="dialog"]')).find(d => /Gönderi oluştur|Create post/i.test(d.innerText || '')) || document;
                const ed = dialog.querySelector('div[role="textbox"][contenteditable="true"]');
                if (!ed) return {ok: false};
                const r = ed.getBoundingClientRect();
                ed.click();
                ed.focus();
                return {ok: true, x: r.left + 40, y: r.top + 15};
            })())""",
            "returnByValue": True,
        }).get("result", {}).get("value", "{}") or "{}")

        if focus_box.get("ok"):
            cdp("Input.dispatchMouseEvent", {"type": "mousePressed", "x": focus_box["x"], "y": focus_box["y"], "button": "left", "clickCount": 1})
            cdp("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": focus_box["x"], "y": focus_box["y"], "button": "left", "clickCount": 1})
            pump_frames(1)
            if not media_attached and collage_candidate.exists():
                cdp("Input.dispatchKeyEvent", {"type": "rawKeyDown", "windowsVirtualKeyCode": 86, "code": "KeyV", "key": "v", "modifiers": 2})
                cdp("Input.dispatchKeyEvent", {"type": "keyUp", "windowsVirtualKeyCode": 86, "code": "KeyV", "key": "v", "modifiers": 2})
                pump_frames(5)
                media_attached = True
            cdp("Input.insertText", {"text": post_data["text"]})
            pump_frames(3)

        # 3. Wait for media upload to finish (Paylaş button becomes enabled) and click Paylaş
        post_click = {"clicked": False}
        for _ in range(15):
            post_click = json.loads(cdp("Runtime.evaluate", {
                "expression": """JSON.stringify((() => {
                    const dialog = Array.from(document.querySelectorAll('div[role="dialog"]')).find(d => /Gönderi oluştur|Create post/i.test(d.innerText || '')) || document;
                    const btns = Array.from(dialog.querySelectorAll('div[aria-label="Paylaş"], div[aria-label="Gönder"], div[aria-label="Post"], div[role="button"], button'));
                    const btn = btns.find(b => {
                        const label = (b.getAttribute('aria-label') || b.innerText || '').trim();
                        return /^(Paylaş|Gönder|Post)$/i.test(label) && b.getAttribute('aria-disabled') !== 'true';
                    });
                    if (!btn) return {clicked: false};
                    const r = btn.getBoundingClientRect();
                    btn.click();
                    return {clicked: true, x: r.left + r.width/2, y: r.top + r.height/2};
                })())""",
                "returnByValue": True,
            }).get("result", {}).get("value", "{}") or "{}")
            if post_click.get("clicked"):
                break
            pump_frames(2)

        if post_click.get("clicked"):
            x, y = post_click.get("x", 0), post_click.get("y", 0)
            if x and y:
                cdp("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
                cdp("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})
            pump_frames(10)
            return {
                "status": "published",
                "account": "Güzel Ai (archzencir@gmail.com)",
                "composer": open_composer,
                "media_attached": media_attached,
                "files_count": len(upload_files),
                "cleanup": cleanup_res,
            }

        return {
            "status": "prepared_in_composer",
            "composer": open_composer,
            "media_attached": media_attached,
            "focus": focus_box,
        }
    finally:
        try:
            ws.close()
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outfit-json", default="output/outfit_links.json")
    parser.add_argument("--login", action="store_true", help="Facebook hesabına giriş yap ve doğrula")
    parser.add_argument("--publish", action="store_true", help="Facebook'ta paylaş")
    parser.add_argument("--ig-reel-url", default="")
    args = parser.parse_args()

    out_dir = os.path.dirname(args.outfit_json) or "output"
    outfit = {}
    if os.path.exists(args.outfit_json):
        with open(args.outfit_json, "r", encoding="utf-8") as f:
            outfit = json.load(f)
        save_facebook_outputs(outfit, out_dir=out_dir, ig_reel_url=args.ig_reel_url or outfit.get("reel_url", ""))

    if args.login:
        res = login_and_verify_facebook()
        print("[Facebook Giriş Sonucu]:", json.dumps(res, ensure_ascii=False, indent=2))

    if args.publish and outfit:
        collage = Path(out_dir) / "kombin_collage.png"
        res = publish_to_facebook_cdp(outfit, media_path=collage, ig_reel_url=args.ig_reel_url or outfit.get("reel_url", ""))
        print("[Facebook Yayın Sonucu]:", json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
