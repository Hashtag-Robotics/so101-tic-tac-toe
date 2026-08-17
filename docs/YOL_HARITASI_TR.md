# Hashtag Robotics SO-101 Platformu — Faz Bazlı Yol Haritası

**Durum:** Software-only baseline bütün fazlarda uygulandı; HIL ve production
doğrulamaları devam ediyor
**Kapsam yaklaşımı:** SO-101 depth-first, safety-first, local-first
**Zaman tahmini:** Bu dokümanda kasıtlı olarak verilmemiştir; Faz 0 teknik
spike'ları ve desteklenecek işletim sistemleri kesinleştikten sonra yapılacaktır.

## Uygulama notu — 23 Temmuz 2026

Bu roadmap'in bütün fazları için çalışan bir ilk dikey dilim oluşturuldu:

- Faz 0 control plane, jobs, leases, safety, doctor ve package
- Faz 1 safe robot workflow ve LeRobot physical command adapter
- Faz 2 dataset/training/policy/evaluation lifecycle
- Faz 3 deterministic agent gateway ve optional Strands planner
- Faz 4 MuJoCo contract sim ve remote inference preflight
- Faz 5 wheel, diagnostics, local fleet ve HIL hazırlığı

Bu, production-ready veya physical-validated anlamına gelmez. Gerçek durum ve
bekleyen doğrulamalar [Uygulama Durumu](UYGULAMA_DURUMU_TR.md) ve
[HIL Test Planı](HIL_TEST_PLANI_TR.md) içinde tutulur.

## 1. Roadmap prensipleri

- Her faz bağımsız bir demo değil, sonraki fazın güvenilir temelidir.
- Gerçek robot hareketi gözlem, doğrulama ve safety katmanından sonra açılır.
- Upstream özellikleri destekleniyor saymak için kurulu yüzey ve contract testi
  gerekir.
- UI ekranı tamamlanmış olsa da backend state/recovery eksikse özellik
  tamamlanmış sayılmaz.
- Simülasyon testi gerçek donanım testinin yerine geçmez; gerçek donanım testi
  de unit/contract testinin yerine geçmez.
- Ajanlar önce read-only, sonra hazırlık, en son onaylı fiziksel aksiyon
  yetkisi alır.
- Her fazın çıkış kriteri karşılanmadan bir sonraki faz ürün kapsamına girmez.

## 2. Fazların genel görünümü

| Faz | Odak | Ana sonuç |
|---|---|---|
| Faz 0 | Temel ve uyumluluk | Çalışan iskelet, version matrix, domain/safety contract |
| Faz 1 | Robot Lab | Kurulum, discovery, calibration, kamera, teleop, record, replay |
| Faz 2 | Data ve Policy | Dataset Studio, training, policy registry, evaluation |
| Faz 3 | Strands Agents | Read-only ajanlardan onaylı robot workflow'larına geçiş |
| Faz 4 | Simulation ve Remote | MuJoCo, sim-first evaluation, async/remote inference |
| Faz 5 | Ürünleştirme ve Fleet | Installer, update, support, fleet, cloud/ROS genişlemesi |

Bağımlılık:

```text
Faz 0
  └─ Faz 1
       └─ Faz 2
            ├─ Faz 3
            └─ Faz 4
                 └─ Faz 5
```

Faz 3'ün read-only ajan kısmı Faz 1 sonlarında başlayabilir; fakat fiziksel
ajan aksiyonları Faz 1 safety ve Faz 2 policy compatibility tamamlanmadan
açılamaz.

---

# Faz 0 — Temel, sürüm matrisi ve mimari iskelet

## Amaç

Ürünün upstream sürüm değişiklikleri altında kontrolsüz dağılmasını önleyecek
teknik temeli oluşturmak.

## 0.1 Ürün ve platform kararları

### İşler

- İlk desteklenecek işletim sistemlerini seç.
- İlk Hashtag SO-101 SKU/hardware revision tanımını çıkar.
- Python ve package adını kesinleştir.
- Local web app ile desktop shell arasındaki ilk dağıtım şeklini seç.
- İlk kamera backend'lerini seç.
- Hub hesabı olmadan çalışması gereken minimum yüzeyi sabitle.
- Lisans ve upstream attribution politikasını yaz.

### Çıktılar

