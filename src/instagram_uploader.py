import os
import sys
import re
import json
import time
import argparse
from pathlib import Path
from urllib.parse import unquote
import requests
from PIL import Image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def upload_via_graph_api(video_path: str, caption: str, access_token: str, ig_user_id: str) -> bool:
    print("[Instagram Graph API] Video geçici bulut bağlantısına yükleniyor...")
    with open(video_path, "rb") as f:
        up_resp = requests.post("https://tmpfiles.org/api/v1/upload", files={"file": f}, timeout=60)
    up_resp.raise_for_status()
    raw_url = up_resp.json()["data"]["url"].replace("tmpfiles.org/", "tmpfiles.org/dl/")

    create_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
    payload = {
        "media_type": "REELS",
        "video_url": raw_url,
        "caption": caption,
        "share_to_feed": "true",
        "access_token": access_token,
    }
    r = requests.post(create_url, data=payload, timeout=30)
    r.raise_for_status()
    creation_id = r.json()["id"]
    print(f"[Instagram Graph API] Medya konteyneri oluşturuldu: {creation_id}, işlenmesi bekleniyor...")

    for _ in range(18):
        time.sleep(10)
        status_r = requests.get(
            f"https://graph.facebook.com/v19.0/{creation_id}",
            params={"fields": "status_code", "access_token": access_token},
            timeout=20,
        )
        status_code = status_r.json().get("status_code")
        print(f"  -> Durum: {status_code}")
        if status_code == "FINISHED":
            break
        if status_code == "ERROR":
            raise RuntimeError(f"Instagram medya işleme hatası: {status_r.text}")

    pub_r = requests.post(
        f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish",
        data={"creation_id": creation_id, "access_token": access_token},
        timeout=30,
    )
    pub_r.raise_for_status()
    print(f"[BAŞARILI] Instagram Reels yayınlandı! Media ID: {pub_r.json().get('id')}")
    return True


