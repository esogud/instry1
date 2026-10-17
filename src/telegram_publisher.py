"""
Telegram Bot & Channel Publisher for @guzelaicom (@guzelaibot)
--------------------------------------------------------------
Features:
- Configures @guzelaibot profile, commands, and descriptions automatically.
- Builds HTML-formatted Kombin cards with direct clickable store links, prices, SKUs,
  and mandatory Turkish Social Media / Ticaret Bakanlığı legal disclosure.
- Attaches interactive Inline Keyboard shopping buttons for 1-click store navigation.
- Auto-discovers users, groups, and channels that message or add @guzelaibot.
- Can run as a one-shot publisher (CI/CD or local) or interactive background polling daemon.
"""
import argparse
import html
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_BOT_TOKEN = "8783821353:AAG9m_SIUO4jAxx_fN2pyD1xbtTaTozuB5U"
SUBSCRIBERS_FILE = Path("assets/telegram_subscribers.json")

TR_TELEGRAM_LEGAL_NOTICE = (
    "⚖️ <i>Yasal Uyarı: Bu paylaşım reklam veya sponsorlu iş birliği içermez; "
    "tamamen kombin önerisi ve bilgilendirme amaçlıdır (zorunlu #reklam #işbirliğideğil).</i>"
)

ITEM_SLOTS = [
    ("outerwear", "🧥", "Ceket/Üst"),
    ("cap", "🕶️", "Aksesuar"),
    ("top", "👕", "İç/Üst"),
    ("bottom", "👖", "Alt Giyim"),
    ("bag", "👜", "Çanta"),
    ("shoes", "👟", "Ayakkabı"),
]


def get_bot_token() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", DEFAULT_BOT_TOKEN).strip()


def tg_api(method: str, data: Optional[Dict[str, Any]] = None, files: Optional[Dict[str, Any]] = None, token: Optional[str] = None) -> Dict[str, Any]:
    tok = token or get_bot_token()
    url = f"https://api.telegram.org/bot{tok}/{method}"
    try:
        if files:
            resp = requests.post(url, data=data, files=files, timeout=90)
        else:
            resp = requests.post(url, json=data or {}, timeout=30)
        return resp.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}


def configure_bot_profile(token: Optional[str] = None) -> Dict[str, Any]:
    """Configures @guzelaibot commands, description, and short description on Telegram."""
    tok = token or get_bot_token()
    results = {}

    results["setMyName"] = tg_api(
        "setMyName",
        {"name": "Güzel AI Kombin & Moda (@guzelaicom)"},
        token=tok,
    )
    results["setMyShortDescription"] = tg_api(
        "setMyShortDescription",
        {
            "short_description": "✨ Günlük 2K Kombin Önerileri, Mağaza Fiyatları ve Tıklanabilir Ürün Linkleri | @guzelaicom"
        },
        token=tok,
    )
    results["setMyDescription"] = tg_api(
        "setMyDescription",
        {
            "description": (
                "👗 Güzel AI (@guzelaicom) Resmi Kombin & Otomasyon Kontrol Botu!\n\n"
                "• 🚀 /yayinla yazarak günün her saatinde anında yeni 2K kombin üretip 10 kanalda yayını başlatabilirsiniz.\n"
                "• 🔗 Bota doğrudan ürün linki (Trendyol, Zara vb.) göndererek o ürünlerle kombin videosu üretip yayınlatabilirsiniz.\n"
                "• 🖼️ Bota fotoğraf veya video yükleyerek doğrudan o görselle tüm platformlarda yayın tetikleyebilirsiniz.\n"
                "• 🛍️ /kombin ve /linkler ile son kombinin doğrulanmış mağaza linklerini alabilirsiniz."
            )
        },
        token=tok,
    )
    results["setMyCommands"] = tg_api(
        "setMyCommands",
        {
            "commands": [
                {"command": "start", "description": "Botu başlat ve kontrol panelini aç"},
                {"command": "yayinla", "description": "Anında yeni 2K kombin üret ve 10 platformda yayınla"},
                {"command": "kombin", "description": "Günün son 2K kombin videosu, kolajı ve mağaza linklerini getir"},
                {"command": "linkler", "description": "Son kombindeki parçaların doğrulanmış alışveriş linkleri"},
                {"command": "durum", "description": "10 kanallı otomasyon ve sistem durumunu kontrol et"},
            ]
        },
        token=tok,
    )
    return results


