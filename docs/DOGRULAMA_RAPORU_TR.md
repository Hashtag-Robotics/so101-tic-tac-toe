# Bağımsız Durum Raporu — SO-101 Control Plane

**Tarih:** 31 Temmuz 2026
**İncelenen sürüm:** `21bf07c` — "Initial SO-101 control plane", 23 Temmuz 2026.
Deponun tek commit'i; tek dal, etiket yok, release yok, CI yok.
**Boyut:** 3.176 satır Python kaynak, 549 satır test (19 test), 1.707 satır React arayüz.
**Soru:** Depo GitHub'daki bu hâliyle robota takılıp çalışır mı?
**Cevap:** Hayır.

**Test ortamı:** Jetson Orin Nano Super 8 GB, JetPack 6.x (Linux 5.15.148-tegra, aarch64),
Python 3.12.12, kurulu gerçek `lerobot 0.6.0`, `torch 2.11.0`, `strands-agents 1.48.0`.

**Yöntem:** depo ayrı bir dizine klonlandı, hiçbir yama uygulanmadı, uygulama olduğu gibi
ayağa kaldırıldı ve ürettiği komutlar gerçek LeRobot 0.6.0'a verildi. Bütün fiziksel denemeler
sahte port adlarıyla (`/dev/ttyNOPE`) yapıldı: hiçbir kol bağlanmadı, hiçbir servo enerjilenmedi.
Aşağıdaki her ölçüm bu makinede alındı.

---

## 1. Özet

Depo kurulur, açılır, kendi testlerini geçer ve simülasyon akışları sorunsuz akar. Gerçek moda
geçirildiği anda **altı fiziksel LeRobot komutunun altısı da** donanıma ulaşmadan argüman
ayrıştırmada düşer. Bu eksik bir özellik değil, hiç çalıştırılmamış bir arayüz sözleşmesidir.

| Kapı | Sonuç |
|---|---|
| Kurulum / import (aarch64, py3.12) | ✅ sorunsuz |
| Kendi test paketi | ✅ 19/19, 5,97 sn |
| Simülasyon/mock iş akışları | ✅ akıyor — sonuçlar uydurma (B16) |
| MuJoCo sözleşme simülasyonu | ✅ koşuyor (gerçek SO-101 modeli değil) |
| Web paneli | ❌ derlenmiş varlık depoda yok (B13) |
| Panelden gerçek moda geçiş | ❌ arayüzde böyle bir yol yok (B4) |
| Gerçek teleoperation | ❌ `exit code 2` (B1) |
| Gerçek kayıt / replay / rollout | ❌ `unrecognized arguments` (B1, B2) |
| Gerçek kalibrasyon | ❌ `EOFError` (B5) |
| Acil durdurma | ⚠️ tork kesilmiyor (B6), etkin gecikme ~5 sn (B7) |
| `doctor.run()` ilk çağrı | ⚠️ 2.680 ms olay döngüsünü kilitliyor (B11) |

### Bulgu dizini

| # | Ağırlık | Bulgu |
|---|---|---|
| B1 | Bloklayıcı | `--robot.type=so_follower` diye bir tip yok; altı komutu birden düşürüyor |
| B2 | Bloklayıcı | `record`/`replay`/`rollout` argüman şeması yanlış |
| B3 | Bloklayıcı (kök sebep) | Testler kodun kendi ürettiği dizgiyi doğruluyor, LeRobot'a sormuyor |
| B4 | Bloklayıcı | Arayüzde gerçek moda çıkan hiçbir yol yok; onay düğmesi yok |
| B5 | Bloklayıcı | Kalibrasyon stdin'siz başlatılıyor → `EOFError` |
| B6 | Güvenlik | Acil durdurma torku kesmiyor; servolar güç altında kalıyor |
| B7 | Yüksek | Durdurma her seferinde 5 sn bekleyip SIGKILL'e düşüyor |
| B8 | Orta | Operatörün iptali audit'e `failed` diye yazılıyor |
| B9 | Orta | Komut hatasının sebebi yutuluyor; operatöre yalnız çıkış kodu ulaşıyor |
| B10 | Orta | Sabit 900 sn iş zaman aşımı; uzun kayıt ortadan kesilir |
| B11 | Yüksek | `doctor.run()` olay döngüsünü 2,68 sn kilitliyor; e-stop de aynı döngüde |
| B12 | Orta | Teleop'ta `--display_data=true` sabit; öksüz görüntüleyici süreçleri kalıyor |
| B13 | Yüksek | Panel derlenmiş hâlde gelmiyor; node/npm gerekiyor |
| B14 | Güvenlik | Güvenlik bayrakları beyana dayalı; `max_relative_target` hiç gönderilmiyor |
| B15 | Orta | Kalibrasyon yedeği/checksum planı var, kodu yok |
| B16 | Orta | Mock sonuçlar uydurma; manifest'ler yine de `verified` damgası alıyor |
| B17 | Orta | Kamera yüzeyi ve diskteki gerçek dataset yok |
| B18 | Orta | Doctor seri port iznini, kamerayı, kalibrasyon dosyalarını kontrol etmiyor |
| B19 | Orta | Komut önizleme uç noktası arayüze bağlanmamış |
| B20 | Bilgi | Uyumluluk doğrulaması yalnız macOS arm64'te yapılmış; Linux+CUDA kapsam dışı |