- Onaylanmış product scope
- Destek matrisi taslağı
- İlk SKU manifest örneği
- Package/repository naming kararı

## 0.2 Upstream compatibility laboratuvarı

### İşler

- LeRobot `0.6.x` temiz environment kurulumu.
- Strands Agents kararlı sürüm kurulumu.
- Strands Robots PyPI ve doğrulanmış `main`/release adayını karşılaştır.
- Python, Torch, ffmpeg, OpenCV ve Feetech dependency'lerini çıkar.
- macOS/Linux ve seçilirse Windows kurulum spike'ı.
- Import/capability probe script'i.
- Port, camera ve policy surface contract testleri.

### Doğrulanacak kombinasyon

```text
Python
LeRobot
Strands Agents
Strands Robots
Torch
OS/architecture
accelerator
camera backend
```

### Çıktılar

- `compatibility.json` veya eşdeğer makine-okunur manifest
- Stable ve preview sürüm seti
- Bilinen conflict listesi
- Kurulum ve rollback prosedürü

## 0.3 Uygulama iskeleti

### İşler

- Python package iskeleti.
- FastAPI application factory.
- React/TypeScript/Vite frontend iskeleti.
- Frontend build'ini wheel'e gömme.
- CLI entrypoint.
- Yerel server startup/shutdown.
- Tek instance lock.
- SQLite ve migration altyapısı.
- Yapılandırılmış log.
- Health endpoint.

### Minimum kullanıcı akışı

```text
package kur
  → komutu çalıştır
  → local server başlasın
  → browser açılsın
  → system status görülsün
  → güvenli kapatma yapılsın
```

## 0.4 Domain contract'ları

### İşler

İlk Pydantic/domain modelleri:

- Device
- RobotProfile
- TeleoperatorProfile
- CameraProfile
- CalibrationArtifact
- DatasetManifest
- PolicyManifest
- Job
- ResourceLease
- Approval
- CapabilityManifest
- AuditEvent

State transition ve validation hataları string yerine kodlanmış hata tipleri
olmalıdır.

## 0.5 Job ve resource altyapısı

### İşler

- Persisted job repository.
- Job state machine.
- Resource lease transaction'ları.
- Worker heartbeat.
- Cancel/abort ayrımı.
- Crash recovery.
- Process output ve structured progress.
- Correlation ID.

İlk sahte job ile uzun işlem ve restart recovery test edilmelidir.

## 0.6 Safety çekirdeği

### İşler

- Read-only, sim ve real target ayrımı.
- Command validation pipeline.
- Approval token modeli.
- Preflight result modeli.
- Joint/action limit policy contract'ı.
- Watchdog interface'i.
- Emergency stop interface'i.
- Secret redaction.
- Audit trail.

Gerçek hareket henüz açılmayabilir; fakat daha sonraki fiziksel job'lar bu
çekirdeği atlayamayacak şekilde tasarlanmalıdır.

## Faz 0 kapsam dışı

- Tam calibration UI
- Gerçek teleop
- Dataset recording
- Training
- Agent chat
- MuJoCo
- Fleet/cloud

## Faz 0 çıkış kriterleri

- Temiz makinede dokümante edilmiş kurulum çalışır.
- Uygulama browser'da açılır ve kontrollü kapanır.
- Doctor gerçek kurulu sürümleri ve eksikleri raporlar.
- Capability manifest üretilebilir.
- SQLite migration, job lifecycle ve resource lease testleri geçer.
- Restart sonrası yarım job güvenli duruma alınır.
- Safety ve approval contract'ları testlidir.
- LeRobot/Strands sürüm seti pinlenmiş ve açıklanmıştır.

---

# Faz 1 — Güvenli Robot Lab

## Amaç

Kullanıcıya SO-101'i kurma, doğrulama, teleop etme ve dataset kaydetme
işlemlerini güvenli bir yerel ürün içinde sunmak.

## 1.1 Setup ve Doctor

### Özellikler

- OS ve architecture
- Python/runtime
- LeRobot/Strands/Torch sürümleri
- ffmpeg
- Serial erişim izinleri
- GPU/MPS/CUDA
- Kamera backend'leri
- Disk alanı
- Hub bağlantısı, fakat token göstermeden
- Capability ve incompatibility raporu
- Redacted diagnostics export

### Kabul kriterleri