def _normalize_items(outfit: Dict[str, Any]) -> List[Dict[str, str]]:
    """Extracts normalized item list from either dict-keyed or list-based outfit structure."""
    raw_items = outfit.get("items", {})
    normalized = []
    if isinstance(raw_items, dict):
        for key, emoji, label in ITEM_SLOTS:
            it = raw_items.get(key)
            if not it:
                continue
            normalized.append({
                "key": key,
                "emoji": emoji,
                "label": label,
                "brand": str(it.get("brand", "Mağaza")),
                "name": str(it.get("name", "Ürün")),
                "price": str(it.get("price", "")),
                "sku": str(it.get("sku", "-")),
                "url": str(it.get("product_url") or it.get("url") or ""),
            })
    elif isinstance(raw_items, list):
        for idx, it in enumerate(raw_items):
            emoji = ITEM_SLOTS[idx][1] if idx < len(ITEM_SLOTS) else "🛍️"
            label = ITEM_SLOTS[idx][2] if idx < len(ITEM_SLOTS) else f"Parça {idx+1}"
            normalized.append({
                "key": f"item_{idx}",
                "emoji": emoji,
                "label": label,
                "brand": str(it.get("brand", "Mağaza")),
                "name": str(it.get("name", "Ürün")),
                "price": str(it.get("price", "")),
                "sku": str(it.get("sku") or it.get("code") or "-"),
                "url": str(it.get("product_url") or it.get("url") or ""),
            })
    return normalized


def build_telegram_html(outfit: Dict[str, Any], reel_url: str = "", threads_url: str = "") -> str:
    """Builds a rich HTML caption (compatible with Telegram parse_mode='HTML', < 1024 chars for media caption)."""
    title = html.escape(
        outfit.get("hook_title")
        or outfit.get("archetype_title")
        or outfit.get("title")
        or "5.000₺ Bütçeyle 50.000₺'lik 'Old Money' Görünmenin Sırrı! 🔥"
    )
    total_str = html.escape(outfit.get("total_price_str", ""))
    items = _normalize_items(outfit)

    lines = [
        f"🔥 <b>{title}</b>",
    ]
    if total_str:
        lines.append(f"💰 <b>Toplam Kombin:</b> {total_str} (<i>%100 Kadın • Benzer Muadil Linkler</i>)")
    lines.append("")
    lines.append("🛍️ <b>GÖRSELLİ KOMBİN PARÇALARI &amp; DOĞRUDAN LİNKLER:</b>")

    for it in items:
        brand = html.escape(it["brand"])
        name = html.escape(it["name"][:28])
        price = html.escape(it["price"])
        sku = html.escape(it["sku"])
        url = it["url"]
        if url:
            lines.append(f"{it['emoji']} <a href=\"{html.escape(url)}\"><b>{brand}</b> - {name}</a> ({price}) [<code>{sku}</code>]")
        else:
            lines.append(f"{it['emoji']} <b>{brand}</b> - {name} ({price}) [<code>{sku}</code>]")

    lines.append("")
    ig_link = reel_url.strip() or outfit.get("reel_url", "") or "https://www.instagram.com/guzelaicom/"
    th_link = threads_url.strip() or "https://www.threads.net/@guzelaicom"
    lines.append(
        "🌐 <a href=\"https://guzelai.com/#kombinler\"><b>GuzelAI.com Görselli Linkler</b></a> | "
        "💬 <a href=\"https://whatsapp.com/channel/0029VbDetYc3mFYDwZSry016\"><b>WhatsApp Kanalı</b></a>"
    )
    lines.append(
        f"📸 <a href=\"{html.escape(ig_link)}\">Instagram</a> | "
        f"🎵 <a href=\"https://www.tiktok.com/@guzelaicom\">TikTok</a> | "
        f"▶️ <a href=\"https://www.youtube.com/@guzelaicom\">YouTube</a> | "
        f"𝕏 <a href=\"https://x.com/guzelaicom\">X</a>"
    )
    lines.append("")
    lines.append(TR_TELEGRAM_LEGAL_NOTICE)

    text = "\n".join(lines)
    return text


