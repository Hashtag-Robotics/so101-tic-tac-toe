# Ürün Kararları ve Risk Kaydı

**Son güncelleme:** 30 Temmuz 2026
**Amaç:** Onaylanmış yönü, açık kararları ve önemli teknik/ürün risklerini tek
yerde tutmak.

## 1. Onaylanmış kararlar

### K-001 — LeLab kopyalanmayacak

**Karar:** LeLab kullanıcı akışları ve teknik fikirler için referans alınacak;
Hashtag platformu bağımsız control plane, job ve safety mimarisi kuracak.

**Gerekçe:** LeLab fikri doğruluyor fakat Hashtag'in cihaz profili, kalıcı job,
resource lease, Strands ajanı ve ticari destek farklarını sağlamıyor.

### K-002 — LeRobot source of truth

**Karar:** SO-101 donanımı, calibration, dataset ve training sözleşmelerinde
LeRobot ana upstream kaynaktır.

**Gerekçe:** Bu yüzeyleri yeniden yazmak maliyetli, riskli ve upstream
uyumluluğunu bozar.

### K-003 — Strands orkestrasyon katmanı

**Karar:** Strands Robots entegrasyon genişliği, Strands Agents ise reasoning ve
workflow için kullanılacak; ikisi de deterministic safety'nin yerine geçmeyecek.

### K-004 — Local-first

**Karar:** Temel robot işlemleri internet veya cloud olmadan çalışacak.

**Gerekçe:** Teleop, stop, kamera ve donanım bağlantısı ağ servislerine bağımlı
olamaz.

### K-005 — Python canonical runtime

**Karar:** Ürünün ana backend/runtime ve canonical package'ı Python olacaktır.
NPM veya desktop installer daha sonra launcher olabilir.

### K-006 — SO-101 depth-first

**Karar:** İlk ürün, çok sayıda robotu yüzeysel desteklemek yerine Hashtag
SO-101 leader/follower setini uçtan uca destekleyecek.

### K-007 — Safety before agent actuation

**Karar:** Ajanlar ilk aşamada read-only/advisory olacak. Gerçek robot aksiyonu
ancak deterministic gateway, resource lease, preflight ve UI onayı üzerinden
çalışacak.

### K-008 — Capability-driven product

**Karar:** UI, dokümanda veya `main` dalında görülen özelliği otomatik
destekleniyor kabul etmeyecek. Kurulu gerçek paket ve contract testi belirleyici
olacak.

### K-009 — Persisted job model

**Karar:** Calibration, teleop, recording, training ve rollout gibi süreçler
process içi global state değil kalıcı Job olarak yönetilecek.

### K-010 — Fiziksel hedefleri yalnız sunucu çözer

**Karar:** İstemci port, cihaz adı, kalibrasyon revizyonu veya hareket limiti
gönderemez. Bu değerler `robot_profile_id`'den sunucuda çözülür, istemcinin
gönderdiği kopyalar komut kurulmadan önce atılır. İstemcinin verebileceği tek
karar `workspace_confirmed`'dır.

**Gerekçe:** Preflight istemcinin `"calibration_verified": true` gibi
beyanlarına bakarken POST atabilen herkes rastgele bir cihaza hareket yetkisi
verebiliyordu. Onay token'ı artık parametre hash'ine ek olarak çözümlenmiş
hedeflerin hash'ine de bağlıdır; kol onayla başlatma arasında başka porta
düşerse iş `targets_changed` ile bloklanır.

### K-011 — Fiziksel komutlar PTY üzerinden sürülür

**Karar:** LeRobot alt süreçleri pipe değil pseudo-terminal üzerinden çalıştırılır;
operatör tuşları `POST /api/jobs/{id}/input` ile gönderilir.