---

## 2. Kanıt tabanı

Adapter'ın gerçek modda ürettiği komutlar — kendi `LeRobotCommandBuilder` sınıfı sürülerek
alındı:

```text
lerobot-teleoperate --robot.type=so_follower --robot.port=… --robot.id=… \
                    --teleop.type=so_leader --teleop.port=… --teleop.id=… --display_data=true
lerobot-record      … --repo_id=… --single_task=… --num_episodes=2 --episode_time_s=30 \
                      --reset_time_s=15 --push_to_hub=false
lerobot-replay      … --repo_id=… --episode=0
lerobot-rollout     … --policy.path=… --task=… --num_episodes=1
lerobot-calibrate   --robot.type=so_follower --robot.port=… --robot.id=…
lerobot-train       --dataset.repo_id=… --policy.type=act …
```

---

## 3. Bloklayıcı bulgular

### B1 — Robot/teleoperator tipi adları LeRobot'ta yok

Adapter `--robot.type=so_follower` ve `--teleop.type=so_leader` gönderiyor. LeRobot 0.6.0'da
kayıtlı tipler `so101_follower` / `so100_follower` ve `so101_leader` / `so100_leader`.

```text
$ lerobot-calibrate --robot.type=so_follower --robot.port=/dev/ttyNOPE --robot.id=follower
lerobot-calibrate: error: argument --robot.type: invalid choice: 'so_follower'
(choose from openarm_follower, …, so100_follower, so101_follower, bi_so_follower, …)
```

Muhtemel kaynak: LeRobot'un **dizin** adı `lerobot/robots/so_follower/`, ama
`@RobotConfig.register_subclass` ile kaydedilen **tip** adı `so101_follower`. Dizin adı sözleşme
sanılmış. `bi_so_follower`'ın gerçekten geçerli bir tip olması karışıklığı besliyor.

Bu tek satır teleoperation, kayıt, replay, rollout, kalibrasyon ve motor kurulumunun hepsini
donanıma ulaşmadan düşürüyor.

### B2 — `record` / `replay` / `rollout` argüman şeması yanlış

LeRobot 0.6.0'da dataset alanları `DatasetRecordConfig` altında yaşar ve `--dataset.` önekiyle
verilir. Adapter düz gönderiyor. `rollout` ise `--num_episodes` diye bir alan tanımıyor;
`--strategy.type` + `--duration` (veya `--strategy.num_episodes`) ile çalışıyor.

Tip adı elle düzeltilip yalnız argümanlar test edildiğinde:

```text
lerobot-record: error: unrecognized arguments: --repo_id=x/y --single_task=pick \
                --num_episodes=1 --episode_time_s=30 --reset_time_s=15 --push_to_hub=false
lerobot-replay: error: unrecognized arguments: --repo_id=x/y --episode=0
lerobot-rollout: error: unrecognized arguments: --num_episodes=1
```

