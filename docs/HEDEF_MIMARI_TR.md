# Hashtag Robotics SO-101 Platformu — Hedef Mimari

**Durum:** Önerilen hedef mimari
**Kapsam:** İlk ürün SO-101 leader/follower setleri
**Mimari yaklaşım:** Local-first, Python runtime, browser UI, deterministic safety

## 1. Mimari hedef

Platform, kullanıcının SO-101 robotunu ve kameralarını bilgisayara bağladıktan
sonra bütün temel robot yaşam döngüsünü tek arayüzden yönetmesini sağlamalıdır:

```text
kurulum
  → keşif
  → motor setup
  → kalibrasyon
  → kamera eşleme
  → teleoperation
  → dataset
  → eğitim
  → evaluation
  → güvenli ajan workflow'ları
```

Mimari, hızlı demo üretmek yerine şu ürün garantilerine göre kurulmalıdır:

- Bir fiziksel kaynak aynı anda yalnızca bir aktif iş tarafından kullanılır.
- Uzun işler API process'i yeniden başlasa bile izlenebilir.
- Gerçek hareket, çözümlenmiş robot ve açık kullanıcı onayı olmadan başlamaz.
- LLM kararları deterministic doğrulamalardan geçer.
- LeRobot veya Strands değişiklikleri ürünün tamamına yayılmaz.
- Kurulu gerçek capability, UI'nın göstereceği yüzeyi belirler.
- Dataset, policy ve robot schema uyumsuzluğu rollout'u engeller.

## 2. Mimari ilkeler

### 2.1 Local-first

Robot kontrol loop'u, kamera erişimi ve güvenlik mekanizması robotun bağlı olduğu
bilgisayarda çalışır. İnternet veya bulut bağlantısı temel teleop ve emergency
stop için zorunlu değildir.

### 2.2 Python ana runtime

LeRobot, Strands Robots, Strands Agents, PyTorch ve donanım sürücülerinin ana
ekosistemi Python'dur. Bu nedenle ürünün canonical runtime'ı Python olacaktır.

Frontend TypeScript/React olabilir; fakat robot süreçlerinin sahibi Node.js veya
browser olmayacaktır.

### 2.3 Adapter sınırı

Ürün domain'i doğrudan çok sayıda LeRobot internal class'ına bağlanmayacaktır:

```text
Product Services
    ↓
Stable Hashtag Contracts
    ↓
LeRobot / Strands Adapters
    ↓
Pinned upstream versions
```

### 2.4 Deterministic guarantees

LLM:

- Plan yapabilir.
- Kullanıcı niyetini yapılandırabilir.
- Dataset ve training sonuçlarını yorumlayabilir.
- Doğrulanmış üst seviye komut talep edebilir.

LLM:

- Joint limit garantisi veremez.
- Calibration uyumunu tek başına belirleyemez.
- Resource lock sahibi olamaz.
- Emergency stop'u engelleyemez.
- Servo frekansında action üretmemelidir.

### 2.5 Capability-driven UI

UI policy, kamera backend'i veya simülasyon özelliğini hardcode ederek
göstermemelidir. Backend, kurulu ortam ve contract testlerinden bir capability
manifest üretmelidir.

## 3. Üst seviye bileşenler

```text
┌─────────────────────────────────────────────────────────────┐
│                     React Dashboard                         │
│ Setup · Devices · Cameras · Teleop · Data · Train · Agents │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST + WebSocket
┌───────────────────────────▼─────────────────────────────────┐
│               Hashtag Local Control Plane                  │
│ API · Profiles · Jobs · Leases · Audit · Compatibility    │
└──────────────┬─────────────────────┬────────────────────────┘
               │                     │
┌──────────────▼─────────────┐  ┌────▼───────────────────────┐
│ Deterministic Safety       │  │ Strands Agent Runtime     │
│ Policy + Command Gateway   │◄─┤ Sessions · Tools · Graphs │
└──────────────┬─────────────┘  └────────────────────────────┘
               │
┌──────────────▼─────────────────────────────────────────────┐
│                     Adapter Layer                          │
│ LeRobot · Strands Robots · Sim · HF Jobs · Remote Policy │
└──────┬─────────────────┬──────────────────┬────────────────┘
       │                 │                  │
  Robot/Teleop        Camera            Training/Policy
       │                 │                  │
┌──────▼─────────────────▼──────────────────▼────────────────┐
│ SO-101 · Leader · Feetech · USB/RealSense · CPU/MPS/CUDA │
└────────────────────────────────────────────────────────────┘
```