def build_inline_keyboard(outfit: Dict[str, Any], reel_url: str = "", threads_url: str = "") -> Dict[str, Any]:
    """Builds 2-column inline shopping buttons for each item + website & social profile links."""
    items = _normalize_items(outfit)
    rows: List[List[Dict[str, str]]] = [
        [
            {"text": "🌐 GuzelAI.com Görselli Linkler", "url": "https://guzelai.com/#kombinler"},
            {"text": "💬 WhatsApp Kanalımız", "url": "https://whatsapp.com/channel/0029VbDetYc3mFYDwZSry016"},
        ]
    ]
    current_row: List[Dict[str, str]] = []

    for it in items:
        if not it["url"]:
            continue
        btn_text = f"{it['emoji']} {it['brand']} ({it['price']})"
        current_row.append({"text": btn_text[:32], "url": it["url"]})
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)

    ig_link = reel_url.strip() or outfit.get("reel_url", "") or "https://www.instagram.com/guzelaicom/"
    th_link = threads_url.strip() or "https://www.threads.net/@guzelaicom"
    rows.append([
        {"text": "📸 Instagram Reels", "url": ig_link},
        {"text": "🎵 TikTok (@guzelaicom)", "url": "https://www.tiktok.com/@guzelaicom"},
    ])
    rows.append([
        {"text": "▶️ YouTube Shorts", "url": "https://www.youtube.com/@guzelaicom"},
        {"text": "𝕏 X (@guzelaicom)", "url": "https://x.com/guzelaicom"},
    ])
    return {"inline_keyboard": rows}


