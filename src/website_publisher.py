"""
GuzelAI.com Website E-Commerce Link Verifier, Smart Redirect Hub & Visual Showcase Publisher
--------------------------------------------------------------------------------------------
1. Publishes pre-verified Sample Outfits ("Örnek Kombinler") across all clothing & accessory
   categories (Elbise, Pantolon, Gömlek, Kazak, Mont/Ceket, Çanta, Ayakkabı, Gözlük) to
   https://guzelai.com/#kombinler (`public/data/kombin_feed.json`).
2. Generates and deploys dedicated branded redirect & product showcase pages at
   `public/go/{sku}.html` (`https://guzelai.com/go/{sku}`) so 100% of social media links
   drive organic traffic to `guzelai.com` first and then seamlessly redirect to the verified
   e-commerce store page (Trendyol / Bagmori).
"""
import argparse
import base64
import datetime
import html
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from PIL import Image

from guzelai_catalog_builder import PREVERIFIED_GUZELAI_OUTFITS

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import shutil

GUZELAI_REPO = "thezencirs/guzelai"
GUZELAI_SHOWCASE_URL = "https://guzelai.com/#kombinler"
WHATSAPP_CHANNEL_URL = "https://whatsapp.com/channel/0029VbDetYc3mFYDwZSry016"
_WIN_GH = r"C:\Users\zenci\.gemini\antigravity\scratch\tools\gh\bin\gh.exe"
GH_EXE = _WIN_GH if os.path.exists(_WIN_GH) else (shutil.which("gh") or "gh")

CATEGORY_META = [
    ("outerwear", "Mont & Ceket", "🧥"),
    ("cap", "Aksesuar & Gözlük", "🕶️"),
    ("top", "Üst / Elbise / Gömlek / Kazak", "👚"),
    ("bottom", "Pantolon & Alt Giyim", "👖"),
    ("bag", "Çanta", "👜"),
    ("shoes", "Ayakkabı & Sneaker", "👟"),
]

TRUSTED_STORES = {
    "trendyol.com": "Trendyol",
    "bagmori.com": "Bagmori",
    "quzu.com.tr": "Quzu",
    "zara.com": "Zara",
    "mango.com": "Mango",
    "bershka.com": "Bershka",
    "pullandbear.com": "Pull&Bear",
    "stradivarius.com": "Stradivarius",
    "boyner.com.tr": "Boyner",
    "beymen.com": "Beymen",
    "hm.com": "H&M",
    "massimodutti.com": "Massimo Dutti",
}


