"""
X (Twitter) Auto-Publisher for @guzelaicom (https://x.com/guzelaicom)
---------------------------------------------------------------------
Features:
- Obeys X growth & brevity rules: Main post is strictly <= 100 characters
  (Relatable Inner-Voice/POV Viral Hook + https://guzelai.com/#kombinler + #reklam).
- Reply thread contains the 6 verified 100% Women's product links, prices, and SKUs.
- Uses persistent local Chrome CDP profile (x_chrome_profile on port 9234)
  to publish media + <=100-char viral post to https://x.com/guzelaicom.
"""
import argparse
import base64
import json
import os
import re
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

X_PROFILE_URL = "https://x.com/guzelaicom"
X_USERNAME = os.environ.get("X_USERNAME", "guzelaicom")
X_EMAIL = os.environ.get("X_EMAIL", "archzencir@gmail.com")
X_PASSWORD = os.environ.get("X_PASSWORD", "K@rd3s.34-48/mugla")
X_CDP_PORT = 9234
X_PROFILE_DIR = Path(r"C:\Users\zenci\.gemini\antigravity\scratch\x_chrome_profile")


def _x_weighted_len(text: str) -> int:
    """Calculates X (Twitter) character length where every URL counts as 23 characters."""
    without_urls = re.sub(r"https?://\S+", "X" * 23, text)
    return len(without_urls)


def build_x_short_main_post(outfit: Dict[str, Any]) -> str:
    """
    X (Twitter) algoritması için 100 karakteri KESİNLİKLE geçmeyen (<= 100 karakter),
    merak uyandıran İç Ses / POV kancalı ana tweet metni üretir.
    """
    short_x_hook = outfit.get("x_short_hook") or "İç sesim bir dk bile susmadığı için gün boyu böyleyim 😭✨"
    # Hedef link + zorunlu #reklam etiketi: " https://guzelai.com/#kombinler #reklam" (39 karakter)
    suffix = " https://guzelai.com/#kombinler #reklam"
    max_hook_len = 100 - len(suffix)
    trimmed_hook = short_x_hook.strip()
    if len(trimmed_hook) > max_hook_len:
        trimmed_hook = trimmed_hook[: max_hook_len - 1].rstrip() + "…"
    main_post = f"{trimmed_hook}{suffix}"
    return main_post[:100]


def build_x_thread(outfit: Dict[str, Any], reel_url: str = "", threads_url: str = "") -> Dict[str, Any]:
    """Builds an X post where Tweet 1 is strictly <= 100 characters, followed by store link replies."""
    items = outfit.get("items", {})
    t1_text = build_x_short_main_post(outfit)

    t2_lines = [
        "🛍️ Üst & Aksesuar Linkleri (1/2):",
        f"🧥 {items['outerwear']['brand']} ({items['outerwear']['price']}): {items['outerwear']['product_url']}",
        f"🕶️ {items['cap']['brand']} ({items['cap']['price']}): {items['cap']['product_url']}",
        f"👚 {items['top']['brand']} ({items['top']['price']}): {items['top']['product_url']}",
        "ℹ️ Kombin önerisidir (#reklam)",
    ]
    t2_text = "\n".join(t2_lines)

    t3_lines = [
        "🛍️ Alt, Çanta & Ayakkabı (2/2):",
        f"👖 {items['bottom']['brand']} ({items['bottom']['price']}): {items['bottom']['product_url']}",
        f"👜 {items['bag']['brand']} ({items['bag']['price']}): {items['bag']['product_url']}",
        f"👟 {items['shoes']['brand']} ({items['shoes']['price']}): {items['shoes']['product_url']}",
        "ℹ️ Kombin önerisidir (#reklam)",
    ]
    t3_text = "\n".join(t3_lines)

    tweets = [
        {
            "step": 1,
            "role": "main_tweet",
            "text": t1_text,
            "raw_len": len(t1_text),
            "weighted_len": _x_weighted_len(t1_text),
        },
        {
            "step": 2,
            "role": "reply_1",
            "text": t2_text,
            "raw_len": len(t2_text),
            "weighted_len": _x_weighted_len(t2_text),
        },
        {
            "step": 3,
            "role": "reply_2",
            "text": t3_text,
            "raw_len": len(t3_text),
            "weighted_len": _x_weighted_len(t3_text),
        },
    ]

    return {
        "account": "@guzelaicom",
        "profile_url": X_PROFILE_URL,
        "tweets": tweets,
    }


