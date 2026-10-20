"""
Google Drive 7/24 Tam Otomasyon ve Bulut Senkronizasyon Modülü (mehmetzenciir@gmail.com)
----------------------------------------------------------------------------------------
Tüm kombin verilerini, 12 ajan kodlarını, JSON geçmiş veritabanlarını, AI manken görsellerini
ve yayınlanan 2K Reels videolarını doğrudan Google Drive (GuzelAI_Tam_Otomasyon_Bulut)
klasörüne senkronize eder. Hem GitHub Actions bulut sunucusunda hem de yerel ortamda
Antigravity ve laptoptan %100 bağımsız çalışır.
"""
import argparse
import base64
import datetime
import io
import json
import mimetypes
import os
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
BRIDGE_CONFIG_PATH = OUTPUT_DIR / "google_drive_bridge.json"


def get_bridge_url() -> str:
    env_url = os.environ.get("GDRIVE_BRIDGE_URL", "").strip()
    if env_url:
        return env_url
    if BRIDGE_CONFIG_PATH.exists():
        try:
            cfg = json.loads(BRIDGE_CONFIG_PATH.read_text(encoding="utf-8"))
            return str(cfg.get("web_app_url", "")).strip()
        except Exception:
            pass
    return ""


def upload_bytes_to_drive(
    bridge_url: str,
    subfolder: str,
    filename: str,
    raw_bytes: bytes,
    mime_type: str = "application/octet-stream",
) -> Dict[str, Any]:
    payload = {
        "action": "upload_file",
        "subfolder": subfolder,
        "filename": filename,
        "mimeType": mime_type,
        "base64Data": base64.b64encode(raw_bytes).decode("ascii"),
    }
    resp = requests.post(bridge_url, json=payload, timeout=90)
    resp.raise_for_status()
    return resp.json()


def upload_file_to_drive(bridge_url: str, subfolder: str, file_path: Path, custom_name: str = "") -> Dict[str, Any]:
    if not file_path.exists():
        return {"ok": False, "error": f"File not found: {file_path}"}
    fname = custom_name or file_path.name
    mime_type, _ = mimetypes.guess_type(fname)
    if not mime_type:
        if fname.endswith(".json"):
            mime_type = "application/json"
        elif fname.endswith(".py") or fname.endswith(".yml") or fname.endswith(".md") or fname.endswith(".txt"):
            mime_type = "text/plain"
        elif fname.endswith(".mp4"):
            mime_type = "video/mp4"
        elif fname.endswith(".jpg") or fname.endswith(".jpeg"):
            mime_type = "image/jpeg"
        elif fname.endswith(".png"):
            mime_type = "image/png"
        else:
            mime_type = "application/octet-stream"

    raw = file_path.read_bytes()
    res = upload_bytes_to_drive(bridge_url, subfolder, fname, raw, mime_type)
    print(f"  ☁️ [Google Drive -> {subfolder}] {fname} ({len(raw):,} byte) yüklendi.")
    return res


def build_system_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in [".github/workflows/daily_reels.yml", "requirements.txt"]:
            p = BASE_DIR / rel
            if p.exists():
                zf.write(p, rel)
        for p in sorted((BASE_DIR / "src").glob("*.py")):
            zf.write(p, f"src/{p.name}")
        for p in sorted(OUTPUT_DIR.glob("*.json")):
            zf.write(p, f"output/{p.name}")
        for p in sorted(OUTPUT_DIR.glob("*.md")):
            zf.write(p, f"output/{p.name}")
    return buf.getvalue()