**Gerekçe:** `lerobot-calibrate` ve `lerobot-setup-motors` `input()` ile ENTER
bekler (pipe'ta `EOFError`), `lerobot-record` ise `sys.stdin.isatty()` yanlışsa
bölüm kontrolünü sessizce devre dışı bırakır. Wayland oturumunda global klavye
yakalanamadığı için PTY tek çalışan yoldur.

### K-012 — Ölçülmeyen sayı raporlanmaz

**Karar:** Dataset bölüm/kare sayıları `meta/info.json` ve yanındaki dosyalardan
okunur; policy manifest'i checkpoint dizininden çıkarılır; rollout başarısı
operatörün bölüm bazlı işaretlemesinden gelir. Hiçbiri iş parametrelerinden
türetilmez veya uydurulmaz.

**Gerekçe:** Eski akış tek kare yazmadan dataset'i `verified` işaretliyor ve
`successes = episodes - 1` diye başarı üretiyordu. Bu sayılar bir satın alma
veya eğitim kararına girerse zarar verir.

### K-013 — Fiziksel control plane loopback'te kalır

**Karar:** `HASHTAG_ENABLE_PHYSICAL=true` iken loopback dışı bir adrese bind
reddedilir. Uzaktan erişim SSH tüneliyle yapılır.

**Gerekçe:** Robotu hareket ettirebilen bir servisin LAN'a açılması, yerel
güvenlik katmanının (Host/Origin allowlist + oturum token'ı) varsaydığı tehdit
modelinin dışına çıkar.

### K-014 — HIL T1-T7 laptopta, rollout Orin'de

**Karar:** Kurulum, kimlik, kalibrasyon, kamera, teleop ve kayıt (HIL T1-T7)
Ubuntu laptopta koşulur. Yalnız gerçek policy rollout (T8) Jetson Orin Nano'da
çalışır; oraya SSH tüneliyle bağlanılır (`ssh -L 8770:127.0.0.1:8770 ...`,
Orin'de 8765 doludur).

**Gerekçe:** Teleop, motor setup, kalibrasyon, kamera ve dataset kaydı GPU
istemez — yalnız USB seri port ve kamera ister. Orin'in çalışan ortamı
Python 3.10 + LeRobot 0.4.4'tür ve bu uygulama 3.12 + LeRobot 0.6 ister;
Orin'i yükseltmek JetPack 6.2 için py3.12 torch wheel'i bulmayı gerektirir ve
çalışan SmolVLA servisini riske atar.

## 2. Açık kararlar ve geçici varsayımlar

| ID | Karar | Geçici varsayım | Karar zamanı |
|---|---|---|---|
| A-001 | İlk işletim sistemleri | macOS + Linux önce; Windows Faz 0 spike sonrası | Faz 0.1 |
| A-002 | Public package adı | `hashtag-robotics` çalışma adı | Faz 0.1 |
| A-003 | UI kabı | Local HTTP + browser önce | Faz 0.1 |
| A-004 | Python sürümü | Python 3.12 | Faz 0.2 |
| A-005 | LeRobot seti | `0.6.x` doğrulama başlangıcı | Faz 0.2 |
| A-006 | Strands Robots | Uyumlu release/commit pinlenecek | Faz 0.2 |
| A-007 | İlk kamera backend'i | OpenCV/USB; RealSense feature pack | Faz 0.2 |
| A-008 | Fabrika profil formatı | İmzalı veya checksum'lı JSON manifest | Faz 0.1 |
| A-009 | Local secret store | OS keychain | Faz 0.3 |
| A-010 | Desktop packaging | Tauri/native installer daha sonra | Faz 5 |
| A-011 | Cloud hesabı | MVP için opsiyonel | Faz 0.1 |
| A-012 | Lisans | Açık kaynak + ticari katman modeli değerlendirilecek | Faz 0.1 |

Geçici varsayımlar onaylanmış karar değildir. İlgili spike veya ticari karar
sonrasında güncellenmelidir.

## 3. Risk değerlendirme ölçeği

- Olasılık: Düşük / Orta / Yüksek
- Etki: Düşük / Orta / Yüksek / Kritik
- Durum: Açık / Azaltılıyor / Kabul / Kapalı

## 4. Teknik ve ürün riskleri

| ID | Risk | Olasılık | Etki | Azaltma |
|---|---|---:|---:|---|
| R-001 | LeRobot ve Strands dependency conflict | Yüksek | Yüksek | Tested matrix, pin, lock ve contract test |
| R-002 | Upstream breaking calibration/schema değişikliği | Yüksek | Kritik | Adapter, artifact versioning, migration ve rollback |
| R-003 | Doküman ile yayımlanmış paket farkı | Yüksek | Yüksek | Runtime capability probe; docs-only özelliği kapat |
| R-004 | Yanlış leader/follower veya port eşleme | Orta | Kritik | Stable fingerprint, profile validation, explicit role |
| R-005 | Kamera index ve semantic key drift | Yüksek | Yüksek | Fingerprint + saved mapping + preflight |
| R-006 | İki job'ın aynı cihazı kullanması | Orta | Kritik | Transactional resource lease |
| R-007 | USB/network disconnect sırasında stale action | Orta | Kritik | Watchdog, heartbeat, stale action reject, safe stop |
| R-008 | Ajanın aşırı yetkili tool kullanması | Orta | Kritik | Dar tool registry, interventions, deterministic gateway |
| R-009 | Prompt injection ile privilege escalation | Orta | Kritik | Role permissions, backend re-validation, red-team test |
| R-010 | API/global state crash sonrası yanlış durum | Yüksek | Yüksek | Persisted job, worker heartbeat, recovery |
| R-011 | PyTorch/CUDA/MPS kurulum sorunları | Yüksek | Yüksek | Feature packs, doctor, clean-machine CI |
| R-012 | Büyük paket/uzun kurulum | Yüksek | Orta | Core ve training extras ayır |
| R-013 | Dataset overwrite veya bozulma | Orta | Kritik | Immutable revision, backup, atomic operation |
| R-014 | Eski policy ile yeni processor uyumsuzluğu | Yüksek | Yüksek | Policy manifest ve migration gate |
| R-015 | Remote inference latency/güvenlik | Orta | Kritik | TLS, auth, latency budget, local watchdog |
| R-016 | Sim başarısını real güvence sanmak | Orta | Yüksek | Sim/real profile ayrımı ve HIL gate |
| R-017 | Secret'ların log/trace'e düşmesi | Orta | Kritik | Redaction, keychain, diagnostics review |
| R-018 | LeLab fork'unun ürünü sınırlaması | Düşük | Yüksek | Referans al, bağımsız domain/control plane |
| R-019 | “Her şeyi V1'e koyma” kapsam büyümesi | Yüksek | Yüksek | Faz çıkış kriterleri ve SO-101 depth-first |
| R-020 | Browser kapanınca güvenlik kontrolü kaybı | Orta | Kritik | Safety worker browser'dan bağımsız |
| R-021 | Fiziksel collision veya kullanıcı yaralanması | Orta | Kritik | Preflight, limits, e-stop, safety copy, HIL QA |
| R-022 | Müşteri ortamlarında desteklenmeyen USB/sürücü | Yüksek | Orta | Device matrix, doctor, diagnostics, support bundle |
| R-023 | License/attribution ihlali | Düşük | Yüksek | Dependency/license inventory ve NOTICE |
| R-024 | Cloud kesintisinin local işi durdurması | Orta | Yüksek | Local-first ve offline mode |

## 5. Fiziksel güvenlik failure mode'ları

### 5.1 Robot yanlış profile çözülür

**Sonuç:** Yanlış calibration veya joint limit uygulanabilir.
**Önlem:** Serial/fingerprint uyuşmazlığında auto-connect değil blocked state.

### 5.2 Leader ve follower ters seçilir

**Sonuç:** Setup veya teleop yanlış cihazda çalışabilir.
**Önlem:** Role profile, cihaz metadata'sı ve kullanıcıya çözümlenmiş özet.

### 5.3 Kamera key'i değişir

**Sonuç:** Policy yanlış görüntüyü alır veya rollout başarısız olur.
**Önlem:** Semantik mapping, preview ve dataset/policy karşılaştırması.

### 5.4 Action shape veya unit farklıdır

**Sonuç:** Hatalı hareket veya limit aşımı.
**Önlem:** Processor ve feature contract doğrulanmadan rollout yok.

### 5.5 Kontrol loop'u gecikir

**Sonuç:** Jitter, action queue büyümesi ve kontrol kaybı.
**Önlem:** Latency budget, stale action rejection ve safe stop.

### 5.6 Uygulama veya worker çöker

**Sonuç:** Torque açık, lease kilitli veya job belirsiz kalabilir.
**Önlem:** Watchdog, heartbeat, process isolation ve startup recovery.

## 6. Security sınırları

Production ajanına verilmeyecek araçlar:

- Raw serial write
- Genel shell
- Arbitrary Python/import
- Geniş dynamic LeRobot bridge
- Doğrudan servo action stream
- Secret/credential read
- İzinli root dışına file write

Mutasyon ve fiziksel işlerde:

- User/session identity
- Role permission
- Typed command
- Resolved target
- Policy validation
- Resource lease
- Gerekli approval
- Audit event

zorunludur.

## 7. Lisans ve marka notları

LeRobot, LeLab ve Strands projelerinin lisans/NOTICE koşulları release öncesi
dependency inventory ile doğrulanmalıdır. Apache-2.0 kaynak kullanımı genellikle
ticari ürüne izin verse de:

- Copyright notice,
- lisans metni,
- NOTICE,
- yapılan değişikliklerin işaretlenmesi,
- upstream marka ve logolarının kullanım koşulları

ayrı ayrı ele alınmalıdır.

Bu doküman hukuk görüşü değildir.

## 8. Karar güncelleme yöntemi

Yeni önemli karar:

1. Bu dosyada yeni `K-xxx` kaydı açar.
2. Gerekçeyi ve reddedilen ana alternatifi yazar.
3. Mimari veya roadmap etkisini ilgili dosyada günceller.
4. Version/compatibility etkisini kaydeder.
5. Fiziksel güvenlik etkisi varsa ayrı risk veya failure mode ekler.

Bir geçici varsayım kesinleştiğinde ilgili `A-xxx` satırı kaldırılmaz; karar
referansına dönüştürülür. Böylece ürün yönünün neden değiştiği izlenebilir.