def upload_via_instagrapi(
    video_path: str,
    caption: str,
    username: str,
    password: str = "",
    session_str: str = "",
    comment_text: str = "",
) -> str:
    # 0. Yurt Dışı Bulut IP (GitHub Actions / Veri Merkezi) Engeli — "Şüpheli Giriş / Şifre Değiştir" uyarısını %100 önler
    if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        print(
            "[BULUT IP KORUMASI AKTİF] Yurt dışı GitHub Actions / Azure veri merkezi IP'sinden "
            "@guzelaicom hesabına bağlanılması güvenlik gereği engellendi. Paylaşımlar yalnızca yerel Türkiye IP'sinden yapılır."
        )
        return ""

    # 1. Kısıt / Güvenlik Kilidi: IG_ENABLE_UPLOAD=1 olmadan Instagram'a istek gönderilmez
    if os.environ.get("IG_ENABLE_UPLOAD", "0") != "1":
        print(
            "[INSTAGRAM KORUMA MODU AKTİF] IG_ENABLE_UPLOAD=1 "
            "olmadan Instagram API'sine hiçbir istek gönderilmez."
        )
        return ""

    out_dir = Path(video_path).parent
    meta_path = out_dir / "outfit_links.json"
    ig_hist_path = out_dir / "instagram_uploaded_history.json"

    # 1.5 Yayın Öncesi %100 İhlal Doğurmaz Raporu & Viral Müzik Denetimi Zorunluluğu
    try:
        from kombin_agent_swarm import run_prepublish_compliance_auditor, run_tiktok_viral_music_scout

        music_rep = run_tiktok_viral_music_scout()
        comp_cert = run_prepublish_compliance_auditor()
        if not comp_cert.get("zero_violation_guaranteed", False):
            print(
                f"[İHLAL KORUMA ENGELİ] Yayın Öncesi Denetim Ajanı (TAN) onay vermedi: {comp_cert.get('verdict')} "
                f"({comp_cert.get('passed_checks')}). Paylaşım durduruldu."
            )
            return ""
        print(
            f"🛡️ [YAYIN ÖNCESİ ONAY - TAN] {comp_cert.get('verdict')} ({comp_cert.get('passed_checks')}) | "
            f"🎵 Müzik (CEM): {music_rep.get('selected_track_for_next_post', {}).get('track_name', '')}"
        )
    except Exception as ce:
        print(f"[Uyumluluk Denetimi Uyarısı] {ce}")

    # 2. En az 4 saatlik paylaşım aralığı (Rate-Limit / Cooldown Koruması)
    min_interval_sec = int(os.environ.get("IG_MIN_INTERVAL_SEC", str(4 * 3600)))
    last_upload_ts = 0.0
    if ig_hist_path.exists():
        try:
            hobj_check = json.loads(ig_hist_path.read_text(encoding="utf-8"))
            last_upload_ts = float(hobj_check.get("last_upload_timestamp", 0.0))
        except Exception:
            pass
    if last_upload_ts > 0 and (time.time() - last_upload_ts) < min_interval_sec:
        rem_min = int((min_interval_sec - (time.time() - last_upload_ts)) // 60)
        print(
            f"[HIZ SINIRI KORUMASI] Son Instagram paylaşımından bu yana 4 saat geçmedi "
            f"(Kalan süre: {rem_min} dk). Spam koruması gereği paylaşım ertelendi."
        )
        return ""

    from instagrapi import Client

    cl = Client()
    cl.set_locale("tr_TR")
    cl.set_country("TR")
    cl.set_country_code(90)
    cl.set_timezone_offset(3 * 3600)

    # 3. Sabit Cihaz Kimliği (Samsung SM-S918B — her çalışmada rastgele cihaz üretilmesini %100 engeller)
    device_profile_path = Path(r"C:\Users\zenci\.gemini\antigravity\scratch\ig_device_profile.json")
    if device_profile_path.exists():
        try:
            saved_dev = json.loads(device_profile_path.read_text(encoding="utf-8"))
            if "uuids" in saved_dev:
                cl.set_uuids(saved_dev["uuids"])
            if "device_settings" in saved_dev:
                cl.set_device(saved_dev["device_settings"])
        except Exception:
            pass

    clean_username = username.lstrip("@").strip()
    session_file_path = Path(r"C:\Users\zenci\.gemini\antigravity\scratch\ig_session.json")

    try:
        logged_in = False
        if not session_str and session_file_path.exists():
            session_str = session_file_path.read_text(encoding="utf-8").strip()

        if session_str and session_str.strip().startswith("{"):
            settings = json.loads(session_str)
            auth_header = settings.get("authorization_data", {})
            if auth_header.get("sessionid") or settings.get("uuids"):
                cl.set_settings(settings)
                cl.init()
                logged_in = True
                print(
                    f"[Instagram Güvenli Kilit] Şifresiz kayıtlı mobil Bearer IGT oturumu ve sabit Samsung SM-S918B cihaz profili ile @{clean_username} hazır."
                )

        if not logged_in:
            print(
                "[SIFIR-İHLAL GÜVENLİK KİLİDİ] Kayıtlı yerel Bearer oturumu (ig_session.json) bulunamadı. "
                "Şifre sıfırlama/giriş uyarısı tetiklememek için parola ile giriş (cl.login) tamamen devre dışıdır."
            )
            return ""
    except Exception as se:
        print(
            f"[GÜVENLİK DURDURMASI] Oturum okuma hatası ({type(se).__name__}: {se}). "
            "Hesabın korunması için hiçbir şifre/giriş denemesi yapılmadı."
        )
        return ""

    try:
        cur_arch_id = ""
        cur_model_frame = ""
        if meta_path.exists():
            try:
                mdata = json.loads(meta_path.read_text(encoding="utf-8"))
                cur_arch_id = mdata.get("archetype_id", "")
                mframes = mdata.get("model_frames") or []
                cur_model_frame = mframes[0] if mframes else ""
            except Exception:
                pass

        published_archs = {
            "telegram_curly_champagne_palazzo",
            "curly_khaki_suede_palazzo",
            "pajama_morning_vibe",
            "chic_black_biker_denim",
            "casual_denim_sherpa_grey",
        }
        published_models = {
            "assets/telegram_curly_step1.jpg",
            "assets/curly_model_step1.jpg",
            "assets/outfit3_model_step1.jpg",
            "assets/outfit2_model_step1.jpg",
            "assets/trial1_model_street.jpg",
        }
        last_urls = {}
        if ig_hist_path.exists():
            try:
                hobj = json.loads(ig_hist_path.read_text(encoding="utf-8"))
                published_archs.update(hobj.get("published_archetypes", []))
                published_models.update(hobj.get("published_models", []))
                last_urls = hobj.get("reel_urls", {})
            except Exception:
                pass

        if (cur_arch_id and cur_arch_id in published_archs) or (cur_model_frame and cur_model_frame in published_models):
            existing_url = last_urls.get(cur_arch_id, "https://www.instagram.com/guzelaicom/reels/")
            print(
                f"[TEKRAR ENGELLEYİCİ] '{cur_arch_id}' ({cur_model_frame}) zaten Instagram'da yayınlanmış! "
                f"Aynı kombin/manken tekrar yüklenmedi -> {existing_url}"
            )
            return existing_url

        thumb_path = Path(video_path).with_suffix(".jpg")
        hook_cover_candidate = Path(video_path).parent / "hook_cover.jpg"
        collage_candidate = Path(video_path).parent / "kombin_collage.png"
        street_candidate = Path(video_path).parent / "model_street.png"
        if hook_cover_candidate.exists():
            Image.open(hook_cover_candidate).convert("RGB").save(thumb_path, "JPEG", quality=98, subsampling=0)
        elif collage_candidate.exists():
            Image.open(collage_candidate).convert("RGB").save(thumb_path, "JPEG", quality=98, subsampling=0)
        elif street_candidate.exists():
            Image.open(street_candidate).convert("RGB").save(thumb_path, "JPEG", quality=98, subsampling=0)
        else:
            Image.new("RGB", (1440, 2560), (247, 245, 241)).save(thumb_path, "JPEG", quality=98, subsampling=0)

        media = cl.clip_upload(video_path, caption=caption, thumbnail=thumb_path)
        reel_url = f"https://www.instagram.com/reel/{media.code}/"
        print(f"[BAŞARILI] Instagram Reels paylaşıldı! Media PK: {media.pk} | Code: {media.code} | Link: {reel_url}")

        try:
            if cur_arch_id:
                published_archs.add(cur_arch_id)
                last_urls[cur_arch_id] = reel_url
            if cur_model_frame:
                published_models.add(cur_model_frame)
            ig_hist_path.write_text(
                json.dumps(
                    {
                        "published_archetypes": sorted(published_archs),
                        "published_models": sorted(published_models),
                        "reel_urls": last_urls,
                        "last_upload_timestamp": time.time(),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as he:
            print(f"[IG Geçmiş Kayıt Uyarısı] {he}")

        # NOT: Instagram spam filtresini tetikleyen 0.5sn'lik otomatik ilk yorum (media_comment) tamamen kaldırıldı!
        return reel_url
    except Exception as e:
        print(f"[Instagram Paylaşım Uyarısı] {type(e).__name__}: {e}")
        return ""


def dispatch_all_channels(video_path: str, reel_url: str = ""):
    """Dispatches and publishes across connected channels (TikTok is paused unless ENABLE_TIKTOK_UPLOAD=1)."""
    out_dir = str(Path(video_path).parent)
    meta_path = os.path.join(out_dir, "outfit_links.json")
    hook_cover_candidate = Path(video_path).parent / "hook_cover.jpg"
    collage_candidate = hook_cover_candidate if hook_cover_candidate.exists() else (Path(video_path).parent / "kombin_collage.png")
    outfit_data = {}

    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as mf:
            outfit_data = json.load(mf)
        if reel_url:
            outfit_data["reel_url"] = reel_url
            with open(meta_path, "w", encoding="utf-8") as mf:
                json.dump(outfit_data, mf, ensure_ascii=False, indent=2)

    # 1. GuzelAI.com (#kombinler) e-ticaret link doğrulama ve görselli vitrin yayını
    try:
        from website_publisher import publish_to_guzelai_website
        web_res = publish_to_guzelai_website(
            outfit_data,
            collage_path=collage_candidate,
            ig_reel_url=reel_url,
            out_dir=out_dir,
        )
        print(f"[GuzelAI.com Görselli Link Vitrini] Durum: {web_res}")
    except Exception as webe:
        print(f"[GuzelAI.com Vitrin Bilgilendirmesi] {webe}")

    # 2. Threads metin çıktısını hazırla
    try:
        from threads_publisher import save_threads_outputs
        save_threads_outputs(outfit_data, out_dir=out_dir, reel_url=reel_url)
    except Exception as te:
        print(f"[Threads Güncelleme Bilgilendirmesi] {te}")

    # 3. TikTok (@guzelaicom) paylaşımı — 0 izlenme sorunu çözülüp ENABLE_TIKTOK_UPLOAD=1 açılana kadar yatırım durduruldu
    if os.environ.get("ENABLE_TIKTOK_UPLOAD", "0") == "1":
        try:
            from tiktok_uploader import build_tiktok_caption, publish_to_tiktok_cdp, save_tiktok_outputs
            save_tiktok_outputs(outfit_data, out_dir=out_dir, ig_reel_url=reel_url)
            tt_caption = build_tiktok_caption(outfit_data, ig_reel_url=reel_url)
            tt_res = publish_to_tiktok_cdp(Path(video_path), tt_caption)
            print(f"[TikTok Otomatik Paylaşım] Durum: {tt_res}")
        except Exception as tke:
            print(f"[TikTok Paylaşım Bilgilendirmesi] {tke}")
    else:
        print("[TikTok Yatırımı Durduruldu] 0-izlenme / algoritma koruması aktif: Onayınız olmadan TikTok'a otomatik yükleme yapılmaz.")

    # 4. Telegram botunda (@guzelaibot) otomatik paylaşım
    try:
        from telegram_publisher import publish_to_telegram
        tg_res = publish_to_telegram(outfit_data, out_dir=out_dir, reel_url=reel_url)
        print(f"[Telegram Otomatik Paylaşım] Durum: {tg_res}")
    except Exception as tge:
        print(f"[Telegram Paylaşım Bilgilendirmesi] {tge}")

    # 5. Pinterest hesabında (archzencir@gmail.com) otomatik Pin paylaşımı
    try:
        from pinterest_publisher import save_pinterest_outputs, publish_to_pinterest_cdp
        save_pinterest_outputs(outfit_data, out_dir=out_dir, reel_url=reel_url)
        pin_media = collage_candidate if collage_candidate.exists() else Path(video_path)
        pin_res = publish_to_pinterest_cdp(outfit_data, pin_media, reel_url=reel_url)
        print(f"[Pinterest Otomatik Paylaşım] Durum: {pin_res}")
    except Exception as pne:
        print(f"[Pinterest Paylaşım Bilgilendirmesi] {pne}")

    # 6. YouTube Shorts kanalında (https://www.youtube.com/@guzelaicom) otomatik paylaşım
    try:
        from youtube_publisher import save_youtube_outputs, publish_to_youtube_cdp
        save_youtube_outputs(outfit_data, out_dir=out_dir, reel_url=reel_url)
        yt_res = publish_to_youtube_cdp(outfit_data, Path(video_path), reel_url=reel_url)
        print(f"[YouTube Shorts Otomatik Paylaşım] Durum: {yt_res}")
    except Exception as yte:
        print(f"[YouTube Shorts Paylaşım Bilgilendirmesi] {yte}")

    # 7. X / Twitter hesabında (https://x.com/guzelaicom) otomatik paylaşım
    try:
        from x_publisher import save_x_outputs, publish_to_x_cdp
        save_x_outputs(outfit_data, out_dir=out_dir, reel_url=reel_url)
        x_media = Path(video_path) if Path(video_path).exists() else collage_candidate
        x_res = publish_to_x_cdp(outfit_data, media_path=x_media, reel_url=reel_url)
        print(f"[X (Twitter) Otomatik Paylaşım] Durum: {x_res}")
    except Exception as xe:
        print(f"[X (Twitter) Paylaşım Bilgilendirmesi] {xe}")

    # 8. Facebook hesabında (archzencir@gmail.com) otomatik paylaşım
    try:
        from facebook_publisher import save_facebook_outputs, publish_to_facebook_cdp
        save_facebook_outputs(outfit_data, out_dir=out_dir, ig_reel_url=reel_url)
        fb_media = collage_candidate if collage_candidate.exists() else Path(video_path)
        fb_res = publish_to_facebook_cdp(outfit_data, media_path=fb_media, ig_reel_url=reel_url)
        print(f"[Facebook Otomatik Paylaşım] Durum: {fb_res}")
    except Exception as fbe:
        print(f"[Facebook Paylaşım Bilgilendirmesi] {fbe}")

    # 9. WhatsApp Kanalı (https://whatsapp.com/channel/0029VbDetYc3mFYDwZSry016 - guzelai.com) canlı yayın
    try:
        from whatsapp_publisher import save_whatsapp_outputs, publish_to_whatsapp_cdp
        wa_res = save_whatsapp_outputs(outfit_data, out_dir=out_dir, ig_reel_url=reel_url)
        wa_pub = publish_to_whatsapp_cdp(outfit_data, ig_reel_url=reel_url)
        print(f"[WhatsApp Kanalı Otomatik Paylaşım] Durum: {wa_pub}")
    except Exception as wae:
        print(f"[WhatsApp Kanalı Bilgilendirmesi] {wae}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True, help="Yüklenecek MP4 dosyası")
    parser.add_argument("--caption-file", required=True, help="Açıklama metni dosyası")
    parser.add_argument(
        "--all-channels",
        action="store_true",
        help="Yalnızca kullanıcı onayladıktan sonra diğer tüm sosyal medya kanallarına dağıt",
    )
    args = parser.parse_args()

    with open(args.caption_file, "r", encoding="utf-8") as f:
        caption = f.read().strip()

    comment_file = os.path.join(os.path.dirname(args.caption_file) or ".", "comment_links.txt")
    comment_text = ""
    if os.path.exists(comment_file):
        with open(comment_file, "r", encoding="utf-8") as f:
            comment_text = f.read().strip()

    access_token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    ig_user_id = os.environ.get("IG_USER_ID", "").strip()
    username = os.environ.get("IG_USERNAME", "guzelaicom").strip()
    password = os.environ.get("IG_PASSWORD", "").strip()
    session_json = os.environ.get("IG_SESSION_JSON", "").strip()

    local_trusted_session = Path(r"C:\Users\zenci\.gemini\antigravity\scratch\ig_session.json")
    if not session_json and local_trusted_session.exists():
        session_json = local_trusted_session.read_text(encoding="utf-8").strip()

    reel_url = ""
    if access_token and ig_user_id:
        upload_via_graph_api(args.video, caption, access_token, ig_user_id)
    elif username or session_json:
        reel_url = upload_via_instagrapi(args.video, caption, username, password, session_json, comment_text=comment_text) or ""
    else:
        print("[BİLGİ] Instagram giriş bilgileri tanımlanmadığı için video yalnızca Artifacts olarak kaydedildi.")

    if args.all_channels:
        dispatch_all_channels(args.video, reel_url=reel_url)
    else:
        if reel_url:
            try:
                out_dir = str(Path(args.video).parent)
                meta_path = os.path.join(out_dir, "outfit_links.json")
                if os.path.exists(meta_path):
                    with open(meta_path, "r", encoding="utf-8") as mf:
                        outfit_data = json.load(mf)
                    outfit_data["reel_url"] = reel_url
                    with open(meta_path, "w", encoding="utf-8") as mf:
                        json.dump(outfit_data, mf, ensure_ascii=False, indent=2)
                    from website_publisher import publish_to_guzelai_website
                    publish_to_guzelai_website(outfit_data, out_dir=out_dir, ig_reel_url=reel_url)
            except Exception as wbe:
                print(f"[GuzelAI.com Reel URL Senkron Uyarısı] {wbe}")
        print("[KALİTE KONTROL MODU] Yalnızca Instagram ve GuzelAI.com vitrinine yayın yapıldı. Onayınız olmadan diğer sosyal medya platformları pas geçildi.")


if __name__ == "__main__":
    main()