| Komut | Adapter'ın ürettiği | LeRobot 0.6.0'ın beklediği | Sonuç |
|---|---|---|---|
| `setup-motors` | `--robot.type=so_follower` | `so101_follower` | ❌ B1 |
| `calibrate` | `--robot.type=so_follower` | `so101_follower` | ❌ B1 + B5 |
| `teleoperate` | `--robot.type=so_follower` | `so101_follower` | ❌ B1 |
| `record` | `--repo_id`, `--single_task`, `--num_episodes`, `--episode_time_s`, `--reset_time_s`, `--push_to_hub` | hepsi `--dataset.*` | ❌ B1 + B2 |
| `replay` | `--repo_id`, `--episode` | `--dataset.repo_id`, `--dataset.episode` | ❌ B1 + B2 |
| `rollout` | `--num_episodes` | `--strategy.*` / `--duration` | ❌ B1 + B2 |
| `train` | `--dataset.repo_id`, `--policy.type`, … | aynısı | ✅ tek doğru komut |

`train`'in doğru, `record`'un yanlış olması tesadüf değil: `dataset.` kuralı biliniyor ama yalnız
eğitim tarafında uygulanmış. Sözleşme okunarak değil, hatırlanarak yazılmış.

### B3 — Kök sebep: testler hatayı doğrulayıp sabitliyor

`tests/test_hardware.py`:

```python
assert "--robot.type=so_follower" in plan.arguments
assert "--teleop.type=so_leader" in plan.arguments
```

Test, kodun ürettiği dizgiyi yine koda soruyor; LeRobot'a hiç sormuyor. `record` ve `replay`
argümanlarının doğruluğunu hiçbir test kontrol etmiyor — kayıt testi yalnızca `repo_id` eksikse
hata atıldığını doğruluyor. 19 testin tamamı 6 saniyede geçiyor, çünkü hiçbiri sürecin dışına
çıkmıyor.

`docs/UYUMLULUK_MATRISI_TR.md` aynı döngüyü resmileştiriyor:

> "Doğrulanan LeRobot console scripts: … proje environment'ında **mevcut olduğu** doğrulanan
> komutlar"

Doğrulanan şey komutların var olduğu; argümanları kabul ettiği değil. Aynı belgedeki release
kuralı #4 ("Typed command builder testleri geçer") de bu yüzden hiçbir şey garanti etmiyor.

### B4 — Arayüzde gerçek moda çıkan yol yok

`App.tsx`'teki 10 iş oluşturma çağrısının 10'u da `"sim"` (biri `"read_only"`) gönderiyor.
Panelde port girilecek alan, gerçek robot profili kaydedecek form ve onay düğmesi yok.
Backend'deki `POST /api/jobs/{id}/confirm` uç noktasını arayüz hiç çağırmıyor — `api.ts`'te böyle
bir çağrı bulunmuyor.

Sonuç: `HASHTAG_ENABLE_PHYSICAL=true` yapılsa bile gerçek bir iş `awaiting_confirmation`
durumunda kalır; onaylamanın tek yolu `curl`.

### B5 — Kalibrasyon panelden tamamlanamaz

`lerobot-calibrate` operatöre `input("Move … and press ENTER")` diyor
(`so_follower.py:131`, `so_leader.py:100`). Uygulama süreci `start_new_session=True` ile, stdin
için hiçbir yol bırakmadan başlatıyor. Aynı çağrı kalıbı birebir kurulduğunda:

```text
Move to middle and press ENTER...
EOFError: EOF when reading a line
çıkış kodu: 1
```

Tipler düzeltilse bile kalibrasyon çalışmaz: panelde ENTER'a basılacak yer yok, terminale bağlı
çalıştırılsa bile süreç oturumdan koparıldığı için oradan da okuyamaz.

---

## 4. Güvenlik bulguları

### B6 — Acil durdurma torku kesmiyor

E-stop yalnızca işleri iptal ediyor: doğrudan çocuk sürece SIGINT, 5 sn sonra SIGKILL. Hiçbir
yolda `Torque_Enable = 0` (adres 40) yazılmıyor. Servolar son hedef pozisyonunu güç altında
tutmayı sürdürür: sıkışmış kol overload olana kadar bastırır, kapana kısılmış kol elle itilemez.
"Yazılım durdu" ile "kola dokunmak güvenli" aynı şey sayılmış.

### B7 — Durdurma her seferinde 5 sn bekleyip SIGKILL'e düşüyor

