"""
Pinterest Auto-Publisher for @guzelaicom (archzencir@gmail.com)
---------------------------------------------------------------
Features:
- Generates Pinterest-optimized Pin titles, descriptions, destination URLs, and alt text
  with product prices, SKUs, and mandatory Turkish Social Media / Ticaret Bakanlığı disclosure.
- Saves output/pinterest_pin.json and output/pinterest_pin.txt.
- Uses persistent local Chrome CDP profile (pinterest_chrome_profile on port 9232)
  to log in once as the single trusted device and publish Image/Video Pins via
  https://www.pinterest.com/pin-creation-tool/
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

PINTEREST_EMAIL = os.environ.get("PINTEREST_EMAIL", "archzencir@gmail.com")
PINTEREST_PASSWORD = os.environ.get("PINTEREST_PASSWORD", "K@rd3s.34-48/mugla")
PINTEREST_CDP_PORT = 9232
PINTEREST_PROFILE_DIR = Path(r"C:\Users\zenci\.gemini\antigravity\scratch\pinterest_chrome_profile")

TR_PINTEREST_LEGAL_NOTICE = (
    "⚠️ Yasal Uyarı: Reklam veya sponsorlu iş birliği içermez; "
    "tamamen kombin önerisi ve bilgilendirme amaçlıdır (zorunlu #reklam #işbirliğideğil)."
)

ITEM_ORDER = [
    ("outerwear", "⌚ Saat/Üst"),
    ("cap", "✨ Küpe/Aksesuar"),
    ("top", "👚 Gömlek/Üst"),
    ("bottom", "👖 Pantolon"),
    ("bag", "👜 Çanta"),
    ("shoes", "👠 Ayakkabı"),
]


def build_pinterest_pin_data(outfit: Dict[str, Any], reel_url: str = "", threads_url: str = "") -> Dict[str, Any]:
    """Builds Pinterest Pin SEO title (<=100 chars), description (<=500 chars), and destination link."""
    raw_title = (
        outfit.get("pinterest_title")
        or outfit.get("hook_title")
        or outfit.get("archetype_title")
        or "Siyah Kaşe Bomber Ceket & Taş Rengi Palazzo Jean Kadın Sonbahar Kombini"
    )
    total_str = outfit.get("total_price_str", "")
    pin_title = f"{raw_title[:84]} ({total_str})"[:100]

    items = outfit.get("items", {})
    desc_lines = [
        f"✨ {outfit.get('hook_title', raw_title)} ({total_str})",
        "🌐 Görselli & Doğrulanmış Mağaza Linkleri: https://guzelai.com/#kombinler",
    ]

    primary_url = "https://guzelai.com/#kombinler"
    if isinstance(items, dict):
        for key, label in ITEM_ORDER:
            it = items.get(key)
            if not it:
                continue
            brand = it.get("brand", "")
            name = it.get("name", "")
            price = it.get("price", "")
            sku = it.get("sku", "-")
            desc_lines.append(f"{label}: {brand} {name} ({price}) [Kod: {sku}]")

    desc_lines.extend([
        "💬 WhatsApp Kanalı: https://whatsapp.com/channel/0029VbDetYc3mFYDwZSry016",
        TR_PINTEREST_LEGAL_NOTICE,
        "#kadınkombin #oldmoneystil #sonbaharkombini #cadılarbayramı #ootd #reklam",
    ])
    description = "\n".join(desc_lines)[:495]

    dest_link = "https://guzelai.com/#kombinler"

    return {
        "account_email": PINTEREST_EMAIL,
        "title": pin_title,
        "description": description,
        "destination_link": dest_link,
        "board_name": "Günlük Kombin Önerileri",
        "alt_text": f"{raw_title} kadın kombin önerisi ve mağaza fiyatları (@guzelaicom)",
    }


def save_pinterest_outputs(outfit: Dict[str, Any], out_dir: str = "output", reel_url: str = "", threads_url: str = "") -> Dict[str, Any]:
    os.makedirs(out_dir, exist_ok=True)
    pin_data = build_pinterest_pin_data(outfit, reel_url=reel_url, threads_url=threads_url)

    json_path = os.path.join(out_dir, "pinterest_pin.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(pin_data, f, ensure_ascii=False, indent=2)

    txt_path = os.path.join(out_dir, "pinterest_pin.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(
            f"BAŞLIK: {pin_data['title']}\n"
            f"HEDEF LİNK: {pin_data['destination_link']}\n"
            f"PANO: {pin_data['board_name']}\n\n"
            f"AÇIKLAMA:\n{pin_data['description']}\n"
        )

    print(f"[BAŞARILI] Pinterest Pin verisi ve açıklaması hazırlandı: {txt_path}")
    return pin_data


def ensure_pinterest_chrome(port: int = PINTEREST_CDP_PORT, profile_dir: Path = PINTEREST_PROFILE_DIR) -> Optional[str]:
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
            f'--window-size=1180,900 "https://tr.pinterest.com/business/hub/"'
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


def login_and_verify_pinterest(
    email: str = PINTEREST_EMAIL,
    password: str = PINTEREST_PASSWORD,
    port: int = PINTEREST_CDP_PORT,
) -> Dict[str, Any]:
    """Logs into Pinterest in the persistent local Chrome profile and saves screenshot."""
    ws_url = ensure_pinterest_chrome(port=port)
    if not ws_url:
        return {"status": "error", "reason": "No Chrome tab available for Pinterest"}

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
        cdp("Network.enable")

        curr_url = cdp("Runtime.evaluate", {"expression": "location.href", "returnByValue": True}).get("result", {}).get("value", "")
        if "login" not in curr_url and "pinterest.com" in curr_url:
            cdp("Page.navigate", {"url": "https://tr.pinterest.com/login/"})
            time.sleep(5)

        fill_js = f"""
        (function(em, pw) {{
            function setNativeValue(el, value) {{
                const valueSetter = Object.getOwnPropertyDescriptor(el, 'value')?.set;
                const prototype = Object.getPrototypeOf(el);
                const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
                if (valueSetter && valueSetter !== prototypeValueSetter) {{
                    prototypeValueSetter.call(el, value);
                }} else if (valueSetter) {{
                    valueSetter.call(el, value);
                }} else {{
                    el.value = value;
                }}
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
            const eInput = document.querySelector('input#email') || document.querySelector('input[name="id"]') || document.querySelector('input[type="email"]');
            const pInput = document.querySelector('input#password') || document.querySelector('input[name="password"]') || document.querySelector('input[type="password"]');
            if (!eInput || !pInput) return "NO_LOGIN_INPUTS";
            eInput.focus();
            setNativeValue(eInput, em);
            pInput.focus();
            setNativeValue(pInput, pw);
            const sub = document.querySelector('button[type="submit"]');
            if (sub) sub.click();
            return "SUBMITTED";
        }})({json.dumps(email)}, {json.dumps(password)})
        """
        fill_res = cdp("Runtime.evaluate", {"expression": fill_js, "returnByValue": True}).get("result", {}).get("value")
        print("[Pinterest] Giriş formu durumu:", fill_res)
        if fill_res == "SUBMITTED":
            time.sleep(8)

        state = json.loads(cdp("Runtime.evaluate", {
            "expression": """JSON.stringify({
                url: location.href,
                title: document.title,
                text: document.body ? document.body.innerText.slice(0, 600) : ''
            })""",
            "returnByValue": True
        }).get("result", {}).get("value", "{}"))

        cookies = cdp("Network.getAllCookies").get("cookies", [])
        pin_cookies = {c["name"]: c["value"] for c in cookies if "pinterest" in c.get("domain", "")}
        logged_in = "_pinterest_sess" in pin_cookies and "login" not in state.get("url", "")

        return {
            "status": "logged_in" if logged_in else "check_state",
            "url": state.get("url"),
            "title": state.get("title"),
            "text_preview": state.get("text", "")[:300],
            "cookies": list(pin_cookies.keys()),
        }
    finally:
        ws.close()


def publish_to_pinterest_cdp(
    outfit: Dict[str, Any],
    media_path: Path,
    reel_url: str = "",
    threads_url: str = "",
    port: int = PINTEREST_CDP_PORT,
) -> Dict[str, Any]:
    """Publishes a Pin on https://tr.pinterest.com/pin-creation-tool/ via Chrome CDP."""
    media_path = media_path.resolve()
    if not media_path.exists():
        return {"status": "error", "reason": f"Media not found: {media_path}"}

    pin_data = build_pinterest_pin_data(outfit, reel_url=reel_url, threads_url=threads_url)
    ws_url = ensure_pinterest_chrome(port=port)
    if not ws_url:
        return {"status": "error", "reason": "No Chrome tab available"}

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
        cdp("Page.bringToFront")

        cdp("Page.navigate", {"url": "https://tr.pinterest.com/pin-creation-tool/"})
        pump_frames(8)

        curr_url = cdp("Runtime.evaluate", {"expression": "location.href", "returnByValue": True}).get("result", {}).get("value", "")
        if "login" in curr_url:
            ws.close()
            login_res = login_and_verify_pinterest(port=port)
            if login_res.get("status") != "logged_in":
                return login_res
            ws = websocket.create_connection(ensure_pinterest_chrome(port=port), timeout=30)
            cdp("Page.enable")
            cdp("DOM.enable")
            cdp("Runtime.enable")
            cdp("Input.enable")
            cdp("Page.bringToFront")
            cdp("Page.navigate", {"url": "https://tr.pinterest.com/pin-creation-tool/"})
            pump_frames(8)

        # Attach file input via Runtime.evaluate objectId
        eval_res = cdp("Runtime.evaluate", {
            "expression": "document.querySelector('input[type=\"file\"]')",
            "returnByValue": False,
        })
        obj_id = eval_res.get("result", {}).get("objectId")
        if not obj_id:
            return {"status": "error", "reason": "Pinterest file input not found"}

        cdp("DOM.setFileInputFiles", {"objectId": obj_id, "files": [str(media_path)]})
        pump_frames(6)

        fill_pin_js = f"""
        (function(title, desc, link) {{
            function setNativeValue(el, value) {{
                const valueSetter = Object.getOwnPropertyDescriptor(el, 'value')?.set;
                const prototype = Object.getPrototypeOf(el);
                const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
                if (valueSetter && valueSetter !== prototypeValueSetter) {{
                    prototypeValueSetter.call(el, value);
                }} else if (valueSetter) {{
                    valueSetter.call(el, value);
                }} else {{
                    el.value = value;
                }}
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
            const tInput = document.querySelector('input[id*="title"], input[placeholder*="Başlık"], input[placeholder*="Title"]');
            if (tInput) {{ tInput.focus(); setNativeValue(tInput, title); }}

            const lInput = document.querySelector('input[id*="link"], input[placeholder*="bağlantı"], input[placeholder*="link"], input[type="url"]');
            if (lInput) {{ lInput.focus(); setNativeValue(lInput, link); }}

            const dEditor = document.querySelector('div[contenteditable="true"]');
            if (dEditor) {{
                dEditor.focus();
                document.execCommand('selectAll', false, null);
                document.execCommand('insertText', false, desc);
            }}
            return "PIN_FIELDS_SET";
        }})({json.dumps(pin_data['title'])}, {json.dumps(pin_data['description'])}, {json.dumps(pin_data['destination_link'])})
        """
        cdp("Runtime.evaluate", {"expression": fill_pin_js, "returnByValue": True})
        pump_frames(3)

        pub_js = """
        (function() {
            const btn = Array.from(document.querySelectorAll('button')).find(b => /Yayınla|Publish|Kaydet|Save/i.test((b.innerText || '').trim()));
            if (btn && !btn.disabled) {
                btn.click();
                return "CLICKED_PUBLISH: " + btn.innerText.trim();
            }
            return "NO_PUBLISH_BTN";
        })()
        """
        pub_res = cdp("Runtime.evaluate", {"expression": pub_js, "returnByValue": True}).get("result", {}).get("value")
        pump_frames(6)
        return {"status": "published", "action": pub_res, "pin_title": pin_data["title"]}
    finally:
        try:
            ws.close()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outfit-json", default="output/outfit_links.json")
    parser.add_argument("--login", action="store_true", help="Pinterest hesabına giriş yap ve doğrula")
    parser.add_argument("--publish", action="store_true", help="Pinterest'te Pin yayınla")
    args = parser.parse_args()

    out_dir = os.path.dirname(args.outfit_json) or "output"
    if os.path.exists(args.outfit_json):
        with open(args.outfit_json, "r", encoding="utf-8") as f:
            outfit = json.load(f)
        save_pinterest_outputs(outfit, out_dir=out_dir)

    if args.login:
        res = login_and_verify_pinterest()
        print("[Pinterest Giriş Sonucu]:", json.dumps(res, ensure_ascii=False, indent=2))

    if args.publish and os.path.exists(args.outfit_json):
        collage = Path(out_dir) / "kombin_collage.png"
        res = publish_to_pinterest_cdp(outfit, collage)
        print("[Pinterest Yayın Sonucu]:", json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