## 4. Çalışan process modeli

Tek process ve modül global state yaklaşımı kullanılmamalıdır.

Önerilen process'ler:

| Process | Sorumluluk |
|---|---|
| `hashtag-server` | API, UI, metadata, authentication, job coordination |
| `hardware-worker` | Robot, teleoperator ve kamera sahipliği |
| `training-worker` | Uzun training/evaluation subprocess'leri |
| `agent-worker` | Strands session ve tool çağrıları |
| Opsiyonel `sim-worker` | MuJoCo/simülasyon süreçleri |

İlk MVP'de bunların tamamı ayrı servis olmak zorunda değildir. Ancak
process/thread sınırları domain contract'larında baştan ayrılmalı; robot loop'u
API event loop'unu bloke etmemelidir.

Uzun operasyonlar:

- Shell string birleştirerek çalıştırılmaz.
- Argüman listesi veya doğrudan typed adapter kullanır.
- PID/process metadata'sı kaydedilir.
- stdout/stderr yapılandırılmış log'a yönlendirilir.
- Cancel ve timeout davranışı tanımlıdır.
- Uygulama yeniden açıldığında yarım kalan iş `unknown` bırakılmaz.

## 5. Temel domain contract'ları

### 5.1 Device

Fiziksel veya sanal bir erişim noktasını temsil eder:

```text
Device
├── id
├── kind: serial | camera | gpu | simulator
├── stable_fingerprint
├── transient_path
├── vendor/product metadata
├── capabilities
├── health
└── last_seen_at
```

`/dev/tty.usbmodem...` gibi geçici yol kimlik olarak kullanılmamalıdır. Mümkün
olduğunda VID/PID, serial, kamera metadata'sı ve kullanıcı eşlemesi birlikte
kullanılmalıdır.

### 5.2 RobotProfile

Bir follower veya sim robotunun çözümlenmiş ürün profilidir:

```text
RobotProfile
├── id
├── product_sku
├── robot_type
├── serial_number
├── hardware_revision
├── motor_layout
├── calibration_revision
├── camera_mapping
├── safety_profile
├── supported_features
└── compatibility_channel
```

### 5.3 TeleoperatorProfile

Leader kol veya başka teleop cihazını temsil eder:

```text
TeleoperatorProfile
├── id
├── type
├── serial_number
├── calibration_revision
├── target_robot_types
└── feature_mapping
```

### 5.4 CameraProfile

Fiziksel kamerayı semantik dataset anahtarına bağlar:

```text
CameraProfile
├── device_fingerprint
├── backend
├── semantic_name: front | wrist | top
├── width
├── height
├── fps
├── color/depth modes
├── orientation
└── latency baseline
```

### 5.5 CalibrationArtifact

Kalibrasyon mutable bir dosya değil, sürümlenmiş artifact olmalıdır:

```text
CalibrationArtifact
├── id
├── target_profile
├── source
├── schema_version
├── checksum
├── created_at
├── supersedes
└── validation_result
```

Fabrika calibration'ı, kullanıcı calibration'ı ve backup açıkça ayrılmalıdır.

### 5.6 DatasetManifest

```text
DatasetManifest
├── repo_id / local_path
├── task
├── robot_profile_id
├── teleoperator_profile_id
├── calibration_revision
├── features
├── camera_mapping
├── fps
├── episode statistics
├── integrity status
└── provenance
```

### 5.7 PolicyManifest

```text
PolicyManifest
├── policy_type
├── checkpoint
├── source_dataset
├── expected_features
├── processor_chain
├── action_shape
├── camera_mapping
├── training runtime
├── evaluation summary
└── compatibility status
```

### 5.8 Job

Her uzun işlem kalıcı bir Job'dır:

```text
Job
├── id
├── kind
├── state
├── requested_by
├── resolved_targets
├── parameters
├── resource_leases
├── process metadata
├── progress
├── result
├── error
└── audit correlation id
```

## 6. Job state machine

Ortak temel durumlar:

```text
created
  → validating
  → blocked
  → awaiting_confirmation
  → queued
  → starting
  → running
  → stopping
  → completed
  → failed
  → aborted
  → interrupted
```

Kurallar:

- `interrupted`, uygulama yeniden başladığında yarım kalan işin aldığı durumdur;
  lease'leri bırakılır ve süreç grubu temizlenir.
