# Hashtag Robotics SO-101 Control Plane

Bu belge control plane'in Türkçe teknik özetidir. Uçtan uca açık kaynak XOX
paketi, baskı dosyaları, güncel 120K model, dataset ve güvenli çalıştırma sırası
için ana [İngilizce README](README.md) ile [donanım paketini](hardware/README.md)
kullanın.

Hashtag Robotics'in sattığı SO-101 leader/follower setleri için local-first,
kurulabilir ve agent-safe robot kontrol platformu.

Platform; cihaz keşfi, robot profili, kalibrasyon, kamera, teleoperation,
dataset, training, evaluation, Strands ajanları ve simülasyon işlerini tek bir
kalıcı control plane içinde birleştirir.

## Mevcut durum

`v0.2.0` software-only baseline tamamlandı ve fiziksel
hardware-in-the-loop (HIL) test sınırına getirildi.

Çalışan yüzey:

- FastAPI local control plane ve React/TypeScript dashboard
- SQLite persisted job, resource lease, approval ve audit
- Read-only serial discovery ve stable device fingerprint
- Hashtag Robot/Camera/Dataset/Policy manifestleri
- Safe mock teleop, recording, replay ve calibration workflow'ları
- Dataset → validation → training → policy → evaluation zinciri
- Gerçek LeRobot `0.6.0` console-script adapter contract'ları
- Strands Agents `1.48.0` structured planner ve deterministic command gateway
- MuJoCo SO-101 altı-joint contract simulation
- Remote inference TLS/latency contract
- Doctor, capability manifest, diagnostics ve HIL checklist
- Python wheel içine gömülü production dashboard

Gerçek robot actuation varsayılan olarak kapalıdır:

```text
HASHTAG_ENABLE_PHYSICAL=false
```

Fiziksel test sırasında bile hareket; resolved resource, calibration, joint
limit, emergency stop, deterministic preflight ve tek kullanımlık kullanıcı
approval'ı olmadan başlayamaz.

## Mimari ayrım

| Katman | Sorumluluk |
|---|---|
| LeRobot | SO-101 donanım, calibration, dataset, training ve rollout |
| Strands Robots | Geniş robot/policy/sim/ROS entegrasyon yüzeyi |
| Strands Agents | Reasoning, structured planning ve workflow |
| Hashtag platform | Product profile, jobs, leases, safety, audit ve UX |

Strands Robots kararlı PyPI sürümünün LeRobot `0.6.0` ile bilinen dependency
uyuşmazlığı nedeniyle bu baseline'a doğrudan kurulmadı. Runtime capability
probe hazırdır; uyumlu kararlı release/commit seçilince adapter açılacaktır.

## Hızlı başlangıç

Geliştirme ortamı:

```bash
uv sync --extra dev --extra agents --extra sim --extra so101
npm install --prefix frontend
```

Dashboard'u build et:

```bash
npm --prefix frontend run build
```

Local uygulamayı başlat:

```bash
HASHTAG_DATA_DIR=.local-data \
HASHTAG_OPEN_BROWSER=false \
uv run hashtag-robotics serve
```

Ardından:

```text
http://127.0.0.1:8765
```

Read-only sistem kontrolü:

```bash
HASHTAG_DATA_DIR=.local-data uv run hashtag-robotics doctor
HASHTAG_DATA_DIR=.local-data uv run hashtag-robotics capabilities
uv run hashtag-robotics hil-checklist
```

## Doğrulama

Bütün software-only gate'leri:

```bash
bash scripts/verify.sh
```

Bu workflow:

1. Python lint/format kontrolü
2. Backend/unit/API/contract testleri
3. Frontend TypeScript kontrolü
4. Production frontend build
5. Python sdist/wheel build
6. Wheel içindeki dashboard asset kontrolü

çalıştırır.

Paket oluşturma:

```bash
bash scripts/build-package.sh
```

Üretilen wheel:

```text
dist/hashtag_robotics-0.2.0-py3-none-any.whl
```

