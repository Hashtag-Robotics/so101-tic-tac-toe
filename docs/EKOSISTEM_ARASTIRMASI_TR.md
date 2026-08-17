# SO-101, LeRobot ve Strands Ekosistemi Araştırması

**Araştırma anlık görüntüsü:** 23 Temmuz 2026
**Ürün bağlamı:** Hashtag Robotics SO-101 robot kolları
**Durum:** Araştırma tamamlandı, uygulama başlamadı

## 1. Yönetici özeti

Hashtag Robotics için doğru ürün, LeRobot CLI komutlarını butonlara dönüştüren
bir web paneli değildir. Doğru ürün; bilgisayara bağlı robot, leader kol,
kameralar, datasetler, eğitim işleri, policy'ler ve ajanlar arasında güvenli,
kalıcı ve gözlemlenebilir bir işletim katmanıdır.

Ekosistemdeki sorumluluk ayrımı şöyle olmalıdır:

| Katman | Birincil sorumluluk |
|---|---|
| LeRobot | SO-101 donanımı, kalibrasyon, kamera, teleop, dataset, eğitim ve rollout |
| Strands Robots | Robot factory, policy adaptörleri, simülasyon, ROS/RTPS ve mesh |
| Strands Agents | Ajanlar, tool'lar, session, workflow, intervention ve gözlemlenebilirlik |
| Hashtag Platform | Cihaz profili, iş yönetimi, güvenlik, uyumluluk, audit ve ürün UX'i |

Bu ayrımın kritik sonucu şudur:

> LeRobot yeniden yazılmayacak, Strands Robots backend'in tamamı kabul
> edilmeyecek ve ajanlar doğrudan fiziksel robot kontrol katmanı olmayacaktır.

Hashtag platformu, upstream projelerin hızlı değişen ve araştırma odaklı
yüzeylerini müşteriye satılabilir bir ürüne çevirecektir.

## 2. İncelenen resmî kaynaklar