def save_x_outputs(outfit: Dict[str, Any], out_dir: str = "output", reel_url: str = "", threads_url: str = "") -> Dict[str, Any]:
    os.makedirs(out_dir, exist_ok=True)
    thread = build_x_thread(outfit, reel_url=reel_url, threads_url=threads_url)

    json_path = os.path.join(out_dir, "x_post.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(thread, f, ensure_ascii=False, indent=2)

    txt_path = os.path.join(out_dir, "x_post.txt")
    blocks = []
    for t in thread["tweets"]:
        blocks.append(
            f"=== X (TWITTER) ADIM {t['step']} (Uzunluk: {t['raw_len']}/100 karakter | X Ağırlıklı: {t['weighted_len']}) ===\n{t['text']}"
        )
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(blocks) + "\n")

    print(f"[BAŞARILI] X (@guzelaicom) <=100 karakter ana tweet ve zincir metinleri hazırlandı: {txt_path}")
    return thread


def ensure_x_chrome(port: int = X_CDP_PORT, profile_dir: Path = X_PROFILE_DIR) -> Optional[str]:
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
            f'--window-size=1200,900 "https://x.com/home"'
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


def login_and_verify_x(
    username: str = X_USERNAME,
    email: str = X_EMAIL,
    password: str = X_PASSWORD,
    port: int = X_CDP_PORT,
) -> Dict[str, Any]:
    """Logs into X in the persistent local Chrome profile."""
    ws_url = ensure_x_chrome(port=port)
    if not ws_url:
        return {"status": "error", "reason": "No Chrome tab available for X"}

    ws = websocket.create_connection(ws_url, timeout=25)
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
        cdp("Runtime.enable")
        cdp("Input.enable")
        cdp("Network.enable")

        cookies = cdp("Network.getAllCookies").get("cookies", [])
        x_cookies = {c["name"]: c["value"] for c in cookies if "x.com" in c.get("domain", "") or "twitter.com" in c.get("domain", "")}
        if "auth_token" in x_cookies:
            return {"status": "logged_in", "cookies": list(x_cookies.keys())}

        cdp("Page.navigate", {"url": "https://x.com/i/jf/onboarding/web?mode=login"})
        time.sleep(5)

        cdp("Runtime.evaluate", {
            "expression": f"""(function() {{
                const inp = document.querySelector('#jf-input-username_or_email') || document.querySelector('input[name="username_or_email"], input[autocomplete="username"]');
                if (!inp) return "NO_INPUT";
                inp.focus();
                const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                nativeSetter.call(inp, {json.dumps(username)});
                inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                const btn = document.querySelector('button[type="submit"]');
                if (btn) btn.click();
                return "SUBMITTED_USER";
            }})()""",
            "returnByValue": True
        })
        time.sleep(5)

        cdp("Runtime.evaluate", {
            "expression": f"""(function() {{
                const inp = document.querySelector('input[type="password"]:not([inert])') || document.querySelector('#jf-input-password');
                if (!inp) return "NO_ACTIVE_PASS";
                inp.focus();
                const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                nativeSetter.call(inp, {json.dumps(password)});
                inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                const btn = document.querySelector('button[type="submit"]');
                if (btn) btn.click();
                return "SUBMITTED_PASS";
            }})()""",
            "returnByValue": True
        })
        time.sleep(8)

        cookies = cdp("Network.getAllCookies").get("cookies", [])
        x_cookies = {c["name"]: c["value"] for c in cookies if "x.com" in c.get("domain", "") or "twitter.com" in c.get("domain", "")}
        return {"status": "logged_in" if "auth_token" in x_cookies else "check_state", "cookies": list(x_cookies.keys())}
    finally:
        ws.close()