Temiz ortam kurulumu:

```bash
uv tool install dist/hashtag_robotics-0.2.0-py3-none-any.whl
hashtag-robotics
```

Proje geliştirilirken editable/managed environment için `uv run` tercih edilir.

## Strands Agent Studio

Deterministic agent command gateway model credential'ı olmadan çalışır.

Canlı Strands planning açmak için model ID açıkça verilir:

```bash
HASHTAG_AGENT_MODEL="<strands-model-id>" \
HASHTAG_DATA_DIR=.local-data \
uv run hashtag-robotics serve
```

Strands modeli hiçbir raw serial, shell veya servo tool görmez. Yalnızca
structured plan üretir; plan rol izinlerinden geçer ve gerçek execution
Hashtag Agent Gateway tarafından yapılır.

## Yerel erişim koruması

Control plane loopback'te dinler ve üç bağımsız kapı uygular:

- **Host allowlist** — kendi alan adını `127.0.0.1`'e çözen bir sayfa (DNS
  rebinding) yine kendi Host başlığını gönderir ve reddedilir.
- **Origin allowlist** — başka bir sitenin isteği reddedilir.
- **Oturum token'ı** — koşum başına üretilir, `GET /api/session` ile dashboard'a
  verilir; `/api/health` dışındaki bütün uçlar ve event soketi bunu ister.

`HASHTAG_ENABLE_PHYSICAL=true` iken loopback dışı bir adrese bind **reddedilir**.
Başka bir makineden erişmek için SSH tüneli kullanın:

```bash
ssh -L 8770:127.0.0.1:8770 kullanici@makine
```

E-stop mandalı kalıcıdır ve yeniden başlatmayı aşar. Panel açılmıyorsa:

```bash
hashtag-robotics clear-estop
```

## Fiziksel test

Robotları bağlamadan önce:

1. [HIL Test Planı](docs/HIL_TEST_PLANI_TR.md) tamamen okunmalı.
2. Kullanıcı `dialout` grubunda olmalı (`sudo usermod -aG dialout <kullanıcı>`,
   sonra oturum yenilenmeli; yenilenmediyse komutlar `sg dialout -c '...'` ile
   sarılmalı).
3. `hashtag-robotics doctor` blocked sonuç vermemeli.
4. Leader/follower port ve kimlikleri read-only çözülmeli.
5. Mevcut calibration `hashtag-robotics import-calibration <dizin>` ile içe
   aktarılmalı; kalibrasyon işi zaten başlamadan önce yedek alır.
6. E-stop yolu robot enerjilenmeden doğrulanmalı.
7. İlk hareket calibration değil, düşük limitli kısa teleop preflight olmalı.

`HASHTAG_ENABLE_PHYSICAL=true` yalnız fiziksel test oturumunda ve kullanıcı
hazırken açılır.

## Dokümanlar

Önerilen okuma sırası:

1. [Ekosistem Araştırması](docs/EKOSISTEM_ARASTIRMASI_TR.md)
2. [Hedef Ürün ve Backend Mimarisi](docs/HEDEF_MIMARI_TR.md)
3. [Uygulama Durumu](docs/UYGULAMA_DURUMU_TR.md)
4. [Workflow Kataloğu](docs/WORKFLOW_KATALOGU_TR.md)
5. [Uyumluluk Matrisi](docs/UYUMLULUK_MATRISI_TR.md)
6. [Faz Bazlı Yol Haritası](docs/YOL_HARITASI_TR.md)
7. [HIL Test Planı](docs/HIL_TEST_PLANI_TR.md)
8. [Ürün Kararları ve Risk Kaydı](docs/KARARLAR_VE_RISKLER_TR.md)

## Güvenlik sınırı

Bu sürüm fiziksel test hazırlığıdır; doğrulanmış production robot controller
değildir. Gerçek SO-101 testleri Mert'in robotları bağlaması, çalışma alanını
hazırlaması ve her actuation adımını açıkça onaylamasıyla birlikte yapılacaktır.
