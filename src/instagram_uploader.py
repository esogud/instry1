import os
import re
import json
import time
import argparse
from pathlib import Path
from urllib.parse import unquote
import requests
from PIL import Image


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


def try_web_ajax_sessionid(cl, username: str, password: str) -> str:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "X-IG-App-ID": "936619743392459",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.instagram.com/accounts/login/",
        "Origin": "https://www.instagram.com",
    })
    r0 = s.get("https://www.instagram.com/accounts/login/", timeout=15)
    csrf_match = re.search(r'"csrf_token":"([^"]+)"', r0.text)
    csrf = s.cookies.get("csrftoken") or (csrf_match.group(1) if csrf_match else "")
    s.headers["X-CSRFToken"] = csrf

    enc = cl.password_encrypt(password)
    r = s.post(
        "https://www.instagram.com/api/v1/web/accounts/login/ajax/",
        data={
            "username": username,
            "enc_password": enc,
            "queryParams": "{}",
            "optIntoOneTap": "false",
        },
        timeout=15,
    )
    return s.cookies.get("sessionid", "")


def upload_via_instagrapi(
    video_path: str,
    caption: str,
    username: str,
    password: str,
    session_str: str = "",
    comment_text: str = "",
) -> bool:
    from instagrapi import Client

    cl = Client()
    cl.set_locale("tr_TR")
    cl.set_country("TR")
    cl.set_country_code(90)
    cl.set_timezone_offset(3 * 3600)

    clean_username = username.lstrip("@").strip()
    print(
        f"[instagrapi] Hazir: user=@{clean_username} | pass_len={len(password)} | "
        f"app={cl.device_settings.get('app_version')}"
    )

    logged_in = False

    if session_str:
        try:
            if session_str.startswith("{"):
                settings = json.loads(session_str)
                cl.set_settings(settings)
                sid = settings.get("cookies", {}).get("sessionid") or settings.get("authorization_data", {}).get("sessionid")
                if sid:
                    cl.login_by_sessionid(unquote(sid))
                else:
                    cl.login(clean_username, password)
            else:
                cl.login_by_sessionid(unquote(session_str.strip()))
            print(f"[instagrapi] Oturum anahtarı ile @{clean_username} hesabına giriş yapıldı!")
            logged_in = True
        except Exception as se:
            print(f"[instagrapi] Oturum anahtarı ile giriş başarısız ({type(se).__name__}: {se}), diğer yöntemler deneniyor...")

    if not logged_in and password:
        try:
            sid = try_web_ajax_sessionid(cl, clean_username, password)
            if sid:
                cl.login_by_sessionid(unquote(sid))
                print(f"[instagrapi] Web AJAX sessionid ile @{clean_username} hesabına giriş yapıldı!")
                logged_in = True
        except Exception as we:
            print(f"[Web AJAX Uyarısı] {type(we).__name__}: {we}")

    if not logged_in and password:
        try:
            cl.login(clean_username, password)
            print(f"[instagrapi] @{clean_username} hesabına mobil şifre ile giriş yapıldı!")
            logged_in = True
        except Exception as e:
            print(f"[Instagram Giriş Uyarısı] {type(e).__name__}: {e}")

    if not logged_in:
        return False

    try:
        thumb_path = Path(video_path).with_suffix(".jpg")
        collage_candidate = Path(video_path).parent / "kombin_collage.png"
        street_candidate = Path(video_path).parent / "model_street.png"
        if collage_candidate.exists():
            Image.open(collage_candidate).convert("RGB").save(thumb_path, "JPEG", quality=92)
        elif street_candidate.exists():
            Image.open(street_candidate).convert("RGB").save(thumb_path, "JPEG", quality=92)
        else:
            Image.new("RGB", (1080, 1920), (247, 245, 240)).save(thumb_path, "JPEG", quality=92)

        media = cl.clip_upload(video_path, caption=caption, thumbnail=thumb_path)
        reel_url = f"https://www.instagram.com/reel/{media.code}/"
        print(f"[BAŞARILI] Instagram Reels paylaşıldı! Media PK: {media.pk} | Code: {media.code} | Link: {reel_url}")

        # Ürün linklerini Reels'in ilk yorumuna da otomatik göm
        if comment_text:
            try:
                cl.media_comment(media.pk, comment_text)
                print("[BAŞARILI] Ürün linkleri Reels'in ilk yorumuna otomatik olarak eklendi!")
            except Exception as ce:
                print(f"[Yorum Bilgilendirmesi] İlk yorum eklenemedi ({ce}), linkler zaten açıklamada yer alıyor.")

        return True
    except Exception as e:
        print(f"[Instagram Paylaşım Uyarısı] {type(e).__name__}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True, help="Yüklenecek MP4 dosyası")
    parser.add_argument("--caption-file", required=True, help="Açıklama metni dosyası")
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
    username = os.environ.get("IG_USERNAME", "").strip()
    password = os.environ.get("IG_PASSWORD", "").strip()
    session_json = os.environ.get("IG_SESSION_JSON", "").strip()

    if access_token and ig_user_id:
        upload_via_graph_api(args.video, caption, access_token, ig_user_id)
    elif username or session_json:
        upload_via_instagrapi(args.video, caption, username, password, session_json, comment_text=comment_text)
    else:
        print("[BİLGİ] Instagram giriş bilgileri tanımlanmadığı için video yalnızca Artifacts olarak kaydedildi.")


if __name__ == "__main__":
    main()