- `blocked`, eksik veya uyumsuz koşulu açık bir kodla taşır.
- Fiziksel actuation işi confirmation olmadan `queued` olamaz.
- Job yeniden başlatıldığında önce eski lease ve process doğrulanır.
- `completed`, yalnızca artifact ve sonuç doğrulandıktan sonra verilir.
- Cancel ile emergency stop aynı şey değildir.
- Emergency stop her state'ten güvenli stop'a gidebilir.

Job türleri:

- `hardware_discovery`
- `motor_setup`
- `calibration`
- `camera_preview`
- `teleoperation`
- `recording`
- `replay`
- `dataset_validate`
- `dataset_transform`
- `training`
- `evaluation`
- `policy_rollout`
- `simulation`
- `remote_inference_probe`
- `hub_sync`
- `diagnostics`

## 7. Resource Lease Manager

Bir iş başlamadan gerekli kaynakları atomik olarak kiralamalıdır:

```text
ResourceLease
├── resource_id
├── resource_type
├── owner_job_id
├── mode: shared_read | exclusive
├── acquired_at
├── heartbeat_at
└── expires_at
```

Örnek:

```text
teleoperation job
├── follower serial port: exclusive
├── leader serial port: exclusive
├── front camera: shared/exclusive policy'ye göre
└── hardware worker: exclusive session
```

Calibration sürerken teleop; recording sürerken ikinci recording; training
output dizini yazılırken aynı output'a başka training başlatılamaz.

Lease heartbeat kaybolduğunda fiziksel kaynak için safe-stop ve manual review
uygulanmalıdır.

## 8. Safety Gateway

Safety Gateway, bütün gerçek robot komutlarının geçtiği deterministic sınırdır.

### 8.1 Preflight kontrolleri

- Hedef gerçek mi sim mi?
- Robot profile çözümlendi mi?
- Leader/follower rolleri doğru mu?
- Portlar ve device fingerprint eşleşiyor mu?
- Calibration mevcut, doğrulanmış ve doğru revision mı?
- Joint/action dimension doğru mu?
- Unit ve coordinate convention biliniyor mu?
- Joint limit ve `max_relative_target` tanımlı mı?
- Kamera anahtarları policy/dataset ile eşleşiyor mu?
- Control FPS ve policy horizon uyumlu mu?
- Power/torque durumu biliniyor mu?
- Fiziksel çalışma alanı kullanıcı tarafından onaylandı mı?
- E-stop ve watchdog aktif mi?
- Aynı kaynak başka job tarafından tutuluyor mu?

### 8.2 Çalışma zamanı kontrolleri

- Heartbeat
- Loop latency ve jitter
- Stale action rejection
- Relative action clipping
- Absolute joint limit
- Maximum job duration
- Camera frame age
- Queue depth
- Policy inference timeout
- Disconnect detection
- Manual stop
- Emergency stop

### 8.3 Approval modeli

Gerçek hareket öncesi UI şunları göstermelidir:

```text
Robot: çözümlenmiş follower
Teleoperator/policy: kaynak
Calibration revision
Kameralar
Control frequency
Joint/action limit profili
Tahmini süre
Fiziksel risk özeti
Stop yöntemi
```

Onay bir model cevabı veya chat metni değil, backend tarafından üretilen
tek-kullanımlık bir approval token olmalıdır. Token:

- Belirli job ID'ye,
- belirli hedef profil ve parametre hash'ine,
- kısa bir son kullanma süresine

bağlanmalıdır.

### 8.4 Emergency stop

Emergency stop:

- Agent izninden bağımsızdır.
- UI yanında klavye/hardware yolu da desteklemelidir.
- Ağ veya browser bağlantısı kesilse de yerel worker'da işler.
- Audit'e kaydedilir ama log yazımı stop'u geciktirmez.

## 9. Agent Command Gateway

Strands ajanı yalnızca Hashtag tool registry içindeki dar tool'ları görür.

Önerilen ilk tool sınıfları:

### Read-only

```text
list_devices
inspect_robot
inspect_calibration
inspect_cameras
inspect_datasets
inspect_policies
inspect_jobs
analyze_diagnostics
```

Tool adlarında kanonik kaynak [Workflow Kataloğu](WORKFLOW_KATALOGU_TR.md) §5'tir;
kod o adları uygular.

### Hazırlık ve planlama

```text
prepare_calibration
prepare_teleoperation
prepare_recording
prepare_training
prepare_evaluation
prepare_rollout
```