`_stop_process()` SIGINT atıp `process.wait()`'i 5 sn bekliyor. Ancak asyncio'da
`Process.wait()`, çocuk ölse bile **stdout borusu kapanmadan** uyanmıyor
(`BaseSubprocessTransport._try_finish` bütün boruların `disconnected` olmasını şart koşuyor).
LeRobot `--display_data=true` ile Rerun görüntüleyicisini ayrı bir süreç olarak başlatıyor ve o
süreç aynı boruyu miras alıyor. Sonuç: çocuk milisaniyeler içinde temiz çıksa bile beklenti
5 sn'lik zaman aşımına düşüyor, ardından SIGKILL gönderiliyor.

Ölçüm — SIGINT'i anında işleyen sahte bir `lerobot-teleoperate` ile, uygulamanın kendi API'si
üzerinden:

| Senaryo | E-stop → işin terminal duruma geçişi |
|---|---|
| Arkada süreç bırakan çocuk (Rerun modeli) | **5,5 sn** |
| Kontrol: yan süreç yok | **0,44 sn** |

E-stop HTTP yanıtı 15–22 ms; gecikmenin tamamı bu yolda. Gerçek `lerobot-teleoperate`
çalıştırıldığında Rerun görüntüleyicisinin ana süreç öldükten sonra da hayatta kaldığı doğrudan
gözlendi. `lerobot-record` için aynı 5 sn'lik pencere daha ağır sonuç doğurur: `dataset.finalize()`
(video kodlama) 5 saniyeden uzun sürer ve SIGKILL onun ortasına düşer.

### B8 — Operatörün iptali "failed" olarak kaydediliyor

Adapter operatör iptalinde `PhysicalExecutionError` fırlatıyor; `JobCoordinator` bunu
`WorkflowCancelled` değil genel `Exception` olarak yakalıyor. İki ölçümde de sonuç
`state=failed, error_code=workflow_failed` oldu. Bilinçli acil durdurma ile kaza audit'te aynı
satıra düşüyor.

### B14 — Güvenlik bayrakları beyana dayalı; gerçek limit hiç gönderilmiyor

`emergency_stop_ready`, `calibration_verified`, `joint_limits_verified` — preflight bunları
yalnızca istekte `true` yazılıp yazılmadığına bakarak geçiriyor. Hiçbir kalibrasyon dosyası,
eklem limiti veya e-stop yolu doğrulanmıyor. LeRobot'un gerçek emniyeti olan
`--robot.max_relative_target` yalnızca çağıran parametre verirse ekleniyor; panelde verecek yer
yok. Yani "joint limits verified" işareti dekoratif.

Uçtan uca denemede yedi preflight kontrolünün yedisi de `pass` verdi, iş onaylandı, komut düştü:

```text
POST /api/jobs -> 200 | state: awaiting_confirmation
   preflight: pass ×7
confirm -> queued
SON DURUM: failed | workflow_failed
HATA: lerobot-teleoperate exited with code 2.
```

### B9 — Hata sebebi yutuluyor

Başarısızlıkta `recent_output` yalnızca başarı yolunda döndürüldüğü için operatöre ulaşan tek
bilgi "exited with code 2" oluyor. LeRobot'un bastığı gerçek sebep
(`invalid choice: 'so_follower'`) hiçbir yerde görünmüyor. Depoyu robotuna takıp deneyen birinin
elinde yalnızca bir çıkış kodu kalır.

---

## 5. Çalışma zamanı ve dayanıklılık bulguları

### B10 — Sabit 900 sn iş zaman aşımı

`timeout_seconds` varsayılanı 900 ve panelden ayarlanamıyor. 20 bölümlük bir kayıt
(20 × 30 sn + reset süreleri) bu sınırı aşar; iş ortadan kesilir ve üstüne B7'deki 5 sn'lik
SIGKILL penceresi biner.

### B11 — `doctor.run()` olay döngüsünü kilitliyor

`/api/summary` her çağrıda `doctor.run()` çalıştırıyor; o da torch'u import edip
`torch.cuda.is_available()` çağırıyor. Panel bu uç noktayı 1,8 saniyede bir yokluyor.

```text
doctor.run() #1: 2680 ms
doctor.run() #2:   15 ms
doctor.run() #3:   13 ms
doctor.run() #4:   14 ms
```

İlk çağrı 2,68 sn boyunca olay döngüsünü bloke ediyor; acil durdurma isteği de aynı döngüde sıra
bekliyor. Yani e-stop'un hızı, birinin daha önce bir sayfa açmış olup olmamasına bağlı.

### B12 — Teleop'ta `--display_data=true` sabit kodlanmış