- Her kontrol `pass`, `warning`, `blocked` veya `not_applicable` verir.
- Hata sadece log değil, uygulanabilir çözüm gösterir.
- Doctor hiçbir motor hareketi yapmaz.

## 1.2 Device Inventory

### Özellikler

- Serial port discovery
- Kamera discovery
- Leader/follower adaylarının listelenmesi
- Stable fingerprint
- Connect/disconnect event'leri
- Read-only joint/state kontrolü
- Hashtag Robot Profile oluşturma/eşleme
- Manuel role override, açık uyarıyla

### Kabul kriterleri

- Birden fazla serial cihaz ayırt edilir.
- Yeniden takılan cihaz mümkünse aynı profile çözülür.
- Belirsiz cihaz otomatik follower kabul edilmez.
- Discovery hiçbir actuation yapmaz.

## 1.3 Motor setup ve calibration wizard

### Özellikler

- Motor setup ön kontrolü
- Leader ve follower için ayrı wizard
- Orta konum ve range adımları
- Calibration backup
- Fabrika ve kullanıcı calibration revision'ları
- Checksum ve validation
- Yanlış role/profile uyarısı
- Calibration restore

### Kabul kriterleri

- Var olan calibration sessizce overwrite edilmez.
- Her değişiklikten önce backup oluşur.
- Calibration sonucu profile ve cihaz fingerprint'e bağlıdır.
- Başarısız calibration sonrası önceki geçerli revision korunur.
- Hareketli adımlar açık fiziksel uyarı ve onay gerektirir.

## 1.4 Camera Studio

### Özellikler

- OpenCV/USB kamera discovery
- Preview
- Backend, resolution ve FPS seçimi
- Semantik isim: `front`, `wrist`, `top`
- Orientation/crop ayarı
- FPS, latency ve dropped frame ölçümü
- Profile'a mapping kaydetme
- Aynı kamerayı iki role atama uyarısı
- No-camera workflow

### Kabul kriterleri

- Kamera device index'i değil stable mapping saklanır.
- Reconnect sonrası mapping doğrulanır.
- Gerçek FPS istenen FPS'ten ayrı gösterilir.
- Preview kapatıldığında kaynak release edilir.
- Dataset feature adı kullanıcıya açıkça gösterilir.

## 1.5 Teleoperation

### Özellikler

- Leader → follower teleop
- Kamera görünümü opsiyonel
- Joint state ve action grafiği
- Control FPS ve latency
- Relative target limit
- Süre sınırı
- Başlatma preflight'ı
- Deadman/watchdog
- Stop ve emergency stop
- Disconnect handling

### Kabul kriterleri

- Teleop, robot ve leader exclusive lease almadan başlayamaz.
- Port/calibration/profile uyuşmazlığı başlangıcı engeller.
- Kamera arızası camera-required değilse teleop'u güvenli şekilde sürdürebilir.
- Leader veya follower disconnect'inde action gönderimi durur.
- Emergency stop browser bağlantısından bağımsız çalışır.
- Audit'te başlangıç, onay, stop nedeni ve metrikler bulunur.

## 1.6 Dataset recording

### Özellikler

- Dataset adı/repo ID
- Task açıklaması
- Episode count
- Episode süresi
- Reset süresi
- Kamera ve feature özeti
- Start/save/retry/abort
- Episode progress
- Disk alanı kontrolü
- Kayıt sonrası temel integrity validation
- Local-only ve Hub upload ayrımı

### Kabul kriterleri

- Recording teleop ve kamera kaynaklarını tek job altında yönetir.
- Dataset FPS ve control loop uyumu doğrulanır.
- Retry, yarım episode'u geçerli episode olarak saymaz.
- Abort mevcut tamamlanmış episode'ları bozmaz.
- Upload başarısızlığı yerel dataset'i kaybettirmez.
- Manifest, robot/calibration/camera mapping provenance'ını taşır.

## 1.7 Replay

### Özellikler

- Dataset/episode seçimi
- Action shape ve robot profile validation
- Süre ve limit özeti
- Real replay approval
- Stop/e-stop
- Sonuç ve hata raporu

### Kabul kriterleri

- Uyumsuz feature/action shape replay'i engeller.
- Replay başlamadan episode ve hedef robot açıkça gösterilir.
- Eski veya bilinmeyen calibration ile replay blocked olur.

## Faz 1 kapsam dışı