### Mutasyon, fakat actuation olmayan

```text
create_robot_profile
save_camera_mapping
queue_dataset_validation
queue_training
sync_hub_artifact
```

### Fiziksel ve onay zorunlu

```text
request_calibration_execution
request_teleoperation
request_replay
request_rollout
stop_job
```

Tool çağrısı fiziksel action göndermez; command oluşturur, doğrular ve gerekiyorsa
approval state'ine geçirir.

Ham `serial_tool`, shell, dynamic import veya genel amaçlı LeRobot method bridge
production ajan tool registry'sine eklenmez.

## 10. API modeli

### 10.1 REST

REST; command, query ve metadata için:

```text
GET  /api/system/capabilities
GET  /api/system/doctor
GET  /api/devices
GET  /api/robots
POST /api/robots/{id}/validate
GET  /api/jobs
POST /api/jobs
POST /api/jobs/{id}/confirm
POST /api/jobs/{id}/cancel
POST /api/safety/emergency-stop
GET  /api/datasets
GET  /api/policies
GET  /api/agents/sessions
```

Bu endpoint'ler kesinleşmiş contract değildir; ilk uygulama sırasında OpenAPI
schema ve domain modelleriyle sabitlenecektir.

### 10.2 WebSocket

WebSocket:

- Device connect/disconnect
- Job state/progress
- Joint telemetry
- Control loop latency
- Camera preview signaling/metadata
- Agent event stream
- Logs

için kullanılabilir.

Kamera stream'i başlangıçta MJPEG/WebSocket frame ile yapılabilir; gecikme ve
CPU maliyeti ölçüldükten sonra WebRTC değerlendirilebilir.

### 10.3 Command ve event ayrımı

UI veya ajan `teleoperation started` event'i yazamaz. Sadece
`StartTeleoperation` command'i gönderebilir. Backend validation sonrası gerçek
event'i üretir.

Bu ayrım audit, retry ve crash recovery için zorunludur.

## 11. Veri ve artifact saklama

### SQLite

- Profiles
- Device mapping
- Jobs ve state transition
- Resource leases
- Approvals
- Audit metadata
- Agent session referansları
- Dataset/policy manifestleri
- User preferences

SQLite; başlangıç için yeterli, taşınabilir ve local-first'tür. WAL mode ve
transaction sınırları kullanılmalıdır.

### Dosya sistemi

- Datasetler
- Videolar
- Checkpointler
- Training output
- Log paketleri
- Calibration artifact kopyaları
- Simülasyon kayıtları

Artifact path'leri app-managed bir root altında tutulmalı; kullanıcı tarafından
seçilen dış path'ler ayrıca izinli workspace olarak kaydedilmelidir.

### Hugging Face Hub / cloud

- Dataset/model senkronizasyonu opsiyoneldir.
- Local operation Hub hesabı olmadan çalışmalıdır.
- Token işletim sisteminin keychain/credential store'unda tutulmalıdır.
- Token log veya trace'e yazılmamalıdır.

## 12. Packaging ve kurulum

### 12.1 Canonical dağıtım

Önerilen son kullanıcı akışı:

```bash
uv tool install hashtag-robotics
hashtag-robotics
```

Alternatif:

```bash
pipx install hashtag-robotics
hashtag-robotics
```

Package adı release öncesi marka ve PyPI müsaitliğiyle kesinleşecektir.

### 12.2 Paket içeriği

Python wheel:

- FastAPI server
- Domain ve adapter kodu
- Migration'lar
- Derlenmiş frontend static asset'leri
- CLI
- Doctor ve diagnostics

### 12.3 Feature extras

Önerilen yapı:

```text
[core]       API, UI, metadata
[so101]      LeRobot + Feetech
[training]   Torch ve training bağımlılıkları
[agents]     Strands Agents/Robots
[sim]        MuJoCo
[realsense]  RealSense
[dev]        test/lint/typecheck
```

`[all]` teknik olarak bulunabilir; fakat son kullanıcı için tavsiye edilen
kurulum olmamalıdır. ROS 2, Isaac, CUDA ve RealSense gibi sistem bağımlılıkları
doctor tarafından ayrı yönetilmelidir.

### 12.4 NPM ve desktop installer

NPM daha sonra:

- Python runtime kontrolü,
- uygun wheel/environment kurulumu,
- uygulama başlatma

için ince bir launcher olabilir. Robot runtime'ın kendisi olmamalıdır.