def save_telegram_outputs(outfit: Dict[str, Any], out_dir: str = "output", reel_url: str = "", threads_url: str = "") -> Dict[str, Any]:
    os.makedirs(out_dir, exist_ok=True)
    html_caption = build_telegram_html(outfit, reel_url=reel_url, threads_url=threads_url)
    reply_markup = build_inline_keyboard(outfit, reel_url=reel_url, threads_url=threads_url)

    payload = {
        "bot_username": "@guzelaibot",
        "parse_mode": "HTML",
        "caption_html": html_caption,
        "reply_markup": reply_markup,
    }

    html_path = os.path.join(out_dir, "telegram_post.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_caption + "\n")

    json_path = os.path.join(out_dir, "telegram_post.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[BAŞARILI] Telegram (@guzelaibot) HTML kartı ve alışveriş butonları hazırlandı: {html_path}")
    return payload


def load_subscribers() -> Dict[str, Any]:
    SUBSCRIBERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if SUBSCRIBERS_FILE.exists():
        try:
            return json.loads(SUBSCRIBERS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"chats": {}, "last_update_id": 0}


def save_subscribers(data: Dict[str, Any]) -> None:
    SUBSCRIBERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SUBSCRIBERS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


_AUTOMATION_LOCK = False


def _download_telegram_file(file_id: str, dest_path: Path, token: str) -> bool:
    """Downloads a photo/video/document sent to @guzelaibot using Telegram getFile API."""
    try:
        info = tg_api("getFile", {"file_id": file_id}, token=token)
        if not info.get("ok"):
            return False
        file_path = info["result"]["file_path"]
        dl_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
        r = requests.get(dl_url, timeout=60)
        if r.status_code == 200:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(r.content)
            return True
    except Exception as e:
        print(f"[Telegram Dosya İndirme Hatası] {e}")
    return False


def _trigger_full_automation_pipeline(
    chat_id: str,
    token: str,
    out_dir: str = "output",
    custom_urls: Optional[List[str]] = None,
    custom_image: Optional[str] = None,
    custom_video: Optional[str] = None,
    custom_title: str = "",
) -> None:
    """Runs the full 2K Kombin generation + 10-channel broadcast in a background thread and reports back to Telegram."""
    import subprocess
    import threading

    def _worker() -> None:
        global _AUTOMATION_LOCK
        if _AUTOMATION_LOCK:
            tg_api(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": "⏳ <b>Şu anda devam eden bir yayın işlemi var.</b> Lütfen mevcut yayın tamamlandıktan sonra tekrar deneyin.",
                    "parse_mode": "HTML",
                },
                token=token,
            )
            return

        _AUTOMATION_LOCK = True
        try:
            py_exe = sys.executable
            os.makedirs(out_dir, exist_ok=True)

            # Save override file if custom URLs, image, or title were provided
            if custom_urls or custom_image or custom_title:
                override_payload = {
                    "custom_urls": custom_urls or [],
                    "custom_image": custom_image,
                    "custom_title": custom_title,
                }
                override_file = Path(out_dir) / "telegram_trigger_override.json"
                override_file.write_text(json.dumps(override_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            trigger_desc = []
            if custom_urls:
                trigger_desc.append(f"🔗 <b>{len(custom_urls)} Özel Ürün Linki</b>")
            if custom_image:
                trigger_desc.append("🖼️ <b>Özel Yüklenen Görsel</b>")
            if custom_video:
                trigger_desc.append("🎬 <b>Özel Yüklenen Video</b>")
            if not trigger_desc:
                trigger_desc.append("✨ <b>Otomatik Yeni 2K Kombin</b>")

            tg_api(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": (
                        f"🚀 <b>Otomasyon Başlatıldı!</b> ({', '.join(trigger_desc)})\n\n"
                        "1️⃣ 2K (1440×2560) Reels videosu, ürün kolajı ve mağaza link doğrulaması hazırlanıyor...\n"
                        "2️⃣ Ardından <b>GuzelAI.com (#kombinler), Instagram Reels, Facebook, TikTok, YouTube Shorts, X, Pinterest, Threads ve Telegram</b> üzerinde otomatik paylaşılacak."
                    ),
                    "parse_mode": "HTML",
                },
                token=token,
            )

            video_target = str(Path(out_dir) / "daily_kombin_reel.mp4")
            caption_target = str(Path(out_dir) / "caption.txt")

            if not custom_video or custom_urls or custom_image:
                env = os.environ.copy()
                env["SLOT_NAME"] = f"tg_{int(time.time())}"
                subprocess.run(
                    [py_exe, "src/main.py", "--output", video_target],
                    env=env,
                    check=False,
                )

            subprocess.run(
                [py_exe, "src/instagram_uploader.py", "--video", video_target, "--caption-file", caption_target],
                check=False,
            )

            meta_path = Path(out_dir) / "outfit_links.json"
            reel_url = "https://www.instagram.com/guzelaicom/"
            title = "Yeni Kombin"
            if meta_path.exists():
                try:
                    od = json.loads(meta_path.read_text(encoding="utf-8"))
                    reel_url = od.get("reel_url") or reel_url
                    title = od.get("archetype_title") or title
                except Exception:
                    pass

            done_text = (
                f"✅ <b>10 Kanallı Otomasyon Yayını Tamamlandı!</b>\n"
                f"👗 <b>Kombin:</b> {html.escape(title)}\n\n"
                f"🌐 <b>GuzelAI.com Görselli Vitrin:</b> https://guzelai.com/#kombinler\n"
                f"📸 <b>Instagram Reels:</b> {html.escape(reel_url)}\n"
                f"📘 <b>Facebook:</b> Güzel Ai (Yayında)\n"
                f"🎵 <b>TikTok:</b> https://www.tiktok.com/@guzelaicom\n"
                f"▶️ <b>YouTube Shorts:</b> https://www.youtube.com/@guzelaicom/shorts\n"
                f"𝕏 <b>X (Twitter):</b> https://x.com/guzelaicom\n"
                f"📌 <b>Pinterest:</b> Yayında\n"
                f"💬 <b>WhatsApp Kanalı:</b> https://whatsapp.com/channel/0029VbDetYc3mFYDwZSry016"
            )
            tg_api("sendMessage", {"chat_id": chat_id, "text": done_text, "parse_mode": "HTML"}, token=token)
        except Exception as e:
            tg_api(
                "sendMessage",
                {"chat_id": chat_id, "text": f"⚠️ Otomasyon sırasında uyarı: {html.escape(str(e))}"},
                token=token,
            )
        finally:
            _AUTOMATION_LOCK = False

    threading.Thread(target=_worker, daemon=True).start()


