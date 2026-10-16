# 👗 Otomatik Instagram Kombin Reels Botu (0₺ Maliyet • GitHub Actions)

Bilgisayarınız tamamen kapalı olsa bile her gün **Sabah 10:00**, **Öğlen 15:00** ve **Akşam 20:00** saatlerinde:
1. Gerçek kıyafet fotoğraflarını şeffaf dekupe (cutout) olarak bir araya getirip **Graph Motion** animasyonuyla (`@nemigiymeli` kolaj stilinde) fiyat ve marka etiketleriyle dizer,
2. Ardından kombinin birebir aynı parçalarını **sokakta yürüyen gerçekçi bir modele giydirip** yürüyüş videosuna dönüştürür,
3. Hazırlanan **9:16 Dikey Reels (1080x1920)** videosunu otomatik olarak Instagram profilinizde paylaşır.

---

## 🚀 3 Adımda Ücretsiz Kurulum (GitHub Actions)

### 1. Bu Klasörü GitHub'a Yükleyin
1. [github.com/new](https://github.com/new) adresinden yeni bir **Public** (Açık) repository oluşturun *(Public depolarda GitHub Actions tamamen **ücretsiz ve sınırsızdır**)*.
2. Bu klasördeki tüm dosyaları (`src/`, `.github/workflows/daily_reels.yml`, `assets/`, `requirements.txt`) GitHub deponuza yükleyin.

### 2. GitHub Secrets Ayarlarını Ekleyin
GitHub deponuzda **Settings -> Secrets and variables -> Actions -> New repository secret** bölümüne giderek aşağıdaki bilgileri ekleyin:

| Secret / Variable Adı | Açıklama | Zorunlu mu? |
| :--- | :--- | :--- |
| `IG_USERNAME` | Instagram kullanıcı adınız | Evet (instagrapi için) |
| `IG_PASSWORD` | Instagram şifreniz | Evet (instagrapi için) |
| `IG_WATERMARK` | *(Variables sekmesine)* Arka plan filigranı (Örn: `@seninsayfan`) | İsteğe bağlı |
| `HF_TOKEN` | Ücretsiz Hugging Face Read Token (AI video kuyruğunda öncelik sağlar) | İsteğe bağlı |

> **İpucu (Resmi Graph API kullanmak isterseniz):** `IG_USERNAME` yerine ücretsiz Meta Developer üzerinden alacağınız `IG_ACCESS_TOKEN` ve `IG_USER_ID` değerlerini de girebilirsiniz. Her iki yöntem de `src/instagram_uploader.py` içinde hazır desteklenmektedir.

### 3. İlk Denemeyi GitHub Üzerinden Tek Tıkla Başlatın
- GitHub deponuzda **Actions** sekmesine tıklayın.
- Soldaki **"Otomatik Instagram Kombin Reels (Günde 3 Kez)"** iş akışını seçip sağdaki **"Run workflow"** butonuna basın.
- Sistem her gün Türkiye saatiyle **10:00, 15:00 ve 20:00**'de (`cron: '0 7,12,17 * * *'`) otomatik olarak çalışacaktır.
