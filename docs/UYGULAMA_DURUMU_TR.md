# Uygulama Durumu

**Sürüm:** `0.1.0`
**Anlık görüntü:** 30 Temmuz 2026
**Durum:** Fiziksel yol uçtan uca yazıldı ve sahte donanımla doğrulandı; gerçek
SO-101 üzerinde HIL testleri bekleniyor

## 0. 30 Temmuz 2026 turunda ne değişti

23 Temmuz'daki software-only iskelet, gerçek donanıma bağlanabilir hâle getirildi:

- **LeRobot 0.6 komut sözleşmesi düzeltildi.** Robot tipleri `so101_follower` /
  `so101_leader`, record ve replay argümanları `--dataset.*` altında, rollout
  süre/strateji sözleşmesiyle. Üretilen argv artık LeRobot'un kendi draccus
  parser'ına verilerek test ediliyor.
- **Fiziksel komutlar PTY üzerinden sürülüyor** (K-011); operatör tuşları
  `POST /api/jobs/{id}/input` ile gönderiliyor, stdout'tan eklem tabloları,
  kalibrasyon aralıkları ve loop zamanlaması ayrıştırılıyor.
- **Hedefler sunucuda çözülüyor** (K-010); istemcinin gönderdiği port, cihaz adı
  ve limit atılıyor, onay token'ı çözümlenmiş hedeflerin hash'ine de bağlanıyor.
- **Kameralar `/dev/v4l/by-id` üzerinden** açılıyor, ölçülen FPS/gecikme
  raporlanıyor, MJPEG önizleme exclusive lease altında akıyor.
- **Uydurulan sonuçlar silindi** (K-012): dataset bütünlüğü diskten okunuyor,
  policy manifest'i checkpoint dizininden çıkarılıyor, rollout başarısı
  operatörün bölüm bazlı işaretlemesinden geliyor.
- **Yerel güvenlik katmanı eklendi**: Host/Origin allowlist, koşum başına oturum
  token'ı ve fiziksel modda loopback dışına bind reddi (K-013).

## 1. Sonuç

Platform bütün roadmap fazlarının yazılım iskeletini ve güvenlik sınırını tek
çalışan uygulamada birleştirir. Bu, bütün production özelliklerinin bitmiş
olduğu anlamına gelmez.

Tamamlanan eşik:

```text
install/build
  → local dashboard
  → doctor/capability
  → persisted jobs
  → leases/approval/audit
  → sunucu tarafı hedef çözümlemesi
  → PTY üzerinden gerçek LeRobot komutları
  → diskten okunan dataset/policy artifact'leri
  → Strands planner boundary
  → MuJoCo contract simulation
  → LeRobot physical command adapter
  → HIL gate
```

Bekleyen eşik:

```text
gerçek leader/follower bağla
  → port/fingerprint
  → calibration backup
  → camera mapping
  → düşük limitli teleop
  → gerçek recording
  → gerçek policy rollout
```

## 2. Faz durumu

| Faz | Donanımsız durum | Fiziksel/harici doğrulama |
|---|---|---|
| Faz 0 | Tamamlandı; CI her push'ta koşuyor | Temiz OS matrisi genişletilecek |
| Faz 1 | Kurulum sihirbazı, PTY, kalibrasyon, kamera ve teleop yolu yazıldı | Leader/follower/kamera HIL bekliyor (T1-T7) |
| Faz 2 | Dataset/policy artifact'leri diskten okunuyor; başarı operatörden | Gerçek training benchmark'ı bekliyor |
| Faz 3 | Deterministic gateway + optional Strands planner hazır | Model provider ve red-team oturumu bekliyor |
| Faz 4 | MuJoCo contract sim + remote TLS contract hazır | Validated digital twin ve uzak GPU bekliyor (T8) |
| Faz 5 | Wheel, diagnostics, fleet-local, update status ve CI hazır | Installer signing, cloud ve support operasyonu bekliyor |

## 3. Çalışan backend yüzeyi

### Control plane

- FastAPI application factory
- Local-only varsayılan bind
- SQLite WAL
- Startup seed ve interrupted job recovery
- Typed Pydantic domain modelleri
- REST ve WebSocket event snapshot

### İş yönetimi

- Persisted job state machine
- Worker queue
- Progress
- Safe cancel/abort
- Emergency stop
- Restart sonrası `interrupted`
- Correlation ID

### Resource yönetimi

- Exclusive ve shared-read lease
- Transactional acquisition
- Heartbeat ve TTL
- Job sonunda kesin release
- Çakışmada deterministic `resource_busy`

### Safety

- `read_only`, `sim`, `real` target ayrımı
- Physical mode environment gate
- LeRobot executable doğrulaması
- Sunucu tarafı hedef çözümlemesi: profil, fingerprint→port, kalibrasyon
  revizyonu/checksum, limit tavanı, action shape, kamera eşlemesi