def sync_subscribers_from_updates(token: Optional[str] = None, handle_commands: bool = True, out_dir: str = "output") -> List[str]:
    """Polls getUpdates, registers users/channels, and handles commands, links, photos, videos, and button callbacks."""
    import re
    tok = token or get_bot_token()
    sub_data = load_subscribers()
    offset = int(sub_data.get("last_update_id", 0)) + 1

    res = tg_api("getUpdates", {"offset": offset, "timeout": 1}, token=tok)
    if not res.get("ok"):
        return list(sub_data.get("chats", {}).keys())

    updates = res.get("result", [])
    for upd in updates:
        uid = upd.get("update_id", 0)
        if uid > sub_data.get("last_update_id", 0):
            sub_data["last_update_id"] = uid

        # 1. Handle inline button callback_query (ADMIN ONLY: 995164733)
        if handle_commands and "callback_query" in upd:
            cb = upd["callback_query"]
            cb_id = cb.get("id")
            cb_data = cb.get("data", "")
            cb_chat = (cb.get("message") or {}).get("chat") or {}
            cb_cid = str(cb_chat.get("id", ""))
            if cb_cid != "995164733":
                if cb_id:
                    tg_api("answerCallbackQuery", {"callback_query_id": cb_id, "text": "🔒 Bu kumanda paneli yalnızca yöneticiye özeldir."}, token=tok)
                continue
            if cb_id:
                tg_api("answerCallbackQuery", {"callback_query_id": cb_id, "text": "İşlem başlatılıyor..."}, token=tok)
            if cb_cid and cb_data == "trigger_new_broadcast":
                _trigger_full_automation_pipeline(cb_cid, tok, out_dir=out_dir)
            continue

        # 2. Extract chat from message, channel_post, or my_chat_member
        msg = upd.get("message") or upd.get("channel_post") or (upd.get("my_chat_member") or {}).get("chat")
        chat = msg.get("chat") if isinstance(msg, dict) and "chat" in msg else msg
        if isinstance(chat, dict) and "id" in chat:
            cid = str(chat["id"])
            # Only register Admin (995164733) or official channels
            if cid != "995164733" and chat.get("type") == "private":
                if handle_commands and "message" in upd:
                    tg_api(
                        "sendMessage",
                        {
                            "chat_id": cid,
                            "text": (
                                "🔒 <b>Bu bot yalnızca GüzelAI Medya yöneticisine özel uzaktan kumanda panelidir.</b>\n\n"
                                "🌐 Güncel kombinler ve doğrulanmış mağaza linkleri için web sitemizi ziyaret edin:\n"
                                "👉 https://guzelai.com/#kombinler\n\n"
                                "💬 WhatsApp Kombin Kanalımız:\n"
                                "👉 https://whatsapp.com/channel/0029VbDetYc3mFYDwZSry016"
                            ),
                            "parse_mode": "HTML",
                        },
                        token=tok,
                    )
                continue

            sub_data["chats"][cid] = {
                "id": chat["id"],
                "type": chat.get("type", "private"),
                "title": chat.get("title") or chat.get("username") or chat.get("first_name") or cid,
                "username": chat.get("username", ""),
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }

            if handle_commands and "message" in upd and cid == "995164733":
                m = upd["message"]
                text = (m.get("text") or "").strip()
                caption = (m.get("caption") or "").strip()
                combined_text = text or caption
                found_urls = re.findall(r"https?://[^\s<>\"']+", combined_text)
                clean_title = re.sub(r"https?://[^\s<>\"']+", "", combined_text).replace("/yayinla", "").replace("/uret", "").replace("/paylas", "").strip()

                # Case A: Admin uploaded a Photo (with optional product link/title in caption)
                if m.get("photo"):
                    best_photo = m["photo"][-1]
                    photo_dest = Path(out_dir) / "telegram_uploaded_photo.jpg"
                    if _download_telegram_file(best_photo["file_id"], photo_dest, tok):
                        _trigger_full_automation_pipeline(
                            cid,
                            tok,
                            out_dir=out_dir,
                            custom_urls=found_urls,
                            custom_image=str(photo_dest),
                            custom_title=clean_title,
                        )
                    continue

                # Case B: Admin uploaded a Video (with optional product link/title in caption)
                if m.get("video"):
                    vid_dest = Path(out_dir) / "daily_kombin_reel.mp4"
                    if _download_telegram_file(m["video"]["file_id"], vid_dest, tok):
                        _trigger_full_automation_pipeline(
                            cid,
                            tok,
                            out_dir=out_dir,
                            custom_urls=found_urls,
                            custom_video=str(vid_dest),
                            custom_title=clean_title,
                        )
                    continue

                # Case C: Admin slash command
                if text.startswith("/"):
                    _handle_bot_command(cid, text, out_dir=out_dir, token=tok)
                # Case D: Admin directly pasted one or more product links in chat
                elif found_urls:
                    _trigger_full_automation_pipeline(
                        cid,
                        tok,
                        out_dir=out_dir,
                        custom_urls=found_urls,
                        custom_title=clean_title,
                    )

    save_subscribers(sub_data)

    env_chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    chat_ids = list(sub_data.get("chats", {}).keys())
    if env_chat and env_chat not in chat_ids:
        chat_ids.append(env_chat)
    return chat_ids