- [Strands Robots dokümanı](https://strands-labs.github.io/robots/)
- [Strands Robots GitHub](https://github.com/strands-labs/robots)
- [Strands Robots PyPI](https://pypi.org/project/strands-robots/)
- [Strands Agents](https://strandsagents.com/)
- [Strands Agents SDK başlangıç ve özellik tablosu](https://strandsagents.com/docs/user-guide/quickstart/overview/)
- [LeRobot GitHub](https://github.com/huggingface/lerobot)
- [LeRobot PyPI](https://pypi.org/project/lerobot/)
- [LeRobot SO-101 dokümanı](https://huggingface.co/docs/lerobot/so101)
- [LeRobot komut özeti](https://huggingface.co/docs/lerobot/main/cheat-sheet)
- [LeRobotDataset v3](https://huggingface.co/docs/lerobot/main/lerobot-dataset-v3)
- [LeRobot processor mimarisi](https://huggingface.co/docs/lerobot/main/introduction_processors)
- [LeRobot async inference](https://huggingface.co/docs/lerobot/main/async)
- [LeRobot backward compatibility](https://huggingface.co/docs/lerobot/main/backwardcomp)
- [LeLab GitHub](https://github.com/huggingface/leLab)
- [Hashtag Robotics](https://labs.hashtagrobotics.tr/)

## 3. Güncel paket ve kaynak durumu

Araştırma tarihindeki görünen kararlı paketler:

| Proje | Kararlı paket | Önemli not |
|---|---:|---|
| LeRobot | `0.6.0` | Python `>=3.12`; proje hızlı değişiyor |
| Strands Robots | `0.4.1` | PyPI ve `main` yetenek/sürüm farkı var |
| Strands Agents | `1.48.0` | Python ve TypeScript SDK mevcut |
| LeLab | Kaynak sürümü `0.1.0` | Henüz olgun son kullanıcı dağıtımı değil |

Bu tablo sabit bir ürün garantisi değildir. Her release hazırlığında resmî
paket metadata'sı ve kurulan gerçek modül yüzeyi yeniden doğrulanmalıdır.

### 3.1 Kritik dependency uyuşmazlığı

`strands-robots==0.4.1` paket metadata'sı LeRobot için şu aralığı tanımlar:

```text
lerobot >=0.5.0, <0.6.0
```

Ancak güncel LeRobot kararlı sürümü `0.6.0`'dır. Strands Robots `main`
dalındaki `pyproject.toml` bu aralığı `>=0.6.0,<0.7.0` olarak günceller, fakat
bu yüzey PyPI'daki `0.4.1` release'iyle aynı değildir.

Sonuç:

- Kullanıcıya `pip install lerobot strands-robots` demek güvenilir değildir.
- Platform kendi test edilmiş sürüm setini pinlemelidir.
- Kurulu paket sürümü kadar, gerçek import/tool yüzeyi de kontrol edilmelidir.
- `stable` ve `preview` uyumluluk kanalları ayrılmalıdır.
- Upstream sürüm yükseltme işlemi calibration, dataset ve policy migration
  testlerinden geçmelidir.

## 4. LeRobot analizi

### 4.1 Üründeki rolü

LeRobot, fiziksel SO-101 ile ilgili doğruluğun ana kaynağı olmalıdır:

- Motor bus ve Feetech adaptörleri
- Leader/follower robot ve teleoperator tanımları
- Port ve kamera keşfi
- Motor kurulumu
- Kalibrasyon
- Teleoperation
- Observation/action üretimi
- Dataset recording ve replay
- Policy training
- Evaluation ve rollout
- Hub, checkpoint ve pretrained policy entegrasyonu

Hashtag backend'i LeRobot'u değiştirmemeli; onun üzerine kararlı bir adaptör
sözleşmesi koymalıdır.

### 4.2 SO-101 yaşam döngüsü

LeRobot'un resmî SO-101 akışı şu zinciri kapsar:

```text
port keşfi
  → motor ID/baud kurulumu
  → leader/follower kalibrasyonu
  → kamera keşfi ve atama
  → teleoperation
  → episode kaydı
  → dataset doğrulama
  → policy eğitimi
  → rollout/evaluation
```

Dashboard bütün zinciri yönetebilir; ancak her adımı tek bir belirsiz "robot
hazır" durumuna indirgememelidir. Port hazır, calibration hazır, kamera hazır,
dataset uyumlu ve rollout güvenli durumları ayrı ayrı modellenmelidir.

### 4.3 Robot ve dataset feature sözleşmesi

SO-101 follower tarafında pratik feature seti altı action/state alanından
oluşur:

```text
shoulder_pan.pos
shoulder_lift.pos
elbow_flex.pos
wrist_flex.pos
wrist_roll.pos
gripper.pos
```

Kamera alanları ise dataset'e verilen semantik adlarla oluşur; örneğin:

```text
observation.images.front
```

Dashboard aşağıdaki varsayımları yapmamalıdır:

- Simülasyon joint isimleri gerçek dataset joint isimleriyle aynıdır.
- USB kamera sırası yeniden başlatmada sabit kalır.
- Policy'nin beklediği `front` kamera otomatik olarak ilk kameradır.
- İki farklı SO-101 calibration dosyası birbirinin yerine kullanılabilir.
- Dataset'in FPS değeri ile gerçek kontrol loop'u farklı olsa da sorun olmaz.

Feature mapping bilinmiyorsa rollout engellenmelidir.

### 4.4 LeRobotDataset v3

LeRobotDataset v3:

- Tabular verileri Parquet olarak,
- görüntüleri/video akışlarını MP4 olarak,
- feature ve episode bilgilerini metadata olarak

tutar. Dataset upload/download dışında split, merge, feature düzenleme,
annotate ve re-encode gibi yaşam döngüsü işlemleri de vardır.

Bu nedenle ürün içinde ayrı bir Dataset Studio gerekir. Dataset Studio en az
şunları göstermelidir:

- Dataset adı, görev açıklaması ve sahiplik
- Episode sayısı ve süreleri
- FPS ve video codec
- Action/state boyutları
- Kamera feature isimleri
- Robot ve calibration profile referansı
- Hatalı/eksik frame ve timestamp durumu
- Kullanılan teleoperator
- Dataset → policy uyumluluk sonucu
- Hub senkronizasyon durumu

### 4.5 Processor katmanı

LeRobot processor'ları raw sensör/robot verisi ile policy arasında köprü kurar:

- Normalization
- Feature yeniden adlandırma
- Coordinate/unit dönüşümü
- Kamera/state/action eşleme
- Model output'unu robot action'a dönüştürme

Hashtag platformu bu zinciri gizli bir upstream detay olarak bırakmamalıdır.
Bir rollout öncesi kullanılan input ve output processor zinciri doğrulanabilir
bir compatibility manifest içinde görünmelidir.

### 4.6 Eğitim ve policy yüzeyi

LeRobot ekosistemi ACT ile sınırlı değildir. Ana kaynak ağacında ACT,
Diffusion, SmolVLA, PI ailesi, GR00T ve başka policy aileleri bulunmaktadır.
Ancak her policy:

- Her işletim sisteminde çalışmayabilir.
- Aynı GPU/VRAM gereksinimine sahip değildir.
- Aynı dataset feature'larını beklemez.
- Aynı LeRobot release'inde kararlı olmayabilir.

UI policy isimlerini hardcode etmemelidir. Backend kurulu sürümden capability
manifest üretmeli ve yalnızca doğrulanmış policy preset'lerini göstermelidir.

### 4.7 Async ve uzak inference

LeRobot async inference, policy prediction ile robot action execution'ı ayırır.
Bu aşağıdaki topolojilere izin verir:

- Robot bilgisayarı + aynı ağdaki GPU workstation
- Yerel robot daemon + Hugging Face/AWS GPU job
- Gelecekte Hashtag tarafından yönetilen inference servisi

Gerçek robotta uzak inference açılmadan önce:

- TLS ve authentication
- Heartbeat
- Latency/jitter ölçümü
- Stale action reddi
- Action queue sınırı
- Disconnect davranışı
- Watchdog ve safe stop

çözülmelidir.

### 4.8 LeRobot kaynaklı riskler

- Hardware calibration formatı değişebilir.
- Normalization processor'a taşındığı için eski policy migration gerekebilir.
- CLI ve internal Python API aynı hızda kararlılaşmayabilir.
- Kamera backend ve sürücüleri işletim sistemine göre farklılaşır.
- PyTorch/CUDA/MPS kurulumu tek tip değildir.
- Upstream `main` dokümanı yayımlanmış paketten ileride olabilir.

Bu risklerin çözümü, Hashtag Product API ile LeRobot Compatibility Adapter'ı
ayırmaktır.

## 5. Strands Robots analizi

### 5.1 Üründeki rolü

Strands Robots aşağıdaki alanları tek ekosistemde birleştirmeyi hedefler:

- Sim ve real robot factory
- LeRobot entegrasyonu
- Policy adaptörleri
- Simülasyon backend'leri
- ROS 2 / RTPS
- Robot mesh ve uzak bağlantı
- Kamera, calibration, serial ve pose araçları
- Ajanlara sunulabilecek robot tool'ları

Bu, Hashtag platformuna genişleme yolu verir; fakat Strands Robots fiziksel
SO-101 doğruluğunun kaynağı olarak LeRobot'un yerine geçmemelidir.

### 5.2 Sim-first yaklaşım

Strands Robots'ta simülasyonun varsayılan, gerçek modun açık seçim olması iyi
bir güvenlik davranışıdır. Hashtag platformu bunu daha sıkı uygulamalıdır:

- Yeni workflow varsayılan olarak simülasyon veya read-only başlar.
- `mode="auto"` güvenlik açısından kullanılmaz.
- Gerçek donanım hedefi açıkça çözülmeden actuation yapılamaz.
- Agent tool schema'sında `real` hedef belirsiz bırakılamaz.

### 5.3 Tool yüzeyi ve aşırı yetki

Strands Robots raw serial ve genel amaçlı LeRobot köprüleri içerir. Bunlar
geliştirici laboratuvarında faydalıdır; son kullanıcıya açık ajanlarda aşırı
yetkilidir.

Ajanlara doğrudan verilmemesi gereken yüzeyler:

- Arbitrary serial read/write
- Arbitrary shell command
- Genel amaçlı dynamic method/module bridge
- Doğrudan gerçek robot factory
- Serbest joint position/velocity gönderimi
- Onaysız policy rollout

Hashtag platformu dar ve tipli tool'lar sunmalıdır:

```text
inspect_hardware
validate_robot_profile
validate_calibration
prepare_teleoperation
prepare_recording
queue_training
request_rollout
stop_robot
```

Bu tool'ların tamamı backend command bus ve safety policy üzerinden
çalışmalıdır.

### 5.4 Doküman ve release farkı

Strands Robots `main` kaynak ağacı hızlı büyümektedir. Dokümanda görülen bir
özelliğin kurulu PyPI paketinde gerçekten mevcut olduğu varsayılmamalıdır.

Platform başlangıçta:

1. Kurulu sürümü bulmalı.
2. İlgili modülü import ederek capability kontrolü yapmalı.
3. Desteklenen contract testlerini çalıştırmalı.
4. UI'da yalnızca kullanılabilir özellikleri açmalıdır.

## 6. Strands Agents analizi

### 6.1 Üründeki rolü

Strands Agents aşağıdaki yetenekleri sunar:

- Python ve TypeScript SDK
- Birden fazla model provider
- Custom function tool ve MCP
- Session management
- Lifecycle hooks
- Interventions
- Graph, workflow, swarm ve agents-as-tools
- Steering ve human-in-the-loop
- OpenTelemetry

Hashtag platformunda Strands, kullanıcı niyetini plan ve doğrulanmış üst seviye
komutlara çeviren reasoning katmanı olmalıdır.

### 6.2 Uygun ajan rolleri

İlk ürün için önerilen ajanlar:

| Ajan | Varsayılan yetki |
|---|---|
| Lab Assistant | Read-only cihaz ve kurulum analizi |
| Calibration Assistant | Adım yönlendirme ve validation |
| Dataset Curator | Dataset kalite ve schema analizi |
| Training Advisor | Policy/preset ve kaynak önerisi |
| Evaluation Analyst | Rollout sonuç ve latency analizi |
| Robot Operator | Sadece onaylı yüksek seviye command |

İlk aşamada serbest swarm yerine Graph/Workflow tercih edilmelidir. Fiziksel
süreçlerde sıra, tekrar üretilebilirlik ve hata durumları açık olmalıdır.

### 6.3 Intervention tek başına safety değildir

Strands Interventions `proceed`, `deny`, `guide`, `confirm` ve `transform`
kararlarıyla tool çağrılarını kontrol edebilir. Bu ajan yetkilendirmesi için
değerlidir; ancak fiziksel güvenlik garantisi değildir.

İki ayrı güvenlik katmanı gerekir:

1. Strands authorization/intervention katmanı
2. LLM'den bağımsız deterministic robot safety gateway

İkinci katman; joint limit, calibration, action dimension, camera mapping,
resource ownership, watchdog ve emergency stop gibi gerçek garantilerin
sahibidir.

### 6.4 Gözlemlenebilirlik

Strands OpenTelemetry ile model çağrıları, tool kullanımı ve agent loop
izlenebilir. Hashtag platformu robot job ve agent trace'lerini ortak bir
correlation ID ile bağlayabilir.

Ancak aşağıdakiler trace'e kontrolsüz yazılmamalıdır:

- Model/API token'ları
- Hub credential'ları
- Kamera görüntüleri
- Kişisel kullanıcı verileri
- Tam calibration veya cihaz secret bilgileri

## 7. LeLab analizi

### 7.1 Ne sunuyor?

LeLab, Hugging Face tarafından LeRobot üzerinde geliştirilen web UI'dır:

- Calibration
- Teleoperation
- Recording
- Training
- Inference/rollout
- Replay
- Dataset upload
- Yerel ve Hugging Face Jobs ile eğitim

Teknik yaklaşımı:

- FastAPI backend
- React/Vite frontend
- Frontend'in Python paketine gömülmesi
- Yerel HTTP sunucusu ve browser UI

Bu, önerilen local-first packaging yaklaşımımızı doğrular.

### 7.2 Neden kopyalanmamalı?

LeLab fikrin doğruluğunu gösterir, fakat Hashtag ürününün tek farklılığı olamaz.
Kaynak incelemesinde görülen sınırlamalar:

- SO-101'e sıkı bağlı akışlar
- Feature modüllerinde process içi/global durum kullanımı
- Merkezi ve kalıcı bir job state machine eksikliği
- Resource lease ve crash recovery'nin ürün seviyesinde olmaması
- Kaynak deposu üzerinden kurulum ağırlığı
- Sınırlı robot/SKU/device profile modeli
- Strands ajan ve safety gateway katmanının bulunmaması

### 7.3 Önerilen kullanım şekli

LeLab:

- UX akışları için referans,
- LeRobot entegrasyon örneği,
- Wheel içine frontend paketleme örneği,
- Apache-2.0 kurallarına uygun olduğunda seçili kod fikirleri

olarak kullanılabilir.

Hashtag platformu kendi:

- Domain modelini,
- job engine'ini,
- resource manager'ını,
- safety gateway'ini,
- version adapter'ını,
- agent permission modelini

kurmalıdır.

## 8. Hashtag Robotics ürün fırsatı

Hashtag Robotics fiziksel robot sattığı için yalnızca genel bir açık kaynak UI
yapmak zorunda değildir. Yazılım, satılan robotu ürün/SKU olarak tanıyabilir.

Önerilen Hashtag Robot Profile:

```text
product_sku
robot_serial
leader_serial
follower_serial
motor_id_layout
device_fingerprints
factory_calibration_revision
camera_profiles
joint_limit_profile
factory_qa_revision
software_compatibility_channel
support_and_warranty_metadata
```

Bu model şu müşteri deneyimini sağlar:

```text
robotu bağla
  → read-only discovery
  → leader/follower ve kamera eşleme
  → fabrika profiliyle karşılaştır
  → calibration ve safety preflight
  → teleop/record/train seçeneklerini aç
```

Robot bağlandığı anda otomatik hareket başlatılmamalıdır.

## 9. Ürünün yapmaması gerekenler

- LeRobot'u yeniden yazmak
- LeLab'i marka değiştirerek kopyalamak
- Node.js'i fiziksel robot runtime'ı yapmak
- Tek process ve global değişkenlerle job yönetmek
- Ajanı servo kontrol loop'una koymak
- Kullanıcıya raw serial veya genel shell tool açmak
- Tüm sim, ROS, Isaac ve policy paketlerini ilk installer'a koymak
- Dokümanda görünen her upstream özelliği destekleniyor kabul etmek
- Dataset/policy/robot schema farkını sessizce dönüştürmek
- Robot bağlanınca otomatik actuation yapmak

## 10. Temel ürün tezi

Hashtag Robotics yazılımının kalıcı farkı üç bileşendir:

1. **Hashtag Robot Profile:** Satılan fiziksel ürünün dijital kimliği.
2. **Persisted Job ve Resource Control Plane:** Robot işlemlerinin güvenilir
   yaşam döngüsü.
3. **Agent-safe Robot Command Gateway:** Ajan kararları ile fiziksel hareket
   arasındaki deterministic güvenlik sınırı.

Bu tez, hedef mimari ve yol haritasının temelidir.