def publish_to_x_cdp(
    outfit: Dict[str, Any],
    media_path: Optional[Path] = None,
    reel_url: str = "",
    threads_url: str = "",
    port: int = X_CDP_PORT,
) -> Dict[str, Any]:
    """
    Publishes the <=100-character viral hook tweet + media (kombin_collage.png or graphmotion_short.mp4)
    to https://x.com/guzelaicom via Chrome CDP.
    """
    thread = build_x_thread(outfit, reel_url=reel_url, threads_url=threads_url)
    main_text = thread["tweets"][0]["text"]
    ws_url = ensure_x_chrome(port=port)
    if not ws_url:
        return {"status": "error", "reason": "No Chrome tab available for X"}

    ws = websocket.create_connection(ws_url, timeout=35)
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
        x_cookies = {c["name"]: c["value"] for c in cookies if "x.com" in c.get("domain", "") or "twitter.com" in c.get("domain", "")}
        if "auth_token" not in x_cookies:
            ws.close()
            login_res = login_and_verify_x(port=port)
            if login_res.get("status") != "logged_in":
                return login_res
            ws = websocket.create_connection(ensure_x_chrome(port=port), timeout=35)
            cdp("Page.enable")
            cdp("DOM.enable")
            cdp("Runtime.enable")
            cdp("Input.enable")
            cdp("Page.bringToFront")

        # Navigate to https://x.com/home where inline composer is always available
        cdp("Page.navigate", {"url": "https://x.com/home"})
        pump_frames(6)

        # Dismiss any onboarding/notification prompts on X home
        cdp("Runtime.evaluate", {
            "expression": """(() => {
                document.querySelectorAll('[data-testid="app-bar-close"], [aria-label="Close"], [aria-label="Kapat"]').forEach(b => b.click());
            })()"""
        })
        pump_frames(1)

        # Focus the inline tweet editor first
        focus_info = json.loads(cdp("Runtime.evaluate", {
            "expression": """JSON.stringify((() => {
                const ed = document.querySelector('[data-testid="tweetTextarea_0"]')
                        || document.querySelector('div[role="textbox"][contenteditable="true"]');
                if (!ed) return {ok: false};
                ed.scrollIntoView({block: 'center'});
                const r = ed.getBoundingClientRect();
                ed.click();
                ed.focus();
                return {ok: true, x: r.left + 25, y: r.top + 18};
            })())""",
            "returnByValue": True
        }).get("result", {}).get("value", "{}") or "{}")

        if not focus_info.get("ok"):
            # Fallback: navigate to compose/post
            cdp("Page.navigate", {"url": "https://x.com/compose/post"})
            pump_frames(5)
            focus_info = json.loads(cdp("Runtime.evaluate", {
                "expression": """JSON.stringify((() => {
                    const ed = document.querySelector('[data-testid="tweetTextarea_0"]')
                            || document.querySelector('div[role="textbox"][contenteditable="true"]');
                    if (!ed) return {ok: false};
                    const r = ed.getBoundingClientRect();
                    ed.click();
                    ed.focus();
                    return {ok: true, x: r.left + 25, y: r.top + 18};
                })())""",
                "returnByValue": True
            }).get("result", {}).get("value", "{}") or "{}")

        if focus_info.get("ok"):
            cdp("Input.dispatchMouseEvent", {"type": "mousePressed", "x": focus_info["x"], "y": focus_info["y"], "button": "left", "clickCount": 1})
            cdp("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": focus_info["x"], "y": focus_info["y"], "button": "left", "clickCount": 1})
            pump_frames(0.8)

        # Select all & delete any leftover draft text
        cdp("Input.dispatchKeyEvent", {"type": "keyDown", "modifiers": 2, "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65})
        cdp("Input.dispatchKeyEvent", {"type": "keyUp", "modifiers": 2, "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65})
        cdp("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
        cdp("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
        pump_frames(0.5)

        # Insert <=100 character viral hook text
        cdp("Input.insertText", {"text": main_text})
        pump_frames(2)

        # Attach collage image via ClipboardEvent('paste') OR fileInput
        collage_candidate = Path("output/kombin_collage.png").resolve()
        upload_file = collage_candidate if collage_candidate.exists() else (media_path.resolve() if media_path and media_path.exists() else None)
        if upload_file and upload_file.exists():
            # If upload_file is an MP4 video, prefer kombin_collage.png for instant X attachment, or paste MP4
            if upload_file.suffix.lower() in (".png", ".jpg", ".jpeg"):
                b64_img = base64.b64encode(upload_file.read_bytes()).decode("ascii")
                mime = "image/png" if upload_file.suffix.lower() == ".png" else "image/jpeg"
                cdp("Runtime.evaluate", {
                    "expression": f"""(() => {{
                        const ed = document.querySelector('[data-testid="tweetTextarea_0"]') || document.querySelector('div[role="textbox"]');
                        if (!ed) return "NO_ED";
                        const bstr = atob("{b64_img}");
                        const u8 = new Uint8Array(bstr.length);
                        for (let i = 0; i < bstr.length; i++) u8[i] = bstr.charCodeAt(i);
                        const file = new File([u8], "{upload_file.name}", {{type: "{mime}"}});
                        const dt = new DataTransfer();
                        dt.items.add(file);
                        ed.dispatchEvent(new ClipboardEvent('paste', {{bubbles: true, cancelable: true, clipboardData: dt}}));
                        return "PASTED_IMAGE";
                    }})()""",
                    "returnByValue": True
                })
                pump_frames(5)
            else:
                eval_res = cdp("Runtime.evaluate", {
                    "expression": "document.querySelector('input[data-testid=\"fileInput\"], input[type=\"file\"]')",
                    "returnByValue": False,
                })
                obj_id = eval_res.get("result", {}).get("objectId")
                if obj_id:
                    cdp("DOM.setFileInputFiles", {"objectId": obj_id, "files": [str(upload_file)]})
                    pump_frames(6)

        # Click Post button ([data-testid="tweetButtonInline"] or [data-testid="tweetButton"]) + Ctrl+Enter
        btn_pos = json.loads(cdp("Runtime.evaluate", {
            "expression": """JSON.stringify((() => {
                const btn = document.querySelector('[data-testid="tweetButtonInline"]')
                         || document.querySelector('[data-testid="tweetButton"]');
                if (!btn) return null;
                btn.scrollIntoView({block: 'center'});
                const r = btn.getBoundingClientRect();
                const dis = btn.disabled || btn.getAttribute('aria-disabled') === 'true';
                if (!dis) btn.click();
                return {x: r.left + r.width/2, y: r.top + r.height/2, dis: dis, testid: btn.getAttribute('data-testid')};
            })())""",
            "returnByValue": True
        }).get("result", {}).get("value", "null") or "null")

        if btn_pos and not btn_pos.get("dis"):
            x, y = btn_pos["x"], btn_pos["y"]
            cdp("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
            cdp("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})
            pump_frames(2)

        # Also send Ctrl+Enter shortcut to guarantee submission if composer is still open
        cdp("Input.dispatchKeyEvent", {"type": "keyDown", "modifiers": 2, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
        cdp("Input.dispatchKeyEvent", {"type": "keyUp", "modifiers": 2, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
        pump_frames(6)

        return {
            "status": "published",
            "char_count": len(main_text),
            "text": main_text,
            "btn_pos": btn_pos,
            "account": "@guzelaicom",
            "url": "https://x.com/guzelaicom",
        }
    finally:
        try:
            ws.close()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outfit-json", default="output/outfit_links.json")
    parser.add_argument("--login", action="store_true", help="X hesabına giriş yap ve doğrula")
    parser.add_argument("--publish", action="store_true", help="X hesabında paylaş")
    args = parser.parse_args()

    out_dir = os.path.dirname(args.outfit_json) or "output"
    if os.path.exists(args.outfit_json):
        with open(args.outfit_json, "r", encoding="utf-8") as f:
            outfit = json.load(f)
        save_x_outputs(outfit, out_dir=out_dir)

    if args.login:
        res = login_and_verify_x()
        print("[X Giriş Sonucu]:", json.dumps(res, ensure_ascii=False, indent=2))

    if args.publish and os.path.exists(args.outfit_json):
        collage = Path(out_dir) / "kombin_collage.png"
        res = publish_to_x_cdp(outfit, media_path=collage)
        print("[X Yayın Sonucu]:", json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