- İstemcinin verebileceği tek beyan `workspace_confirmed`
- Parametre **ve** çözümlenmiş hedef hash'ine bağlı beş dakikalık approval
- Confirmation öncesi ve sonrası yeniden preflight; hedef değişmişse
  `targets_changed` ile blok
- Kalıcı emergency-stop mandalı (yeniden başlatmayı aşar) + `clear-estop`
- Kalibrasyon işinden önce zorunlu yedek; yedek başarısızsa iş başlamaz

## 4. Faz 1 robot yüzeyi

### Hazır

- Read-only serial discovery
- Stable fingerprint
- Simulated SO-101 ve local compute inventory
- Robot, camera ve calibration revision sözleşmeleri
- Kamera semantic key modeli
- Kurulum sihirbazı: tara → rol/ad → motor setup → kalibrasyon → doğrula
- Canlı MIN/POS/MAX aralık tablosu ve operatör tuşları
- Sunucunun çalıştıracağı komutun önizlemesi (preflight'ıyla birlikte)
- Shell kullanmadan LeRobot subprocess adapter
- SIGINT → timeout → kill güvenli stop sırası
- Output redaction

### Fiziksel test bekleyen

Aşağıdakilerin tamamı **yazıldı ve sahte donanımla doğrulandı**; eksik olan
gerçek SO-101 üzerinde koşulmalarıdır:

- Feetech follower/leader kimlik eşleme (çıkar-tak sonrası aynı profile çözülme)
- Gerçek kalibrasyon sihirbazı ve canlı MIN/POS/MAX aralıkları
- Kamera discovery, ölçülen FPS ve canlı preview
- Gerçek teleop loop telemetrisi
- Torque/power durumu — henüz hiç okunmuyor, ürün yüzeyinde yok
- Donanım E-stop yolu — şu an yalnız UI düğmesi ve ESC tuşu var

## 5. Faz 2 data/policy yüzeyi

### Hazır

- `meta/info.json` ve yanındaki dosyalardan okunan DatasetManifest
  (bölüm, kare, fps, robot tipi, feature sözleşmesi, action shape)
- Dört seviyeli bütünlük: `verified` / `incomplete` / `missing` / `unsupported`,
  her biri gerekçesiyle
- Diski yeniden okuyan dataset validation job'ı
- Checkpoint dizininden çıkarılan PolicyManifest (adım, policy tipi, kaynak repo,
  feature sözleşmesi); ağırlık yoksa policy kaydedilmez
- Operatörün bölüm bazlı işaretlemesinden hesaplanan başarı oranı
- `lerobot-train` typed command builder ve dataset'siz eğitimi engelleyen gate

### Gerçek benchmark bekleyen

- Hub push/pull
- ACT gerçek training (yerel CUDA yok; Orin'de T8)
- MPS/CUDA kaynak ölçümü
- Processor chain'in checkpoint'ten tam çıkarımı
- Rollout videosu

## 6. Faz 3 agent yüzeyi

### Hazır

- Beş rol:
  - Lab Assistant
  - Dataset Curator
  - Training Advisor
  - Evaluation Analyst
  - Robot Operator
- Role → allowed action allowlist
- Deterministic command conversion
- Permission denial
- Agent/job correlation
- Optional Strands `1.48.0` structured planner
- Model planı ile execution ayrımı
- Strands'e raw robot tool verilmemesi

### Harici doğrulama bekleyen

- Seçilecek model provider
- Credential/keychain
- Gerçek prompt/trace redaction
- Prompt injection dataset'i
- Human-in-the-loop UI resume
- OTLP/observability backend

## 7. Faz 4 simulation/remote yüzeyi

### Hazır

- Safe mock simulation
- Gerçek MuJoCo runtime
- Altı joint'li SO-101 contract MJCF
- 30 Hz control / 500 Hz physics test
- Joint range violation ölçümü
- Kamera contract
- Remote endpoint TLS requirement
- Remote probe'un network access yapmayan dry-run sonucu

### Açık sınır

MuJoCo modeli bir **contract modelidir**, ölçülmüş SO-101 digital twin değildir.
Link geometrisi, kütle, inertia, actuator dynamics, backlash ve Feetech davranışı
gerçek robot üzerinden tanımlanmamıştır.

## 8. Faz 5 productization yüzeyi

### Hazır

- Production React build
- Frontend asset'lerini içeren Python wheel
- `hashtag-robotics` CLI
- `doctor`
- `capabilities`
- `import-calibration`
- `clear-estop`
- `hil-checklist`
- Diagnostics API
- Local fleet view
- Update status contract
- Build ve verification scripts

### Bekleyen

- PyPI publish
- Package/marka adı kesin kararı
- macOS signing/notarization
- Windows installer kararı
- Automatic update ve rollback
- Hashtag SKU provisioning servisi
- Cloud user/organization/fleet

## 9. Test sonucu

Donanımsız test paketi (30 Temmuz 2026'da **116 test geçti**):

- API, seed, read-only discovery, lease semantiği, audit
- LeRobot argv sözleşmesi — LeRobot'un kendi draccus parser'ıyla doğrulanır
- PTY süreç omurgası: ENTER teslimi, ok tuşları, süreç grubu durdurma,
  yeniden başlatma sonrası yetim temizliği, PID yeniden kullanımı
- Kalibrasyon: checksum, yedek-önce kuralı, revizyon zinciri, geri yükleme
- Sunucu tarafı safety: istemci beyanının geçmediği, port sızdırılamadığı,
  kalibrasyon kayması, e-stop mandalı, ayrık leader/follower, kamera çözümlemesi
- Bayat onay: kol başka porta düşünce `targets_changed`
- Kamera: by-id çözümleme, ölçülen FPS/gecikme, MJPEG, exclusive lease
- Dataset bütünlüğü ve checkpoint okuma (gerçek v3.0 düzeninden fixture)
- Operatör annotation'ı ve yalnız bölümlü işlerin işaretlenebilmesi
- Yerel güvenlik: token, Host/Origin allowlist, WebSocket, loopback kuralı

Fiziksel yol, sahte pyserial katmanı ve sahte `lerobot-calibrate` ile uçtan uca
sürülerek doğrulandı (`scripts/demo_fake_arm.py`). Kesin sonuç her zaman
`bash scripts/verify.sh` çıktısından alınmalıdır.

## 10. Kod haritası

```text
src/hashtag_robotics/
├── api.py               API, runtime composition ve erişim koruması
├── models.py            Domain contract'ları
├── repository.py        SQLite, jobs, leases, approvals, flags, audit
├── jobs.py              Job coordinator, approval, e-stop mandalı, annotation
├── safety.py            Sunucu tarafı hedef çözümlemesi ve preflight
├── security.py          Host/Origin allowlist ve oturum token'ı
├── workflows.py         Workflow engine ve artifact toplama
├── hardware.py          LeRobot CLI adapter (argüman dizisi, shell yok)
├── process.py           PTY/pipe süreç yönetimi, süreç grubu, yetim temizliği
├── telemetry.py         stdout ayrıştırma (loop, eklem, kalibrasyon aralığı)
├── calibration.py       Kalibrasyon oku/arşivle/geri yükle/içe aktar
├── camera.py            by-id kamera çözümleme, probe, MJPEG
├── dataset.py           LeRobotDataset v3.0 metadata ve bütünlük
├── policy.py            Checkpoint dizini okuma
├── simulation.py        MuJoCo contract adapter
├── agents.py            Deterministic agent gateway
├── strands_runtime.py   Optional structured Strands planner
├── doctor.py            Capability ve compatibility
├── discovery.py         Read-only device discovery (serial + kamera)
├── seeding.py           Safe başlangıç profilleri
└── web/                 Derlenmiş dashboard

frontend/
├── src/App.tsx          10 görünüm: kurulum sihirbazı, operate, kamera stüdyosu…
├── src/api.ts           REST istemcisi, oturum token'ı, event soketi
└── src/styles.css

tests/
├── test_api.py          API akışları ve annotation
├── test_calibration.py  Kalibrasyon arşivi ve revizyon zinciri
├── test_camera.py       Kamera çözümleme, probe, MJPEG, lease
├── test_contracts.py    Argv'yi LeRobot'un kendi parser'ına verir
├── test_dataset.py      Dataset bütünlüğü ve checkpoint okuma
├── test_hardware.py     Komut kurucusu
├── test_physical.py     PTY, onay, e-stop mandalı, bayat onay
├── test_process.py      Süreç grubu ve yetim temizliği
├── test_repository.py   Lease semantiği
├── test_safety.py       Sunucu tarafı çözümleme ve red gerekçeleri
├── test_security.py     Host/Origin/token ve loopback kuralı
├── test_simulation.py   MuJoCo joint limit sözleşmesi
└── test_telemetry.py    stdout ayrıştırıcıları

scripts/
├── verify.sh            ruff + pytest + tsc + wheel
└── build-package.sh     Frontend build'ini wheel'e gömer

.github/workflows/ci.yml  Hızlı `software` işi + ağır `lerobot-contract` işi
```

## 11. Doğru sonraki adım

Yeni feature eklemek değil, [HIL Test Planı](HIL_TEST_PLANI_TR.md) T0→T8 sırasını
gerçek kolla koşmaktır. Ön koşullar:

```bash
sudo usermod -aG dialout <kullanıcı>     # sonra oturumu yenile
ls -l /dev/serial/by-id/                 # iki kol görünmeli
HASHTAG_ENABLE_PHYSICAL=true uv run hashtag-robotics serve
```

Oturum yenilenmediyse seri porta dokunan komutlar `sg dialout -c '...'` ile
sarılmalıdır. Sıra: T1/T2 kimlik → T3 kalibrasyon → T5/T6 e-stop ve düşük
limitli teleop → T4/T7 kamera ve tek bölüm kayıt/replay → T8 rollout (Orin).