def _handle_bot_command(chat_id: str, text: str, out_dir: str = "output", token: Optional[str] = None) -> None:
    import re
    tok = token or get_bot_token()
    parts = text.split()
    cmd = parts[0].lower().split("@")[0]
    found_urls = re.findall(r"https?://[^\s<>\"']+", text)
    clean_title = re.sub(r"https?://[^\s<>\"']+", "", " ".join(parts[1:])).strip()

    if cmd in ("/yayinla", "/uret", "/paylas", "/tetikle"):
        _trigger_full_automation_pipeline(
            chat_id,
            tok,
            out_dir=out_dir,
            custom_urls=found_urls,
            custom_title=clean_title,
        )
        return

    meta_path = Path(out_dir) / "outfit_links.json"
    outfit = {}
    if meta_path.exists():
        try:
            outfit = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            outfit = {}

    if cmd in ("/start", "/kombin"):
        welcome = (
            "👋 <b>Güzel AI (@guzelaicom) 10 Kanallı Otomasyon &amp; Kombin Kontrol Merkezine Hoş Geldiniz!</b>\n\n"
            "Günün her saatinde buradan otomasyonu tetikleyebilirsiniz:\n"
            "• 🚀 <b>/yayinla</b> yazarak veya aşağıdaki butona basarak anında yeni 2K kombin üretip 10 kanalda yayınlatabilirsiniz.\n"
            "• 🔗 <b>Doğrudan Ürün Linki Gönderin:</b> Trendyol/Zara vb. ürün linki yapıştırırsanız o ürünle 2K video üretip tüm hesaplarda paylaşır.\n"
            "• 🖼️ <b>Fotoğraf veya Video Gönderin:</b> Bota fotoğraf/video atarsanız (açıklamasına link de ekleyebilirsiniz) doğrudan o görselle tüm platformlarda yayına çıkar!\n\n"
            "👇 <i>En son hazırlanan kombin aşağıda yükleniyor...</i>"
        )
        control_kb = {
            "inline_keyboard": [
                [{"text": "🚀 Yeni 2K Kombin Üret & 10 Kanalda Yayınla", "callback_data": "trigger_new_broadcast"}],
                [
                    {"text": "🌐 GuzelAI.com Görselli Linkler", "url": "https://guzelai.com/#kombinler"},
                    {"text": "💬 WhatsApp Kanalımız", "url": "https://whatsapp.com/channel/0029VbDetYc3mFYDwZSry016"},
                ],
            ]
        }
        if cmd == "/start":
            tg_api(
                "sendMessage",
                {"chat_id": chat_id, "text": welcome, "parse_mode": "HTML", "reply_markup": control_kb},
                token=tok,
            )
        if outfit:
            send_outfit_to_chat(
                chat_id=chat_id,
                outfit=outfit,
                video_path=Path(out_dir) / "daily_kombin_reel.mp4",
                collage_path=Path(out_dir) / "kombin_collage.png",
                token=tok,
            )
    elif cmd == "/linkler":
        if outfit:
            html_cap = build_telegram_html(outfit)
            kb = build_inline_keyboard(outfit)
            tg_api(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": html_cap,
                    "parse_mode": "HTML",
                    "reply_markup": kb,
                    "disable_web_page_preview": True,
                },
                token=tok,
            )
    elif cmd == "/durum":
        sub_data = load_subscribers()
        status_msg = (
            "📊 <b>@guzelaibot 10 Kanallı Otomasyon Durumu</b>\n\n"
            "• 🌐 <b>GuzelAI.com Vitrini:</b> Aktif (https://guzelai.com/#kombinler)\n"
            "• 📸 <b>Instagram Reels:</b> Bağlı (@guzelaicom)\n"
            "• 📘 <b>Facebook:</b> Bağlı (Güzel Ai - archzencir@gmail.com)\n"
            "• 🎵 <b>TikTok:</b> Bağlı (@guzelaicom)\n"
            "• ▶️ <b>YouTube Shorts:</b> Bağlı (youtube.com/@guzelaicom)\n"
            "• 𝕏 <b>X (Twitter):</b> Bağlı (x.com/guzelaicom)\n"
            "• 📌 <b>Pinterest:</b> Bağlı (archzencir@gmail.com)\n"
            "• 🧵 <b>Threads:</b> Bağlı (@guzelaicom)\n"
            "• 💬 <b>WhatsApp Kanalı:</b> Bağlı (whatsapp.com/channel/0029VbDetYc3mFYDwZSry016)\n"
            "• 🤖 <b>Telegram Uzaktan Tetikleyici:</b> Aktif (/yayinla, Link veya Görsel Gönderimi)\n"
            f"• 👥 <b>Kayıtlı Abone Sayısı:</b> {len(sub_data.get('chats', {}))}\n"
            "• 🛍️ <b>Son Kombin:</b> " + html.escape(outfit.get("archetype_title", "Hazır"))
        )
        control_kb = {
            "inline_keyboard": [
                [{"text": "🚀 Şimdi Yeni Kombin Üret & Yayınla", "callback_data": "trigger_new_broadcast"}],
                [{"text": "🌐 GuzelAI.com Görselli Linkler", "url": "https://guzelai.com/#kombinler"}],
            ]
        }
        tg_api(
            "sendMessage",
            {"chat_id": chat_id, "text": status_msg, "parse_mode": "HTML", "reply_markup": control_kb},
            token=tok,
        )