- Tam training UI
- Serbest policy rollout
- Gerçek robotu yöneten agent
- Multi-robot fleet
- ROS 2
- Isaac/Newton

## Faz 1 çıkış kriterleri

- Hashtag'in doğrulanmış bir leader/follower setinde uçtan uca akış çalışır:

```text
install
  → doctor
  → discover
  → profile
  → calibrate
  → camera map
  → teleop
  → record
  → validate
  → replay
```

- USB disconnect, kamera kaybı ve uygulama kapanması test edilmiştir.
- No-camera teleop ve recording dışı akış çalışır.
- Fiziksel hareketlerin tamamı approval ve audit üretir.
- Son kullanıcıya uygun diagnostics bundle üretilebilir.

---

# Faz 2 — Dataset, training ve policy yaşam döngüsü

## Amaç

Toplanan veriyi doğrulamak, eğitmek, policy'yi kayıt altına almak ve güvenli
şekilde değerlendirmek.

## 2.1 Dataset Studio

### Özellikler

- Dataset listesi ve manifest
- Episode/video önizleme
- Feature schema
- İstatistikler
- Dataset integrity
- Delete/split/merge
- Episode annotation
- Feature ekleme/kaldırma
- Re-encode
- Local ↔ Hub sync
- Dataset version/provenance

### Kabul kriterleri

- Mutasyon öncesi geri alınabilir revision veya backup vardır.
- İşlemler büyük datasette API process'ini bloke etmez.
- Hub ve local state ayrı gösterilir.
- Dataset değişince bağlı policy compatibility yeniden hesaplanır.

## 2.2 Training Studio

### Özellikler

- Capability tabanlı policy kataloğu
- Hashtag tarafından doğrulanmış preset'ler
- Dataset/policy compatibility preflight
- Local CPU/MPS/CUDA
- Hugging Face Jobs
- Training parametreleri
- Resume
- Log ve metric stream
- Checkpoint listesi
- W&B opsiyonel entegrasyonu
- Disk/VRAM tahmini

### Kabul kriterleri

- Desteklenmeyen policy UI'da çalışabilir gösterilmez.
- Training argümanları typed config'ten üretilir.
- Credential log'a düşmez.
- Cancel checkpoint/artifact durumunu açık gösterir.
- Uzak job bağlantısı kesilse de job identity kaybolmaz.

## 2.3 Policy Registry

### Özellikler

- Local ve Hub policy'ler
- Policy type
- Kaynak dataset
- Processor chain
- Expected features
- Kamera mapping
- Action shape
- Training runtime
- Checkpoint metadata
- Evaluation history
- Compatibility sonucu

### Kabul kriterleri

- Checkpoint yalnız path olarak tutulmaz; manifest oluşturulur.
- Kaynağı bilinmeyen policy `unverified` olur.
- Policy ve robot schema farkları görünür ve kodlanmış hata üretir.

## 2.4 Evaluation ve rollout

### Özellikler

- Önce sim/read-only compatibility
- Gerçek rollout preflight
- Kamera preview
- Control/inference latency
- Action queue
- Süre ve episode sayısı
- Manual success/failure annotation
- Video ve telemetry
- Result distribution

### Kabul kriterleri

- Dataset toplama kamera config'i ile rollout config'i karşılaştırılır.
- Processor/normalization bilgisi eksikse rollout engellenir.
- Gerçek rollout exclusive lease ve explicit confirmation gerektirir.
- Disconnect/timeout safe-stop ile sonuçlanır.
- Rapor yalnız ortalama değil, episode bazlı sonuç dağılımı verir.

## Faz 2 kapsam dışı

- Ajanın onaysız eğitim veya rollout yapması
- Otomatik policy deployment
- Çok robotlu production fleet
- Genel amaçlı cloud orchestration

## Faz 2 çıkış kriterleri

- Uçtan uca akış:

```text
dataset
  → validate
  → train local veya HF Jobs
  → checkpoint register
  → compatibility
  → evaluation
  → result report
```

- En az bir klasik policy ve bir VLA/policy ailesi capability tabanlı denenmiştir.
- MPS/CUDA/CPU destek iddiaları gerçek test sonucu ile etiketlenmiştir.
- Dataset/policy migration ve version mismatch senaryoları testlidir.

---

# Faz 3 — Strands Agent Studio

## Amaç