Kapatma seçeneği yok; her teleoperation işi Rerun penceresi açmaya çalışıyor. Bu bayrak hem
B7'deki 5 sn + SIGKILL davranışını tetikliyor hem de öksüz görüntüleyici süreçleri bırakıyor:
`start_new_session=True` ile süreç grubu ayrılıyor, ama öldürme yalnız doğrudan çocuğa gidiyor.

### B13 — Panel derlenmiş hâlde gelmiyor

`src/hashtag_robotics/web/` depoda yok; `vite build` çıktısı `.gitignore`'da. Uygulama olduğu
gibi başlatıldığında kök sayfa şunu döndürüyor:

```json
{"message": "Frontend assets are not built. Use the API at /docs."}
```

Panel için node + npm + vite kurulumu gerekiyor. "Kur ve aç" senaryosu doğrudan çalışmıyor;
elde yalnız JSON API kalıyor.

---

## 6. Doğruluk ve şeffaflık bulguları

### B15 — Kalibrasyon yedeği/checksum planı var, kodu yok

`docs/HIL_TEST_PLANI_TR.md` T3 adımı "calibration backup + artifact checksum + revision bağlama"
istiyor. Kodda karşılığı yok: `calibration_revision` profildeki bir dizge, "Backing up the active
calibration" ise mock adım listesindeki bir cümle. Kod tabanının tamamında dosya sistemine
dokunan tek yer veri dizini ve SQLite dosyası.

### B16 — Simülasyon sonuçları uydurma, damga yine de "verified"

Kayıt → eğitim → değerlendirme zinciri çalıştırıldığında üçü de saniyeler içinde `completed` oldu:

- kayıt diske hiçbir şey yazmıyor (veri dizini sonunda 76 KB, yalnız `state.db`),
- eğitim `mock://checkpoints/<job_id>` üretiyor,
- değerlendirme başarı oranını `(episodes-1)/episodes`, gecikmeyi sabit 18,4 / 27,9 ms
  döndürüyor.

Üretilen dataset manifest'i `integrity_status="verified"` damgası alıyor. Ürün vitrini olarak
makul, ama panelde "verified" gören biri gerçek bir bütünlük kontrolü yapıldığını sanır.

### B17 — Kamera ve gerçek dataset yüzeyi yok

Canlı görüntü uç noktası yok. `discovery.py` yalnızca seri portları listeliyor; leader/follower
ayrımı, kamera keşfi ve motor seviyesinde doğrulama yok. Dataset'ler diskteki gerçek
LeRobotDataset'ler değil, SQLite'taki manifest satırları. Gerçek kayıt için gereken
`--robot.cameras` yalnızca çağıran parametre verirse ekleniyor; panelde verilecek yer olmadığı
için üretilecek dataset görüntüsüz olurdu.

### B18 — Doctor'ın bakmadığı yerler

Kontrol ediliyor: python sürümü, işletim sistemi, ffmpeg, disk alanı, paket sürümleri,
lerobot/strands-robots çakışması, fiziksel kapı.
Kontrol edilmiyor: seri port izni (`dialout` grubu), udev kuralları, kameralar, kalibrasyon
dosyalarının varlığı, LeRobot konsol betiklerinin PATH'te olup olmadığı (yalnız modülün import
edilebilirliğine bakılıyor). Linux'ta gerçek bir kullanıcının ilk çarpacağı duvar — port izni —
doctor'da hiç görünmüyor.

### B19 — Komut önizlemesi arayüze bağlanmamış

`POST /api/hardware/command-preview` çalışıyor ve üretilecek argüman dizisini döndürüyor; yani
komutun yanlış olduğunu operatöre gösterebilecek tek ekran mevcut. Ancak arayüz bu uç noktayı hiç
çağırmıyor. HIL test planı T3 bu önizlemeyi bir kabul kriteri olarak sayıyor.

### B20 — Uyumluluk iddiası Linux'u kapsamıyor

`docs/UYUMLULUK_MATRISI_TR.md`: doğrulama macOS arm64 geliştirme ortamında yapılmış ve "destek
iddiası olmayan yüzeyler" listesinde açıkça "Ubuntu + CUDA" yazıyor. Bu raporun kurulum tarafında
sorun bulmaması (py3.12 + aarch64 + lerobot 0.6.0 sorunsuz kuruldu) bu iddiadan bağımsız bir
olumlu sonuçtur.