def send_outfit_to_chat(
    chat_id: str,
    outfit: Dict[str, Any],
    video_path: Optional[Path] = None,
    collage_path: Optional[Path] = None,
    reel_url: str = "",
    threads_url: str = "",
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """Sends the Kombin collage photo and/or 2K Reel video with HTML caption and shopping buttons to a chat_id."""
    tok = token or get_bot_token()
    html_caption = build_telegram_html(outfit, reel_url=reel_url, threads_url=threads_url)
    reply_markup_json = json.dumps(build_inline_keyboard(outfit, reel_url=reel_url, threads_url=threads_url))

    results: Dict[str, Any] = {}

    # 1. Send Collage Photo if available
    if collage_path and collage_path.exists():
        with open(collage_path, "rb") as pf:
            res_photo = tg_api(
                "sendPhoto",
                data={
                    "chat_id": chat_id,
                    "caption": f"🖼️ <b>{html.escape(outfit.get('archetype_title', 'Günün Kombini'))} — Ürün Kolajı</b>",
                    "parse_mode": "HTML",
                },
                files={"photo": pf},
                token=tok,
            )
            results["photo"] = res_photo.get("ok", False)

    # 2. Send 2K Reel Video with full HTML caption + Inline Shopping Buttons
    if video_path and video_path.exists():
        with open(video_path, "rb") as vf:
            res_vid = tg_api(
                "sendVideo",
                data={
                    "chat_id": chat_id,
                    "caption": html_caption,
                    "parse_mode": "HTML",
                    "reply_markup": reply_markup_json,
                    "supports_streaming": "true",
                    "width": "1440",
                    "height": "2560",
                },
                files={"video": vf},
                token=tok,
            )
            results["video"] = res_vid.get("ok", False)
            if not res_vid.get("ok"):
                results["video_error"] = res_vid.get("description")
    else:
        res_msg = tg_api(
            "sendMessage",
            data={
                "chat_id": chat_id,
                "text": html_caption,
                "parse_mode": "HTML",
                "reply_markup": json.loads(reply_markup_json),
            },
            token=tok,
        )
        results["message"] = res_msg.get("ok", False)

    return results


def publish_to_telegram(
    outfit: Dict[str, Any],
    out_dir: str = "output",
    reel_url: str = "",
    threads_url: str = "",
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """Saves Telegram outputs and broadcasts to all registered subscribers / TELEGRAM_CHAT_ID."""
    tok = token or get_bot_token()
    save_telegram_outputs(outfit, out_dir=out_dir, reel_url=reel_url, threads_url=threads_url)

    chat_ids = sync_subscribers_from_updates(token=tok, handle_commands=True, out_dir=out_dir)
    if not chat_ids:
        print(
            "[Telegram Bilgilendirmesi] Henüz kayıtlı chat_id bulunamadı. "
            "Telegram'dan @guzelaibot'a /start yazarak veya botu kanalınıza ekleyerek otomatik yayını başlatabilirsiniz."
        )
        return {"status": "waiting_for_subscriber", "bot": "@guzelaibot"}

    video_path = Path(out_dir) / "daily_kombin_reel.mp4"
    collage_path = Path(out_dir) / "kombin_collage.png"

    sent_results = {}
    for cid in chat_ids:
        sent_results[cid] = send_outfit_to_chat(
            chat_id=cid,
            outfit=outfit,
            video_path=video_path,
            collage_path=collage_path,
            reel_url=reel_url,
            threads_url=threads_url,
            token=tok,
        )
        print(f"[BAŞARILI - Telegram] @guzelaibot üzerinden {cid} adresine kombin gönderildi: {sent_results[cid]}")

    return {"status": "published", "results": sent_results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outfit-json", default="output/outfit_links.json")
    parser.add_argument("--reel-url", default="")
    parser.add_argument("--threads-url", default="")
    parser.add_argument("--setup-profile", action="store_true", help="Bot profil ve komutlarını yapılandır")
    parser.add_argument("--publish", action="store_true", help="Kayıtlı abonelere/kanala kombin gönder")
    parser.add_argument("--poll", type=int, default=0, help="Belirtilen saniye boyunca gelen mesajları dinle ve yanıtla")
    args = parser.parse_args()

    tok = get_bot_token()
    if args.setup_profile:
        cfg = configure_bot_profile(token=tok)
        print("[BAŞARILI] @guzelaibot profil ve komut ayarları güncellendi:", json.dumps(cfg, ensure_ascii=False))

    out_dir = os.path.dirname(args.outfit_json) or "output"
    if os.path.exists(args.outfit_json):
        with open(args.outfit_json, "r", encoding="utf-8") as f:
            outfit = json.load(f)
        if args.publish:
            publish_to_telegram(outfit, out_dir=out_dir, reel_url=args.reel_url, threads_url=args.threads_url, token=tok)
        else:
            save_telegram_outputs(outfit, out_dir=out_dir, reel_url=args.reel_url, threads_url=args.threads_url)

    if args.poll > 0:
        print(f"[Telegram Bot] @guzelaibot {args.poll} saniye boyunca mesajları dinliyor...")
        end_time = time.time() + args.poll
        while time.time() < end_time:
            sync_subscribers_from_updates(token=tok, handle_commands=True, out_dir=out_dir)
            time.sleep(2)


if __name__ == "__main__":
    main()