Kullanıcıya doğal dille çalışan fakat deterministic ürün sınırları içinde kalan
robot ajanları sunmak.

## 3.1 Agent runtime ve session

### Özellikler

- Model provider seçimi
- Yerel ve cloud model ayarları
- Session persistence
- Tool registry
- Permission profile
- Structured output
- OpenTelemetry
- Agent/job correlation

## 3.2 Read-only ajanlar

İlk ajanlar:

- Lab Assistant
- Dataset Curator
- Training Advisor
- Evaluation Analyst

Bu ajanlar cihazı veya artifact'i değiştirmeden önce analiz ve öneri üretir.

### Kabul kriterleri

- Tool listesi ajan rolüne göre daraltılır.
- Read-only rol mutation command oluşturamaz.
- Secret ve büyük kamera payload'ları modele kontrolsüz verilmez.
- Her tool call trace ve audit ile ilişkilidir.

## 3.3 Deterministic workflow'lar

Graph/Workflow örnekleri:

```text
Prepare Dataset
  → inspect
  → validate
  → quality report
  → user decision
```

```text
Prepare Training
  → inspect dataset
  → list compatible policies
  → estimate resources
  → generate typed config
  → user confirmation
  → queue job
```

## 3.4 Gated Robot Operator

Robot Operator yalnız yüksek seviye command oluşturabilir:

- Prepare teleop
- Prepare recording
- Request calibration
- Request real rollout
- Stop robot

### Kabul kriterleri

- Ajan raw serial, shell veya robot instance görmez.
- Agent `confirm` üretse bile UI/human approval yerine geçmez.
- Command parametreleri backend tarafından yeniden resolve edilir.
- Prompt injection testi tool privilege escalation'a yol açmaz.
- Stop/E-stop ajan runtime'ından bağımsızdır.

## Faz 3 kapsam dışı

- LLM'in servo loop çalıştırması
- Serbest swarm ile gerçek donanım yönetimi
- Kullanıcı onayı olmadan real actuation
- Ajanın kendi tool permission'ını değiştirmesi

## Faz 3 çıkış kriterleri

- En az dört uzman ajan read-only olarak çalışır.
- Training workflow typed config ve confirmation ile job oluşturur.
- Robot Operator hiçbir deterministic gate'i atlayamaz.
- Prompt injection, tool spoofing ve stale approval testleri geçer.
- Ajan trace'i ile robot/job audit'i uçtan uca ilişkilendirilebilir.

---

# Faz 4 — Simülasyon, policy değerlendirme ve remote inference

## Amaç

Gerçek robot riskini azaltacak sim-first geliştirme ve güçlü GPU'yu uzaktan
kullanma kabiliyeti eklemek.

## 4.1 MuJoCo başlangıcı

### Özellikler

- SO-101 sim profile
- Scene/object setup
- Camera mapping
- Teleop in simulation
- Synthetic recording
- Policy rollout
- Video ve telemetry
- Domain randomization için temel contract

### Kabul kriterleri

- Sim feature'ları gerçek dataset feature'larıyla açık adapter üzerinden eşlenir.
- Sim ve real profile hiçbir zaman aynı identity olarak kullanılmaz.
- Sim başarısı gerçek deployment garantisi olarak gösterilmez.

## 4.2 Sim-first agent workflow

- Ajan planını önce sim ortamında çalıştırma
- Constraint ve collision sonucu
- Başarısız adım analizi
- Gerçek robota taşımadan önce compatibility gate

## 4.3 Remote/async inference

### Özellikler

- Yerel policy server
- Ağdaki GPU workstation
- Authentication ve TLS
- Heartbeat ve latency
- Action queue/smoothing
- Timeout ve fallback
- Client/server version compatibility

### Kabul kriterleri

- Stale action uygulanmaz.
- Ağ kesintisi safe-stop üretir.
- Inference server kimliği ve policy manifest doğrulanır.
- Public internet erişimi varsayılan kapalıdır.

## 4.4 İleri sim backend'leri

Newton, Isaac veya başka backend'ler yalnız:

- kurulum maliyeti,
- lisans,
- platform desteği,
- gerçek ürün ihtiyacı

doğrulandıktan sonra capability pack olarak eklenir.

## Faz 4 çıkış kriterleri