---

## 7. Deponun doğru yaptıkları

Depo kötü yazılmış değil; denenmemiş. Sağlam duran kısımlar:

- **Mimari ayrım net:** LeRobot = donanım, Strands = planlama, uygulama = ürün/iş/güvenlik.
- **İş durum makinesi** (validating → awaiting_confirmation → queued → running → terminal),
  kaynak lease'leri, tek kullanımlık ve parametre-hash'e bağlı onaylar, audit kaydı. Onaydan sonra
  parametre değişirse iş bloke oluyor.
- **SQLite WAL + RLock**, yeniden başlatmada yarım kalan işleri `interrupted` işaretleyip
  lease'leri bırakan kurtarma yolu.
- **Kabuk kullanılmıyor:** komutlar argüman dizisi olarak çalışıyor, string enjeksiyonu yüzeyi
  kapalı. Çıktıda `token=` / `password=` maskesi var.
- `lerobot-train` sözleşmesi doğru.
- MuJoCo modeli kendi çıktısında "validated SO-101 digital twin değildir" uyarısını taşıyor.
- **README dürüst:** "software-only baseline", "fiziksel HIL test sınırına getirildi",
  "doğrulanmış production robot controller değildir", "`HASHTAG_ENABLE_PHYSICAL=true` şu anda
  açılmamalıdır".

Tutmayan tek iddia şu satır: **"Gerçek LeRobot 0.6.0 console-script adapter contract'ları"** —
altı fiziksel sözleşmenin altısı da gerçek 0.6.0 tarafından reddediliyor.

---

## 8. Çalışır hâle gelmesi için gereken minimum iş

Bir sonraki adımı açan iş önce gelecek şekilde:

1. **Tip adlarını düzelt** (`so101_follower` / `so101_leader`) — tek satır, altı komutu birden açar.
2. **`record`/`replay`/`rollout` argümanlarını gerçek şemaya taşı** (`--dataset.*`, rollout için
   `--strategy.*`).
3. **Testleri LeRobot'a sordur:** üretilen argv'yi gerçek konsol betiğine doğrulatan bir sözleşme
   testi. Bu olmadan 1 ve 2 tekrar bozulur.
4. **Kalibrasyon için stdin köprüsü** (PTY) ve panelde bir "ENTER" düğmesi.
5. **Acil durdurmayı fiziksel yap:** süreç grubunu öldür, sonra portlara `Torque_Enable=0` yayınla
   ve geri okuyarak doğrula.
6. **Durdurma yolunu boru bağımlılığından kurtar** (süreç grubu + returncode yoklaması) ve zaman
   aşımını iş türüne göre ayarla.
7. **`doctor.run()`'ı olay döngüsünden çıkar**, böylece acil durdurma kimseyi beklemez.
8. **Panele gerçek modu ekle:** port/profil formu, komut önizlemesi, onay düğmesi.
9. **Derlenmiş paneli yayına koy** (release varlığı veya wheel), node gerektirmeyen kurulum.

1–3 yapılmadan kalan maddelerin hiçbiri ölçülebilir hâle gelmiyor: gerçek kolda ilk hareketi
gören şey 1. maddedir.

---

## Ek — Yeniden üretme

Depo kökünde, `21bf07c` üzerinde:

```bash
# 1) komutları üret
PYTHONPATH=src python -c "
from hashtag_robotics.hardware import LeRobotCommandBuilder
from hashtag_robotics.models import JobCreateRequest, JobKind, TargetMode
p = LeRobotCommandBuilder().build(JobCreateRequest(kind=JobKind.RECORDING, target_mode=TargetMode.REAL,
    parameters=dict(robot_port='/dev/ttyNOPE', robot_id='f', teleop_port='/dev/ttyNOPE2',
                    teleop_id='l', repo_id='x/y', task='pick')))
print(p.executable, *p.arguments)"

# 2) çıkan komutu gerçek lerobot 0.6.0'a ver (sahte port: donanıma dokunmaz)
lerobot-record --robot.type=so_follower ...     # -> invalid choice
lerobot-record --robot.type=so101_follower ...  # -> unrecognized arguments: --repo_id …

# 3) uygulamayı ayağa kaldır ve gerçek iş aç
HASHTAG_ENABLE_PHYSICAL=true PYTHONPATH=src python -m hashtag_robotics serve
```
