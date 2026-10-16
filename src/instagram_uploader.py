import os
import json
import time
import argparse
import requests


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
            timeout=20
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
        timeout=30
    )
    pub_r.raise_for_status()
    print(f"[BAŞARILI] Instagram Reels yayınlandı! Media ID: {pub_r.json().get('id')}")
    return True


def upload_via_instagrapi(video_path: str, caption: str, username: str, password: str, session_json: str = "") -> bool:
    from instagrapi import Client

    cl = Client()
    cl.set_locale("tr_TR")
    cl.set_timezone_offset(3 * 3600)  # Türkiye Saati (UTC+3)
    clean_username = username.lstrip("@").strip()

    try:
        if session_json:
            settings = json.loads(session_json)
            cl.set_settings(settings)
        cl.login(clean_username, password)
        print(f"[instagrapi] @{clean_username} hesabına başarıyla giriş yapıldı.")
        media = cl.clip_upload(video_path, caption=caption)
        print(f"[BAŞARILI] Instagram Reels paylaşıldı! Media PK: {media.pk}")
        return True
    except Exception as e:
        print(f"[Instagram Giriş/Paylaşım Uyarısı] {e}")
        print(
            "Not: Instagram yeni bir sunucu IP'sinden (GitHub Actions) ilk kez giriş yapıldığında "
            "uygulama içinden 'Bu bendim (It was me)' onayı isteyebilir. "
            "Üretilen MP4 videosu GitHub Actions Artifacts sekmesine başarıyla kaydedilmiştir."
        )
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True, help="Yüklenecek MP4 dosyası")
    parser.add_argument("--caption-file", required=True, help="Açıklama metni dosyası")
    args = parser.parse_args()

    with open(args.caption_file, "r", encoding="utf-8") as f:
        caption = f.read().strip()

    access_token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    ig_user_id = os.environ.get("IG_USER_ID", "").strip()
    username = os.environ.get("IG_USERNAME", "").strip()
    password = os.environ.get("IG_PASSWORD", "").strip()
    session_json = os.environ.get("IG_SESSION_JSON", "").strip()

    if access_token and ig_user_id:
        upload_via_graph_api(args.video, caption, access_token, ig_user_id)
    elif username and password:
        upload_via_instagrapi(args.video, caption, username, password, session_json)
    else:
        print("[BİLGİ] Instagram giriş bilgileri tanımlanmadığı için video yalnızca Artifacts olarak kaydedildi.")


if __name__ == "__main__":
    main()