- Aynı policy manifest sim ve real compatibility raporundan geçebilir.
- MuJoCo'da tekrarlanabilir evaluation raporu üretilir.
- Remote inference disconnect ve latency testleri güvenli sonuçlanır.
- Sim-to-real belirsizlikleri UI'da açıkça gösterilir.

---

# Faz 5 — Ticari ürün, fleet ve genişleme

## Amaç

Laboratuvar uygulamasını Hashtag Robotics müşterilerine dağıtılabilir,
güncellenebilir ve desteklenebilir ürüne çevirmek.

## 5.1 Son kullanıcı installer'ları

- PyPI/uv canonical release
- macOS installer
- Windows installer, destek kararı verilirse
- Linux package/AppImage
- Code signing/notarization
- Offline install bundle ihtiyacı

## 5.2 Update ve migration

- Stable/preview channel
- Uygulama update
- Dependency environment migration
- DB migration
- Calibration/dataset compatibility
- Rollback
- Release notes ve breaking change bildirimi

## 5.3 Support ve QA

- Hashtag SKU/profile registry
- Fabrika calibration provisioning
- QR/seri numarası onboarding
- Redacted diagnostics bundle
- Remote support, açık kullanıcı izniyle
- Warranty/QA history
- Assembly ve test checklist bağlantısı

## 5.4 Fleet ve cloud

İhtiyaç doğrulanırsa:

- Kullanıcı/organizasyon
- Robot ownership
- Dataset/model senkronizasyonu
- Fleet health
- Uzak training job broker
- Policy release channel
- Audit retention

Cloud, yerel safety loop'un sahibi olmaz.

## 5.5 ROS 2, mesh ve B2B API

- ROS 2 bridge
- Strands robot mesh
- MCP veya kurumsal tool gateway
- B2B API
- Çok robotlu job scheduling

Bu yüzeyler ilk SO-101 kullanıcı akışı olgunlaşmadan ürüne eklenmez.

## Faz 5 çıkış kriterleri

- Temiz son kullanıcı makinesinde installer çalışır.
- Update ve rollback calibration/dataset kaybettirmez.
- Support bundle secret içermediği test edilmiştir.
- SKU onboarding ve fabrika QA akışı dokümante edilmiştir.
- Cloud kesintisinde local safety ve temel robot işlemleri devam eder.

---

# 3. İlk uygulama backlog'u

Faz 0 başladığında önerilen ilk iş sırası:

1. `ADR-001`: Local-first Python control plane.
2. `ADR-002`: Desteklenen ilk OS ve package yöntemi.
3. LeRobot/Strands temiz environment spike.
4. Compatibility probe.
5. Monorepo/package dizin iskeleti.
6. FastAPI health ve React shell.
7. Wheel içine frontend build.
8. SQLite migration.
9. Domain model taslağı.
10. Job state machine.
11. Resource lease.
12. Doctor command.
13. Safety command/approval contract.
14. CI: lint, typecheck, unit ve clean-install test.

# 4. Definition of Done

Bir özellik yalnızca şu koşullarda tamamlanmış sayılır:

- Kullanıcı akışı UI'da çalışır.
- Backend state ve hata kodları tanımlıdır.
- Resource ownership tanımlıdır.
- Cancel, timeout ve crash davranışı testlidir.
- Safety etkisi değerlendirilmiştir.
- Audit ve telemetry üretir.
- Secret redaction uygulanmıştır.
- En az unit/contract testi vardır.
- Gerekliyse gerçek donanım testinden geçmiştir.
- Dokümantasyon ve diagnostics çıktısı günceldir.
- Desteklenen version/capability bilgisi açıktır.

# 5. Başarı ölçütleri

Ürün ilerledikçe yalnız feature sayısı değil şu metrikler izlenmelidir:

- İlk kurulum başarı oranı
- Robot discovery süresi
- Calibration başarı/tekrar oranı
- Teleop loop FPS, p50/p95 latency ve disconnect sayısı
- Kamera dropped frame oranı
- Başarılı dataset episode oranı
- Dataset validation hata dağılımı
- Training completion/failure dağılımı
- Rollout başarı dağılımı
- Safety block ve emergency stop nedenleri
- Agent tool deny/confirm dağılımı
- Diagnostics ile çözülebilen support vakası oranı

Bu metrikler müşteri telemetry'si olarak toplanacaksa açık izin, gizlilik
politikası ve local-only seçeneği gerekir.
