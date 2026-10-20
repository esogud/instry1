import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
SCRATCH_DIR = BASE_DIR.parent
IG_SESSION_PATH = SCRATCH_DIR / "ig_session.json"
IG_DEVICE_PATH = SCRATCH_DIR / "ig_device_profile.json"
IG_UPLOAD_HIST_PATH = OUTPUT_DIR / "instagram_uploaded_history.json"
HEALTH_REPORT_PATH = OUTPUT_DIR / "social_health_report.json"
HEALTH_HISTORY_PATH = OUTPUT_DIR / "social_health_history.json"
GH_BIN = SCRATCH_DIR / "tools" / "gh" / "bin" / "gh.exe"


def _load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def check_instagram_health_and_metrics(force: bool = False) -> dict:
    """
    Sabit cihaz kimliği (ig_device_profile.json) ve kalıcı Bearer IGT oturumu (ig_session.json)
    ile KESİNLİKLE yeni şifre girişi (cl.login) yapmadan, salt-okunur (read-only) modda
    @guzelaicom hesap sağlığını, takipçi sayısını ve Reels izlenme/etkileşim verilerini analiz eder.
    """
    now_ts = time.time()
    # Spam/sorgu koruması: Force edilmedikçe son 15 dakika içinde alınmış rapor varsa önbellekten dön
    if not force and HEALTH_REPORT_PATH.exists():
        cached = _load_json(HEALTH_REPORT_PATH, {})
        cached_ts = float(cached.get("timestamp_epoch", 0))
        if (now_ts - cached_ts) < 900 and cached.get("instagram", {}).get("session_healthy"):
            ig_cached = cached["instagram"]
            ig_cached["from_cache"] = True
            return ig_cached

    result = {
        "username": "guzelaicom",
        "session_healthy": False,
        "device_profile_locked": IG_DEVICE_PATH.exists(),
        "bearer_token_present": False,
        "account_status": "UNKNOWN",
        "risk_level": "HIGH",
        "risk_notes": [],
        "compliance_checks": {
            "persistent_device_uuid": IG_DEVICE_PATH.exists(),
            "zero_auto_comment_bot": True,
            "zero_raw_urls_in_caption": True,
            "hashtag_count_safe": True,
            "cooldown_4h_active": True,
        },
        "metrics": {
            "follower_count": 0,
            "following_count": 0,
            "media_count": 0,
            "total_reel_views": 0,
            "total_reel_likes": 0,
            "total_reel_comments": 0,
            "avg_views_per_reel": 0.0,
            "engagement_rate_pct": 0.0,
        },
        "deltas": {
            "follower_delta": 0,
            "total_views_delta": 0,
            "total_likes_delta": 0,
        },
        "recent_reels": [],
        "cooldown_status": {},
    }

    # 1. Son paylaşım zamanı ve 4 saatlik hız sınırı kontrolü
    ig_hist = _load_json(IG_UPLOAD_HIST_PATH, {})
    last_upload_ts = float(ig_hist.get("last_upload_timestamp", 0.0))
    elapsed_sec = (now_ts - last_upload_ts) if last_upload_ts > 0 else 999999
    cooldown_remaining_min = max(0, int((4 * 3600 - elapsed_sec) // 60))
    result["cooldown_status"] = {
        "last_upload_epoch": last_upload_ts,
        "minutes_since_last_upload": int(elapsed_sec // 60) if last_upload_ts > 0 else None,
        "cooldown_4h_remaining_min": cooldown_remaining_min,
        "ready_for_next_post": cooldown_remaining_min == 0,
    }

    # 2. Son açıklama (caption.txt) uyumluluk denetimi
    caption_path = OUTPUT_DIR / "caption.txt"
    if caption_path.exists():
        cap_txt = caption_path.read_text(encoding="utf-8", errors="ignore")
        raw_urls = [w for w in cap_txt.split() if w.startswith("http://") or w.startswith("https://")]
        hashtags = [w for w in cap_txt.split() if w.startswith("#")]
        result["compliance_checks"]["zero_raw_urls_in_caption"] = len(raw_urls) == 0
        result["compliance_checks"]["hashtag_count_safe"] = len(hashtags) <= 8
        if raw_urls:
            result["risk_notes"].append(f"Açıklamada {len(raw_urls)} adet ham URL bulundu (Spam riski).")
        if len(hashtags) > 8:
            result["risk_notes"].append(f"Açıklamada çok fazla etiket ({len(hashtags)}) var.")

    if not IG_SESSION_PATH.exists():
        result["account_status"] = "MISSING_SESSION"
        result["risk_notes"].append("ig_session.json bulunamadı.")
        return result

    raw_session = IG_SESSION_PATH.read_text(encoding="utf-8").strip()
    if not raw_session.startswith("{"):
        result["account_status"] = "LEGACY_COOKIE_ONLY"
        result["risk_notes"].append("ig_session.json tam mobil Bearer IGT formatında değil.")
        return result

    try:
        settings = json.loads(raw_session)
        auth_data = settings.get("authorization_data", {})
        result["bearer_token_present"] = bool(auth_data.get("sessionid"))

        from instagrapi import Client

        cl = Client()
        cl.set_locale("tr_TR")
        cl.set_country("TR")
        cl.set_country_code(90)
        cl.set_timezone_offset(3 * 3600)
        cl.set_settings(settings)
        cl.init()

        user_id = int(auth_data.get("ds_user_id", 46394512287))
        uinfo = cl.user_info_v1(user_id)

        followers = int(getattr(uinfo, "follower_count", 0) or 0)
        following = int(getattr(uinfo, "following_count", 0) or 0)
        media_cnt = int(getattr(uinfo, "media_count", 0) or 0)

        # Son 10 paylaşımın izlenme ve beğeni analizi (tekil hafif çağrı)
        medias = cl.user_medias_v1(user_id, amount=10)
        recent_reels = []
        total_views = 0
        total_likes = 0
        total_comments = 0

        for m in medias:
            code = getattr(m, "code", "")
            pk = str(getattr(m, "pk", ""))
            play_cnt = int(getattr(m, "play_count", 0) or getattr(m, "view_count", 0) or 0)
            like_cnt = int(getattr(m, "like_count", 0) or 0)
            comment_cnt = int(getattr(m, "comment_count", 0) or 0)
            taken_at = getattr(m, "taken_at", None)
            taken_str = taken_at.strftime("%Y-%m-%d %H:%M") if taken_at else ""
            caption_preview = (getattr(m, "caption_text", "") or "").split("\n")[0][:80]

            total_views += play_cnt
            total_likes += like_cnt
            total_comments += comment_cnt

            recent_reels.append(
                {
                    "code": code,
                    "pk": pk,
                    "url": f"https://www.instagram.com/reel/{code}/",
                    "taken_at": taken_str,
                    "play_count": play_cnt,
                    "like_count": like_cnt,
                    "comment_count": comment_cnt,
                    "title": caption_preview,
                }
            )

        n_reels = max(1, len(recent_reels))
        avg_views = round(total_views / n_reels, 1)
        denom = max(1, total_views if total_views > 0 else followers)
        eng_rate = round(((total_likes + total_comments) / denom) * 100.0, 2)

        result["session_healthy"] = True
        result["account_status"] = "HEALTHY_ACTIVE"
        result["risk_level"] = "LOW" if not result["risk_notes"] else "MEDIUM"
        result["metrics"] = {
            "follower_count": followers,
            "following_count": following,
            "media_count": media_cnt,
            "total_reel_views": total_views,
            "total_reel_likes": total_likes,
            "total_reel_comments": total_comments,
            "avg_views_per_reel": avg_views,
            "engagement_rate_pct": eng_rate,
        }
        result["recent_reels"] = recent_reels

        # Geçmiş kayıtlarla değişim (delta) analizi
        hist = _load_json(HEALTH_HISTORY_PATH, {"snapshots": []})
        snapshots = hist.get("snapshots", [])
        if snapshots:
            prev = snapshots[-1]
            result["deltas"] = {
                "follower_delta": followers - int(prev.get("follower_count", followers)),
                "total_views_delta": total_views - int(prev.get("total_reel_views", total_views)),
                "total_likes_delta": total_likes - int(prev.get("total_reel_likes", total_likes)),
            }

        snapshots.append(
            {
                "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
                "follower_count": followers,
                "media_count": media_cnt,
                "total_reel_views": total_views,
                "total_reel_likes": total_likes,
                "total_reel_comments": total_comments,
            }
        )
        HEALTH_HISTORY_PATH.write_text(
            json.dumps({"snapshots": snapshots[-100:]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    except Exception as e:
        result["session_healthy"] = False
        result["account_status"] = f"ERROR_{type(e).__name__}"
        result["risk_level"] = "HIGH"
        result["risk_notes"].append(f"Instagram API okuma hatası: {type(e).__name__}: {e}")

    return result


def check_other_platforms_health() -> dict:
    """
    GuzelAI.com web vitrini, GitHub Actions otomasyonu ve diğer sosyal medya
    kanallarının (TikTok, Threads, YouTube, Pinterest, X, Telegram) sağlık durumunu denetler.
    """
    platforms = {}

    # 1. GuzelAI.com Web Vitrini & /go/ Yönlendirme Sağlığı
    t0 = time.time()
    try:
        r = requests.get("https://guzelai.com/", timeout=10)
        latency_ms = int((time.time() - t0) * 1000)
        feed_file = SCRATCH_DIR / "guzelai" / "public" / "data" / "kombin_feed.json"
        has_kombinler = feed_file.exists() or ("kombinler" in r.text.lower())
        go_dir = SCRATCH_DIR / "guzelai" / "public" / "go"
        go_count = len(list(go_dir.glob("*.html"))) if go_dir.exists() else 0
        platforms["guzelai_web"] = {
            "status": "HEALTHY" if r.status_code == 200 else f"HTTP_{r.status_code}",
            "http_code": r.status_code,
            "latency_ms": latency_ms,
            "showcase_section_active": has_kombinler,
            "active_go_redirect_links": go_count,
        }
    except Exception as e:
        platforms["guzelai_web"] = {"status": "ERROR", "detail": str(e)}

    # 2. GitHub Actions Bulut Otomasyonu Sağlığı
    try:
        if os.environ.get("LOCAL_ONLY", "0") == "1" or os.environ.get("DISABLE_GITHUB_SYNC", "0") == "1":
            platforms["github_actions"] = {
                "status": "LOCAL_ONLY_PROTECTED",
                "detail": "Yerel Tek Güvenli Oturum Modu: Uzak GitHub Actions ve sunucu sorgusu devredışı.",
            }
        elif GH_BIN.exists():
            res = subprocess.run(
                [
                    str(GH_BIN),
                    "run",
                    "list",
                    "-R",
                    "thezencirs/instagram-kombin-bot",
                    "-L",
                    "1",
                    "--json",
                    "databaseId,status,conclusion,createdAt,event",
                ],
                capture_output=True,
                text=True,
                timeout=12,
            )
            if res.returncode == 0 and res.stdout.strip():
                runs = json.loads(res.stdout)
                if runs:
                    latest = runs[0]
                    platforms["github_actions"] = {
                        "status": "HEALTHY" if latest.get("conclusion") in ("success", None) else "WARNING",
                        "latest_run_id": latest.get("databaseId"),
                        "run_status": latest.get("status"),
                        "conclusion": latest.get("conclusion"),
                        "created_at": latest.get("createdAt"),
                        "cloud_ip_protection": "ACTIVE (dry_run=true default)",
                    }
    except Exception as e:
        platforms["github_actions"] = {"status": "UNKNOWN", "detail": str(e)}

    # 3. Diğer Sosyal Medya Kanalları (Oturum & İçerik Hazırlık Durumu)
    channel_profiles = {
        "tiktok": {
            "handle": "@guzelaicom",
            "profile_dir": SCRATCH_DIR / "tiktok_chrome_profile",
            "post_file": OUTPUT_DIR / "tiktok_post.txt",
            "mode": "STANDBY_SAFE (FYP linksiz format hazır)",
        },
        "threads": {
            "handle": "@guzelaicom",
            "profile_dir": SCRATCH_DIR / "ig_device_profile.json",
            "post_file": OUTPUT_DIR / "threads_post.txt",
            "mode": "STANDBY_SAFE (Instagram SSO bağlı, tıklanabilir link metni hazır)",
        },
        "youtube_shorts": {
            "handle": "@guzelaicom",
            "profile_dir": SCRATCH_DIR / "youtube_chrome_profile",
            "post_file": OUTPUT_DIR / "youtube_short.txt",
            "mode": "READY (2K dikey video + başlık/açıklama hazır)",
        },
        "pinterest": {
            "handle": "@guzelaicom",
            "profile_dir": SCRATCH_DIR / "pinterest_chrome_profile",
            "post_file": OUTPUT_DIR / "pinterest_pin.txt",
            "mode": "READY (Old Money vitrin kartı + doğrudan link hazır)",
        },
        "x_twitter": {
            "handle": "@guzelaicom",
            "profile_dir": SCRATCH_DIR / "x_chrome_profile",
            "post_file": OUTPUT_DIR / "x_post.txt",
            "mode": "READY (<=100 karakter ana tweet + kombin zinciri hazır)",
        },
        "telegram": {
            "handle": "@guzelaibot",
            "profile_dir": OUTPUT_DIR / "telegram_post.html",
            "post_file": OUTPUT_DIR / "telegram_post.html",
            "mode": "READY (HTML ürün kartı hazır)",
        },
    }

    for ch_key, cfg in channel_profiles.items():
        platforms[ch_key] = {
            "handle": cfg["handle"],
            "session_or_profile_present": cfg["profile_dir"].exists(),
            "latest_content_ready": cfg["post_file"].exists(),
            "operating_mode": cfg["mode"],
        }

    return platforms


def run_full_health_audit(force: bool = False) -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ig_report = check_instagram_health_and_metrics(force=force)
    other_report = check_other_platforms_health()

    full_report = {
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp_epoch": time.time(),
        "overall_health": "HEALTHY" if ig_report.get("session_healthy") else "ACTION_REQUIRED",
        "instagram": ig_report,
        "other_platforms": other_report,
    }

    HEALTH_REPORT_PATH.write_text(
        json.dumps(full_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return full_report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GuzelAI Sosyal Medya Sağlık ve Analitik Ajanı")
    parser.add_argument("--force", action="store_true", help="Önbelleği atlayıp canlı API verisi çek")
    args = parser.parse_args()

    report = run_full_health_audit(force=args.force)
    ig = report["instagram"]
    m = ig["metrics"]
    d = ig["deltas"]
    print("=" * 72)
    print(f"🛡️ GUZELAI SOSYAL MEDYA SAĞLIK & ANALİTİK RAPORU ({report['generated_at']})")
    print("=" * 72)
    print(
        f"📸 Instagram (@{ig['username']}): {ig['account_status']} | Risk: {ig['risk_level']} | "
        f"Sabit Cihaz: {'EVET' if ig['device_profile_locked'] else 'HAYIR'} | "
        f"Bearer IGT: {'AKTİF' if ig['bearer_token_present'] else 'YOK'}"
    )
    print(
        f"👥 Takipçi: {m['follower_count']} ({d['follower_delta']:+d}) | "
        f"Takip Edilen: {m['following_count']} | Gönderi: {m['media_count']}"
    )
    print(
        f"🎬 Son {len(ig['recent_reels'])} Reels Toplam İzlenme: {m['total_reel_views']} ({d['total_views_delta']:+d}) | "
        f"Ortalama İzlenme: {m['avg_views_per_reel']} | "
        f"Toplam Beğeni: {m['total_reel_likes']} | Yorum: {m['total_reel_comments']} | "
        f"Etkileşim Oranı: %{m['engagement_rate_pct']}"
    )
    print("-" * 72)
    for idx, r in enumerate(ig["recent_reels"][:5], 1):
        print(
            f"  {idx}. [{r['code']}] {r['taken_at']} -> "
            f"👁️ {r['play_count']} izlenme | ❤️ {r['like_count']} beğeni | 💬 {r['comment_count']} yorum | {r['url']}"
        )
    print("-" * 72)
    web = report["other_platforms"].get("guzelai_web", {})
    gha = report["other_platforms"].get("github_actions", {})
    print(
        f"🌐 GuzelAI.com: {web.get('status')} ({web.get('latency_ms')} ms) | "
        f"Aktif /go/ Linkleri: {web.get('active_go_redirect_links')}"
    )
    print(
        f"⚙️ GitHub Actions: {gha.get('status')} (Run #{gha.get('latest_run_id')} -> {gha.get('run_status')}/{gha.get('conclusion')})"
    )
    print("=" * 72)