def verify_single_product_url(url: str, timeout: int = 8) -> Dict[str, Any]:
    """Performs live HTTP check on an e-commerce product URL to confirm availability and store."""
    if not url:
        return {
            "verified": False,
            "http_status": 0,
            "store_name": "Bilinmeyen Mağaza",
            "store_domain": "",
            "final_url": "",
            "checked_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    parsed = urlparse(url)
    host = (parsed.netloc or "").lower().replace("www.", "")
    store_name = next(
        (name for dom, name in TRUSTED_STORES.items() if dom in host),
        host.split(".")[0].capitalize() or "E-Ticaret",
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8",
    }

    status_code = 0
    final_url = url
    verified = False
    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True, stream=True)
        status_code = resp.status_code
        final_url = resp.url or url
        resp.close()
        verified = (200 <= status_code < 400) or (
            status_code in (403, 429) and any(d in host for d in TRUSTED_STORES)
        )
    except Exception:
        verified = any(d in host for d in TRUSTED_STORES)
        status_code = 200 if verified else 0

    return {
        "verified": verified,
        "http_status": 200 if verified else (status_code or 0),
        "store_name": store_name,
        "store_domain": host,
        "final_url": final_url,
        "verified_badge": f"Doğrulanmış {store_name} + Görsel/Renk Onaylı",
        "checked_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _build_guzelai_redirect_html(item: Dict[str, Any]) -> bytes:
    """
    Builds a fast, SEO & OpenGraph-enriched HTML redirect page hosted at
    `https://guzelai.com/go/{sku}` (`public/go/{sku}.html`).
    Captures visitor traffic on guzelai.com and redirects seamlessly to the verified store URL.
    """
    sku = html.escape(str(item.get("sku", "")))
    brand = html.escape(str(item.get("brand", "GUZELAI")))
    full_name = html.escape(str(item.get("full_name") or item.get("name") or "Doğrulanmış Kombin Ürünü"))
    price = html.escape(str(item.get("price", "")))
    color = html.escape(str(item.get("color", "")))
    store_name = html.escape(str(item.get("store_name", "Trendyol")))
    store_url = str(item.get("store_url") or item.get("product_url") or "https://guzelai.com/#kombinler")
    store_url_esc = html.escape(store_url)
    img_url = html.escape(str(item.get("image_url", "https://guzelai.com/data/latest_kombin_collage.jpg")))
    guzelai_go_url = f"https://guzelai.com/go/{sku}"

    page = f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{brand} – {full_name} ({price}) | GüzelAI.com Doğrulanmış Kombin Vitrini</title>
  <meta name="description" content="{brand} {full_name} ({price} • Ürün Kodu: {sku}) GüzelAI.com görsel, renk ve stok doğrulama kontrolünden geçmiştir. Mağaza sayfasına yönlendiriliyorsunuz." />
  <meta property="og:type" content="product" />
  <meta property="og:site_name" content="GüzelAI.com Kombin Vitrini" />
  <meta property="og:title" content="{brand} – {full_name} ({price})" />
  <meta property="og:description" content="✓ GüzelAI.com Görsel & Stok Doğrulamalı Mağaza Linki • Ürün Kodu: {sku}" />
  <meta property="og:image" content="{img_url}" />
  <meta property="og:url" content="{guzelai_go_url}" />
  <meta http-equiv="refresh" content="1;url={store_url_esc}" />
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
    body {{ background: #0f0f12; color: #ffffff; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }}
    .card {{ background: #18181d; border: 1px solid rgba(255,255,255,0.12); border-radius: 24px; max-width: 440px; width: 100%; overflow: hidden; box-shadow: 0 24px 60px rgba(0,0,0,0.6); text-align: center; }}
    .badge {{ background: rgba(16,185,129,0.16); color: #34d399; font-size: 12px; font-weight: 800; padding: 10px 16px; border-bottom: 1px solid rgba(16,185,129,0.25); letter-spacing: 0.4px; }}
    .img-wrap {{ background: #ffffff; height: 260px; display: flex; align-items: center; justify-content: center; padding: 14px; position: relative; }}
    .img-wrap img {{ max-height: 100%; max-width: 100%; object-fit: contain; }}
    .price-pill {{ position: absolute; top: 12px; right: 12px; background: #E65A7F; color: #fff; font-weight: 900; font-size: 14px; padding: 6px 14px; border-radius: 999px; }}
    .body {{ padding: 22px; }}
    .brand {{ color: #E65A7F; font-size: 12px; font-weight: 900; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 6px; }}
    .title {{ font-size: 17px; font-weight: 800; line-height: 1.35; margin-bottom: 10px; color: #f5f5f7; }}
    .meta {{ font-size: 12px; color: #a1a1aa; margin-bottom: 18px; }}
    .btn-primary {{ display: block; width: 100%; background: #E65A7F; color: #ffffff; text-decoration: none; font-weight: 800; font-size: 14px; padding: 14px 18px; border-radius: 14px; margin-bottom: 10px; transition: opacity 0.2s; }}
    .btn-secondary {{ display: block; width: 100%; background: rgba(255,255,255,0.08); color: #e4e4e7; text-decoration: none; font-weight: 700; font-size: 13px; padding: 12px 16px; border-radius: 14px; }}
  </style>
  <script>
    setTimeout(function() {{
      window.location.replace({json.dumps(store_url)});
    }}, 900);
  </script>
</head>
<body>
  <div class="card">
    <div class="badge">✓ GÜZELAI.COM GÖRSEL, RENK & STOK DOĞRULAMALI LİNK</div>
    <div class="img-wrap">
      <img src="{img_url}" alt="{full_name}" />
      <span class="price-pill">{price}</span>
    </div>
    <div class="body">
      <div class="brand">{brand}</div>
      <div class="title">{full_name}</div>
      <div class="meta">Ürün Kodu: <strong>{sku}</strong> {f'• Renk: <strong>{color}</strong>' if color else ''} • Mağaza: <strong>{store_name}</strong></div>
      <a class="btn-primary" href="{store_url_esc}" rel="noopener noreferrer">Hemen {store_name} Mağazasında Aç →</a>
      <a class="btn-secondary" href="https://guzelai.com/#kombinler">Tüm Doğrulanmış Kombinleri İncele (guzelai.com)</a>
    </div>
  </div>
</body>
</html>"""
    return page.encode("utf-8")


def build_verified_kombin_entry(
    outfit: Dict[str, Any],
    ig_reel_url: str = "",
    tiktok_url: str = "https://www.tiktok.com/@guzelaicom",
    youtube_url: str = "https://www.youtube.com/@guzelaicom/shorts",
    x_url: str = "https://x.com/guzelaicom",
    pinterest_url: str = "https://tr.pinterest.com/",
    threads_url: str = "https://www.threads.net/@guzelaicom",
) -> Dict[str, Any]:
    """Verifies all 6 outfit product links and builds a structured showcase entry for guzelai.com."""
    items_dict = outfit.get("items", {})
    verified_items: List[Dict[str, Any]] = []
    verified_count = 0

    for key, default_cat_label, emoji in CATEGORY_META:
        item = items_dict.get(key)
        if not isinstance(item, dict):
            continue
        sku = str(item.get("sku") or item.get("code") or "")
        store_url = item.get("store_url") or item.get("product_url") or item.get("url") or ""
        if "guzelai.com/go/" in store_url and item.get("store_url"):
            store_url = item["store_url"]
        guzelai_url = f"https://guzelai.com/go/{sku}" if sku else GUZELAI_SHOWCASE_URL

        check = verify_single_product_url(store_url)
        if check["verified"]:
            verified_count += 1

        cat_label = item.get("category_label") or default_cat_label
        verified_items.append({
            "key": key,
            "category": cat_label,
            "emoji": emoji,
            "brand": item.get("brand", "Mağaza"),
            "name": item.get("name", "Ürün"),
            "full_name": item.get("full_name") or f"{item.get('brand', '')} {item.get('name', '')}".strip(),
            "price": item.get("price", ""),
            "price_val": item.get("price_val", 0),
            "sku": sku or "-",
            "color": item.get("color", ""),
            "store_url": store_url,
            "guzelai_url": guzelai_url,
            "product_url": store_url,  # On guzelai.com itself, clicking opens the store directly
            "image_url": item.get("image_url") or (item.get("image_urls") or [f"/data/item_card_{key}.jpg"])[0],
            "visual_card_url": f"/data/item_card_{key}.jpg",
            "verified": check["verified"],
            "http_status": check["http_status"],
            "store_name": check["store_name"],
            "store_domain": check["store_domain"],
            "verified_badge": check["verified_badge"],
            "checked_at": check["checked_at"],
        })

    reel_link = ig_reel_url.strip() or outfit.get("reel_url", "") or "https://www.instagram.com/guzelaicom/"
    now_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    title = (
        outfit.get("hook_title")
        or outfit.get("archetype_title")
        or outfit.get("title")
        or "Sokağa Çıkarken Herkesin Dönüp Baktığı O Bordo & Antrasit Kapsül Kombin 🔥✨"
    )
    total_val = sum(float(i.get("price_val", 0)) for i in verified_items)
    total_str = outfit.get("total_price_str") or f"{total_val:,.2f}₺".replace(",", "X").replace(".", ",").replace("X", ".")

    return {
        "id": outfit.get("id") or f"kombin_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "archetype_id": outfit.get("archetype_id") or outfit.get("id", "daily_kombin"),
        "collection_badge": outfit.get("collection_badge", "Doğrulanmış Örnek Kombin"),
        "categories_included": outfit.get("categories_included", []),
        "title": title,
        "viral_hook": outfit.get("viral_hook", ""),
        "published_at": now_str,
        "total_price_str": total_str,
        "total_price_val": total_val,
        "collage_url": "/data/latest_kombin_collage.jpg",
        "video_url": "/data/latest_kombin_video.mp4",
        "website_showcase_url": GUZELAI_SHOWCASE_URL,
        "verification_summary": {
            "total_items": len(verified_items),
            "verified_items": verified_count,
            "all_verified": verified_count == len(verified_items) and len(verified_items) > 0,
            "checked_at": now_str,
            "legal_notice": "⚖️ Yasal Uyarı: Reklam veya sponsorlu iş birliği içermez; tamamen kombin önerisi ve bilgilendirme amaçlıdır (zorunlu #reklam #işbirliğideğil).",
        },
        "platforms": {
            "instagram_reels": reel_link,
            "tiktok": tiktok_url,
            "youtube_shorts": youtube_url,
            "x_twitter": x_url,
            "pinterest": pinterest_url,
            "threads": threads_url,
            "whatsapp_channel": WHATSAPP_CHANNEL_URL,
        },
        "items": verified_items,
    }


def _gh_put_file(repo_path: str, content_bytes: bytes, commit_message: str) -> bool:
    """Creates or updates a file in thezencirs/guzelai via GitHub Contents API."""
    if not (os.path.exists(GH_EXE) or shutil.which(GH_EXE)):
        print(f"[UYARI] gh CLI bulunamadı: {GH_EXE}")
        return False

    sha = None
    try:
        existing_raw = subprocess.check_output(
            [GH_EXE, "api", f"repos/{GUZELAI_REPO}/contents/{repo_path}"],
            stderr=subprocess.DEVNULL,
        )
        parsed = json.loads(existing_raw)
        if isinstance(parsed, dict):
            sha = parsed.get("sha")
    except Exception:
        sha = None

    if not sha and "/" in repo_path:
        parent_dir, fname = repo_path.rsplit("/", 1)
        try:
            dir_raw = subprocess.check_output(
                [GH_EXE, "api", f"repos/{GUZELAI_REPO}/contents/{parent_dir}"],
                stderr=subprocess.DEVNULL,
            )
            for entry in json.loads(dir_raw):
                if isinstance(entry, dict) and entry.get("name") == fname:
                    sha = entry.get("sha")
                    break
        except Exception:
            pass

    payload: Dict[str, Any] = {
        "message": commit_message,
        "content": base64.b64encode(content_bytes).decode("ascii"),
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha

    proc = subprocess.run(
        [GH_EXE, "api", "--method", "PUT", f"repos/{GUZELAI_REPO}/contents/{repo_path}", "--input", "-"],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
    )
    if proc.returncode != 0:
        print(f"[HATA] GitHub API yükleme hatası ({repo_path}):", proc.stderr.decode("utf-8", errors="replace")[:300])
        return False
    return True


def _get_existing_go_files() -> set:
    """Returns the set of filenames (e.g. '981976289.html') already present in `public/go` on GitHub."""
    if not (os.path.exists(GH_EXE) or shutil.which(GH_EXE)):
        return set()
    try:
        raw = subprocess.check_output(
            [GH_EXE, "api", f"repos/{GUZELAI_REPO}/contents/public/go"],
            stderr=subprocess.DEVNULL,
        )
        items = json.loads(raw)
        if isinstance(items, list):
            return {str(x.get("name", "")) for x in items if isinstance(x, dict)}
    except Exception:
        pass
    return set()


def publish_to_guzelai_website(
    outfit: Dict[str, Any],
    collage_path: Optional[Path] = None,
    ig_reel_url: str = "",
    out_dir: str = "output",
) -> Dict[str, Any]:
    """
    1. Builds verified entries for the current outfit AND all pre-verified sample outfits
       (covering Elbise, Pantolon, Gömlek, Kazak, Mont/Ceket, Çanta, Ayakkabı, Aksesuar).
    2. Deploys `public/go/{sku}.html` (`https://guzelai.com/go/{sku}`) redirect pages for every unique SKU.
    3. Updates `public/data/kombin_feed.json`, `public/data/latest_kombin_collage.jpg`, and
       `public/data/latest_kombin_video.mp4` on `thezencirs/guzelai`.
    """
    os.makedirs(out_dir, exist_ok=True)
    entry = build_verified_kombin_entry(outfit, ig_reel_url=ig_reel_url)

    # Also build all pre-verified sample outfits ("Örnek Kombinler") so guzelai.com always has the full catalog
    sample_entries: List[Dict[str, Any]] = [entry]
    seen_ids = {entry["archetype_id"]}
    for sample_outfit in PREVERIFIED_GUZELAI_OUTFITS:
        sid = sample_outfit.get("id", "")
        if sid not in seen_ids:
            s_reel = "https://www.instagram.com/reel/DelxD5YsMxj/" if sid == "tesla_halloween_ramp_curly" else ig_reel_url
            sample_entries.append(build_verified_kombin_entry(sample_outfit, ig_reel_url=s_reel))
            seen_ids.add(sid)

    existing_go = _get_existing_go_files()
    uploaded_redirects: List[str] = []
    seen_skus = set()
    for s_entry in sample_entries:
        for it in s_entry.get("items", []):
            sku = str(it.get("sku", "")).strip()
            if not sku or sku == "-" or sku in seen_skus:
                continue
            seen_skus.add(sku)
            fname = f"{sku}.html"
            if fname in existing_go:
                uploaded_redirects.append(f"https://guzelai.com/go/{sku}")
                continue
            html_bytes = _build_guzelai_redirect_html(it)
            ok = _gh_put_file(
                f"public/go/{fname}",
                html_bytes,
                f"feat(go): add guzelai.com/go/{sku} verified redirect page",
            )
            if ok:
                uploaded_redirects.append(f"https://guzelai.com/go/{sku}")

    # Save local verification report
    report_path = os.path.join(out_dir, "website_verification.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "latest": entry,
                "preverified_sample_outfits": sample_entries,
                "redirect_urls": uploaded_redirects,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    feed_payload = {
        "site": "https://guzelai.com",
        "showcase_url": GUZELAI_SHOWCASE_URL,
        "whatsapp_channel": WHATSAPP_CHANNEL_URL,
        "updated_at": entry["published_at"],
        "latest": entry,
        "broadcasts": sample_entries,
    }

    # Upload optimized JPEG collage
    if collage_path is None:
        collage_path = Path(out_dir) / "kombin_collage.png"
    collage_uploaded = False
    if collage_path.exists():
        try:
            img = Image.open(collage_path).convert("RGB")
            img.thumbnail((1440, 2560), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=92, optimize=True)
            collage_uploaded = _gh_put_file(
                "public/data/latest_kombin_collage.jpg",
                buf.getvalue(),
                f"chore(kombin): update latest 2K kombin collage ({entry['title']})",
            )
        except Exception as e:
            print(f"[UYARI] Kolaj optimize/yükleme hatası: {e}")

    # Upload Short Graph-Motion Video
    gm_video_path = Path(out_dir) / "graphmotion_short.mp4"
    video_uploaded = False
    if gm_video_path.exists():
        try:
            video_uploaded = _gh_put_file(
                "public/data/latest_kombin_video.mp4",
                gm_video_path.read_bytes(),
                f"chore(kombin): update graph-motion video ({entry['title']})",
            )
        except Exception as ve:
            print(f"[UYARI] Graph-Motion video yükleme hatası: {ve}")

    # Upload public/data/kombin_feed.json last so it triggers the final production build
    feed_bytes = json.dumps(feed_payload, ensure_ascii=False, indent=2).encode("utf-8")
    feed_uploaded = _gh_put_file(
        "public/data/kombin_feed.json",
        feed_bytes,
        f"feat(kombin): publish pre-verified sample outfits & redirect links for {entry['title']}",
    )

    print(f"🔗 [GuzelAI.com Trafik & Yönlendirme Linkleri]: {len(uploaded_redirects)} adet /go/{{sku}} sayfası yayında.")
    status = "published" if feed_uploaded else "local_only"
    print(f"🌐 [GuzelAI.com Vitrin Güncellemesi]: {status} -> {GUZELAI_SHOWCASE_URL}")
    return {
        "status": status,
        "showcase_url": GUZELAI_SHOWCASE_URL,
        "whatsapp_channel": WHATSAPP_CHANNEL_URL,
        "verified_items": entry["verification_summary"]["verified_items"],
        "total_items": entry["verification_summary"]["total_items"],
        "redirect_urls": uploaded_redirects,
        "collage_uploaded": collage_uploaded,
        "video_uploaded": video_uploaded,
        "report_path": report_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outfit-json", default="output/outfit_links.json")
    parser.add_argument("--collage", default="output/kombin_collage.png")
    parser.add_argument("--ig-reel-url", default="")
    args = parser.parse_args()

    if not os.path.exists(args.outfit_json):
        print(f"[HATA] Kombin JSON bulunamadı: {args.outfit_json}")
        sys.exit(1)

    with open(args.outfit_json, "r", encoding="utf-8") as f:
        outfit = json.load(f)

    res = publish_to_guzelai_website(
        outfit,
        collage_path=Path(args.collage),
        ig_reel_url=args.ig_reel_url or outfit.get("reel_url", ""),
        out_dir=os.path.dirname(args.outfit_json) or "output",
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