def run_sync(mode: str = "cloud-post-run") -> Dict[str, Any]:
    bridge_url = get_bridge_url()
    if not bridge_url:
        print("[Google Drive Sync] GDRIVE_BRIDGE_URL tanımlı değil, senkronizasyon atlandı.")
        return {"ok": False, "reason": "no_bridge_url"}

    uploaded_items: List[Dict[str, Any]] = []
    ts_str = datetime.datetime.now().strftime("%Y%m%d_%H%M")

    # 1. Her çalışmada kritik JSON geçmiş ve durum dosyalarını 02_Veritabani_ve_Gecmis_JSON klasörüne yedekle
    json_files = [
        "instagram_uploaded_history.json",
        "published_outfits_history.json",
        "last_used_music_profiles.json",
        "social_health_report.json",
        "outfit_links.json",
        "prepublish_compliance_certificate.json",
        "viral_music_selection_report.json",
        "algorithm_reach_diagnosis_report.json",
        "concept_architect_briefs.json",
        "agent_curated_outfits.json",
        "pinterest_trends_queue.json",
        "store_verified_matches.json",
    ]
    for jf in json_files:
        p = OUTPUT_DIR / jf
        if p.exists():
            try:
                r = upload_file_to_drive(bridge_url, "02_Veritabani_ve_Gecmis_JSON", p)
                uploaded_items.append({"file": jf, "subfolder": "02_Veritabani_ve_Gecmis_JSON", "result": r})
            except Exception as e:
                print(f"  [Uyarı] {jf} yüklenemedi: {e}")

    # 2. Raporları ve Tam Sistem ZIP Yedeğini 05_Ajan_Denetim_Raporlari_ve_Tam_Yedek klasörüne yedekle
    for mf in ["latest_agent_briefing.md", "concept_architect_report.md", "prepublish_compliance_certificate.md"]:
        p = OUTPUT_DIR / mf
        if p.exists():
            try:
                upload_file_to_drive(bridge_url, "05_Ajan_Denetim_Raporlari_ve_Tam_Yedek", p)
            except Exception:
                pass

    try:
        zip_bytes = build_system_zip_bytes()
        upload_bytes_to_drive(
            bridge_url,
            "05_Ajan_Denetim_Raporlari_ve_Tam_Yedek",
            "GuzelAI_Tam_Sistem_Kod_ve_Veri_Yedegi.zip",
            zip_bytes,
            "application/zip",
        )
        print(f"  ☁️ [Google Drive] GuzelAI_Tam_Sistem_Kod_ve_Veri_Yedegi.zip ({len(zip_bytes):,} byte) yüklendi.")
    except Exception as e:
        print(f"  [Uyarı] ZIP yedeği yüklenemedi: {e}")

    # 3. Son üretilen 2K Reels videosu ve kapağını 04_Yayinlanan_2K_Reels_Arsivi klasörüne yedekle
    for media_name, custom_archive in [
        ("reel_final.mp4", f"reel_{ts_str}.mp4"),
        ("hook_cover.jpg", f"hook_cover_{ts_str}.jpg"),
        ("caption.txt", f"caption_{ts_str}.txt"),
    ]:
        mp = OUTPUT_DIR / media_name
        if mp.exists() and mp.stat().st_size < 25 * 1024 * 1024:
            try:
                upload_file_to_drive(bridge_url, "04_Yayinlanan_2K_Reels_Arsivi", mp, media_name)
                if mode == "cloud-post-run" and media_name == "reel_final.mp4":
                    upload_file_to_drive(bridge_url, "04_Yayinlanan_2K_Reels_Arsivi", mp, custom_archive)
            except Exception as e:
                print(f"  [Uyarı] {media_name} yüklenemedi: {e}")

    # 4. Tam Taşıma (full) modunda kaynak kodları ve AI manken görsellerini de yükle
    if mode == "full":
        for py_file in sorted((BASE_DIR / "src").glob("*.py")):
            try:
                upload_file_to_drive(bridge_url, "01_Kaynak_Kodlar_ve_12_Ajan", py_file)
            except Exception:
                pass
        wf_path = BASE_DIR / ".github" / "workflows" / "daily_reels.yml"
        if wf_path.exists():
            try:
                upload_file_to_drive(bridge_url, "01_Kaynak_Kodlar_ve_12_Ajan", wf_path)
            except Exception:
                pass

        for model_img in [
            "hw_couple1_step1.jpg",
            "hw_couple1_step2.jpg",
            "hw_couple1_step3.jpg",
            "hw_couple2_step1.jpg",
            "hw_couple2_step2.jpg",
            "hw_couple2_step3.jpg",
            "hw27_women_step1.jpg",
            "hw27_men_step1.jpg",
            "men1_model_step1.jpg",
            "men2_model_step1.jpg",
            "kid1_model_step1.jpg",
            "sun1_model_step1.jpg",
            "mon1_model_step1.jpg",
            "mon2_model_step1.jpg",
        ]:
            img_p = BASE_DIR / "assets" / model_img
            if img_p.exists():
                try:
                    upload_file_to_drive(bridge_url, "03_AI_Manken_ve_Kombin_Gorselleri", img_p)
                except Exception:
                    pass

    return {"ok": True, "uploaded_count": len(uploaded_items)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="cloud-post-run", choices=["full", "cloud-post-run"])
    args = parser.parse_args()
    run_sync(args.mode)