Tauri veya native installer sonraki aşamada aynı Python control plane'i
paketleyebilir.

## 13. Capability ve version yönetimi

Başlangıçta backend şu manifesti üretmelidir:

```text
platform_version
python_version
os/architecture
lerobot_version
strands_agents_version
strands_robots_version
torch_version
accelerator
ffmpeg
camera_backends
robot_adapters
teleoperator_adapters
policy_adapters
simulation_backends
contract_test_results
```

Capability yalnızca paket sürümünden çıkarılmamalıdır. Import ve minimum
contract test sonucu da gereklidir.

Release kanalları:

- `stable`: Tam contract testlerinden geçmiş kombinasyon.
- `preview`: Yeni upstream özellikleri, açık risk uyarısı.
- `development`: Kaynak commit'leri ve geliştirici araçları.

## 14. Güvenlik ve gizlilik

- Varsayılan bind adresi `127.0.0.1`.
- Browser session yerel token ile doğrulanır.
- LAN erişimi varsayılan kapalıdır.
- LAN/remote açılırsa TLS ve kullanıcı authentication zorunludur.
- Shell command oluşturulurken string interpolation kullanılmaz.
- File path'ler izinli root içinde resolve edilir.
- Secret'lar redacted edilir.
- Diagnostics bundle oluşturulmadan önce kullanıcıya içerik gösterilir.
- Camera kaydı ve Hub upload açık kullanıcı aksiyonu gerektirir.
- Agent trace'leri prompt injection ve PII açısından filtrelenir.
- Update, calibration ve dataset migration için rollback üretir.

## 15. Gözlemlenebilirlik

Üç telemetry alanı birbirinden ayrılmalıdır:

### Robot telemetry

- Joint state
- Action
- Loop FPS
- Latency/jitter
- Dropped camera frames
- Torque/power durumu
- Watchdog

### Job telemetry

- State transition
- Progress
- Worker PID/health
- Resource leases
- Artifacts
- Failure code

### Agent telemetry

- Session
- Model call
- Tool call
- Intervention
- Approval
- Token/latency metrikleri

Ortak correlation ID ile:

```text
agent request → command → job → hardware event → result
```

zinciri izlenebilir olmalıdır.

## 16. Test stratejisi

### Unit

- State machine
- Safety rules
- Feature mapping
- Path ve secret redaction
- Compatibility resolution

### Contract

- Belirli LeRobot sürümüne karşı adapter
- Strands tool schema
- Kamera backend
- Dataset ve policy manifest extraction

### Simulation

- Teleop ve action sınırları
- Agent workflow
- Disconnect ve timeout
- Dataset recording

### Hardware-in-the-loop

- Gerçek leader/follower keşfi
- Calibration
- Kamera mapping
- Teleop latency
- Emergency stop
- USB disconnect
- Güç kesintisi sonrası recovery

### Release

- Temiz işletim sisteminde kurulum
- Upgrade/downgrade
- Offline startup
- Diagnostics
- Uninstall ve artifact koruma

## 17. İlk teknik teknoloji seçimi

Bunlar başlangıç önerileridir; Faz 0 spike'larıyla doğrulanacaktır:

| Alan | Öneri |
|---|---|
| Runtime | Python 3.12 |
| API | FastAPI + Pydantic v2 |
| Metadata | SQLite + migration sistemi |
| Frontend | React + TypeScript + Vite |
| Realtime | WebSocket |
| Agent runtime | Strands Agents Python |
| Robot adapter | LeRobot |
| Genişletme | Strands Robots |
| Simülasyon | MuJoCo ile başla |
| Test | Pytest + Playwright |
| Paketleme | Python wheel + gömülü frontend |
| CLI install | `uv tool` / `pipx` |

## 18. Mimari karar kapıları

Kodlamaya başlamadan veya Faz 0 sırasında kesinleşmesi gerekenler:

1. İlk desteklenen işletim sistemleri.
2. İlk Hashtag SO-101 SKU ve hardware revision'ı.
3. PyPI ve ürün adı.
4. Stable LeRobot/Strands sürüm seti.
5. UI'nın yerel HTTP mi desktop shell mi başlayacağı.
6. Fabrika calibration ve seri numarası formatı.
7. İlk kamera backend'leri.
8. Cloud/Hugging Face hesabının MVP'deki yeri.

Bu kararların mevcut varsayımları
[Kararlar ve Riskler](KARARLAR_VE_RISKLER_TR.md) dokümanında tutulur.
