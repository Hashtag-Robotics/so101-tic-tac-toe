# SO-101 Hardware-in-the-Loop Test Planı

**Durum:** Fiziksel robotlar bağlanmadan hazırlandı
**Test sahibi:** Mert Özbaş / Hashtag Robotics
**Kural:** Mert robotları bağlamadan ve her hareket adımını açıkça onaylamadan
hiçbir physical actuation yapılmaz.

## 1. Test hedefi

Software-only baseline'ın gerçek Hashtag Robotics SO-101 leader/follower setiyle:

- Cihaz kimliğini doğru çözdüğünü
- Calibration artifact'lerini koruduğunu
- Kamera key'lerini doğru eşlediğini
- Düşük limitli teleop'u güvenli çalıştırdığını
- Dataset kaydettiğini
- Policy compatibility'yi doğru engellediğini
- Stop, disconnect ve emergency stop davranışını

doğrulamak.

İlk HIL oturumunun hedefi eğitim veya autonomous rollout değildir. İlk hedef
yalnızca güvenli discovery, identity, calibration validation ve düşük limitli
teleop'tur.

## 2. Fiziksel riskler

- Leader/follower'ın ters seçilmesi
- Yanlış port
- Yanlış veya eski calibration
- Motor ID/baud uyuşmazlığı
- Beklenmeyen torque-on
- Kolun masa, kablo, kamera veya insana çarpması
- USB disconnect sonrası stale action
- Kamera semantic key farkı
- Yanlış unit/action shape
- Gripper sıkışması
- Control latency/jitter

Bu test planı riskleri azaltır; tüm fiziksel riskleri ortadan kaldırmaz.

## 3. Test alanı hazırlığı

### Mekanik

- Robot sağlam ve düz zeminde sabit.
- Leader ve follower çalışma hacimleri boş.
- Kablolar joint hareket yolunda değil.
- Gripper içinde nesne yok.
- Follower başlangıç pozu kontrollü ve dengeli.
- Kol masa kenarından yeterince uzakta.
- Gerekirse düşük enerjili/yumuşak test nesnesi hazır.

### Elektrik

- Güç adaptörü ve kablolar görsel olarak sağlam.
- USB hub kullanılacaksa yeterli güç sağlıyor.
- Acil güç kesme yolu erişilebilir.
- Kullanıcı güç kablosuna ve E-stop'a aynı anda erişebilir.

### Bilgisayar

- Uyku modu kapalı.
- Gereksiz kamera/serial uygulamaları kapalı.
- Dataset için yeterli disk alanı var.
- Terminal ve dashboard aynı local makinede.

## 4. Yazılım hazırlığı

```bash
cd /path/to/so101-tic-tac-toe
uv sync --extra dev --extra agents --extra sim --extra so101
npm --prefix frontend run build
bash scripts/verify.sh
```

Beklenen:

- Python testleri geçer.
- Frontend build geçer.
- Wheel build geçer.
- LeRobot console scripts bulunur.
- MuJoCo contract testi geçer.

Doctor:

```bash
HASHTAG_DATA_DIR=.local-data \
HASHTAG_ENABLE_PHYSICAL=false \
uv run hashtag-robotics doctor
```

`blocked` sonuç varsa fiziksel teste geçilmez.

## 5. Test kayıt formatı

Her test için kaydedilecekler:

```text
test_id
timestamp
operator
robot_serial
leader_serial
follower_port
leader_port
calibration_revision
camera_mapping
software_versions
result: pass | fail | blocked | aborted
latency/fps
stop_reason
notes
artifact paths
```

Secret veya credential kaydedilmez.

---

# T0 — Software-only final gate

## Adımlar

1. `bash scripts/verify.sh`
2. Dashboard'u physical mode kapalı başlat.
3. Overview, Dataset, Training, Agents ve Simulation sayfalarını aç.
4. Safe simulation job çalıştır.
5. MuJoCo scenario çalıştır.
6. Emergency stop'a bas.

## Kabul kriteri

- Testler geçer.
- Simulation `constraint_violations=0`.
- E-stop aktif job'ları durdurur veya tamamlanmış job'a zarar vermez.
- Physical mode `locked` görünür.

---

# T1 — Read-only device discovery

## Başlangıç durumu

- Follower ve leader USB ile bağlı.
- Motor gücü mümkünse kapalı.
- `HASHTAG_ENABLE_PHYSICAL=false`.

## Adımlar

1. Dashboard'u başlat.
2. Robot Lab → `Cihazları tara`.
3. Serial cihaz listesini kaydet.
4. Gerekirse LeRobot read-only port yardımcısını ayrı çalıştır:

```bash
uv run lerobot-find-port
```

5. Fiziksel USB sök/tak ile hangi portun hangi cihaz olduğunu doğrula.
6. Stable fingerprint ve transient path'i karşılaştır.

## Kabul kriteri

- Leader ve follower portları belirsiz kalmadan çözülür.
- Discovery hiçbir motor hareketi yapmaz.
- Yeniden takıldığında profile eşleme tekrar yapılabilir.
- Belirsiz cihaz otomatik follower seçilmez.

## Blocker

- Aynı fingerprint
- Değişken veya boş serial
- Port permission hatası
- Cihazın bağlantı sırasında reset döngüsü

---

# T2 — Robot ve teleoperator profile

## Adımlar

1. Follower için RobotProfile oluştur.
2. Leader için TeleoperatorProfile oluştur.
3. Hashtag SKU, seri numarası ve hardware revision kaydet.
4. Motor layout'u mevcut ürün QA bilgisiyle karşılaştır.
5. Resource ID'lerini profile bağla.

## Kabul kriteri

- Leader ve follower aynı profile/role olamaz.
- Transient port değişse de product identity korunur.
- Yanlış role seçimi dashboard tarafından uyarılır.

---

# T3 — Calibration backup ve validation

## Fiziksel onay kapısı

Calibration motorları hareket ettirebilir. Mert:

- Çalışma alanını kontrol eder.
- Kolları güvenli başlangıç konumuna getirir.
- Hangi kolun calibration'a gireceğini tekrar doğrular.
- Komut preview'ını inceler.
- Son onayı verir.

## Önce backup

Mevcut LeRobot calibration dosyaları değişmeden önce:

- Dosya yolu
- Checksum
- Robot/teleoperator ID
- Timestamp

ile yedeklenir.

Backup başarısızsa calibration yapılmaz.

## Command preview

API:

```text
POST /api/hardware/command-preview
```

Preview:

- Executable
- Argüman listesi
- Hedef role
- Port
- Calibration ID
- `uses_shell=false`

göstermelidir.

## Test sırası

1. Leader calibration preview.
2. Mert onayı.
3. Leader guided calibration.
4. Artifact checksum ve validation.
5. Follower calibration preview.
6. Mert onayı.
7. Follower guided calibration.
8. Artifact checksum ve validation.
9. Eski backup'ın hâlâ mevcut olduğunu doğrula.

## Kabul kriteri

- Yanlış role/port ile job blocked.
- Calibration sessiz overwrite yapmaz.
- Başarısız işlemde önceki artifact korunur.
- Yeni revision profile'a bağlıdır.

---

# T4 — Kamera discovery ve semantic mapping

## Başlangıç

Motor actuation kapalı kalabilir.

## Adımlar

1. LeRobot camera discovery:

```bash
uv run lerobot-find-cameras opencv
```

2. Her kamerayı fiziksel olarak kapat/aç veya hareket ettirerek kimliğini çöz.
3. `front`, `wrist`, `top` semantic role ata.
4. Resolution/FPS seç.
5. Gerçek FPS, dropped frame ve latency ölç.
6. Reconnect sonrası mapping'i tekrar doğrula.
7. Dataset feature preview:

```text
observation.images.front
observation.images.wrist
```

## Kabul kriteri

- Camera index kalıcı identity kabul edilmez.
- Preview kapanınca kamera release edilir.
- Dataset key açıkça görünür.
- Policy'nin beklediği key yoksa rollout blocked.
- No-camera teleop yolu kamera eksikliği nedeniyle bloke olmaz.

---

# T5 — E-stop ve disconnect testi

Bu test teleop'tan önce tamamlanır.

## E-stop

1. Motor gücü kapalıyken dashboard E-stop çalıştır.
2. Audit event üretildiğini doğrula.
3. Physical worker'da stop yolunu doğrula.
4. Güç kesme yoluna fiziksel erişimi doğrula.

## USB disconnect

İlk kez motor gücü kapalı:

1. Follower USB bağlantısını kes.
2. Device disconnect event bekle.
3. Lease'in ve job state'in güvenli kapandığını doğrula.
4. Reconnect sonrası identity tekrar çözülmeli.

## Kabul kriteri

- E-stop agent runtime'dan bağımsız.
- Browser kapansa bile local worker stop edebilir.
- Disconnect sonrası stale action gönderilemez.
- Lease TTL sonrası temizlenir.

---

# T6 — İlk düşük limitli teleoperation

## Zorunlu ön koşullar

- T1–T5 geçti.
- Leader/follower identity doğrulandı.
- Calibration revision doğrulandı.
- E-stop çalıştı.
- Workspace boş.
- Fiziksel kullanıcı onayı alındı.

## Physical mode

Yalnız test oturumu için:

```bash
HASHTAG_DATA_DIR=.local-data \
HASHTAG_ENABLE_PHYSICAL=true \
HASHTAG_OPEN_BROWSER=false \
uv run hashtag-robotics serve
```

Bu environment açıkken uygulama kapatılmadan robot başı terk edilmez.

## İlk parametreler

- Minimum pratik `max_relative_target`
- Kısa timeout
- Kamera zorunlu değil
- Düşük hareket hızı
- Boş gripper
- Kullanıcı E-stop üzerinde

## Sıra

1. Command preview.
2. Dashboard preflight.
3. Resolved robot/leader/ports/calibration özeti.
4. Mert'in tek kullanımlık approval'ı.
5. 1–2 saniyelik küçük leader hareketi.
6. Follower yön ve eklem eşleşmesi kontrolü.
7. Stop.
8. Joint delta, loop FPS ve latency kontrolü.
9. Her joint için ayrı küçük hareket.
10. Gripper en son.

## Anında abort koşulları

- Ters joint yönü
- Beklenmeyen joint hareketi
- Titreşim veya motor sesi
- Joint limit yaklaşımı
- Loop latency artışı
- USB reset
- Kolun mekanik zorlanması
- E-stop gecikmesi

## Kabul kriteri

- Altı feature doğru joint'e gider.
- `max_relative_target` aşılmaz.
- Stop komutundan sonra yeni action uygulanmaz.
- p50/p95 latency kaydedilir.
- Disconnect safe stop üretir.

---

# T7 — Gerçek recording ve replay

T6 geçmeden yapılmaz.

## Recording

1. Yumuşak ve düşük riskli görev seç.
2. Tek kamera ile başla.
3. `task`, FPS, episode/reset süreleri doğrula.
4. İlk olarak 1 episode kaydet.
5. Dataset manifest ve video kontrolü.
6. State/action shape `[6]`.
7. Kamera key `observation.images.front`.
8. İkinci episode ancak birinci doğrulanırsa.

## Replay

Replay autonomous actuation'dır.

1. Aynı robot profile.
2. Aynı calibration revision.
3. Aynı action shape/unit.
4. Empty workspace.
5. Düşük relative target.
6. Mert approval.
7. Tek episode.

## Kabul kriteri

- Yarım episode geçerli sayılmaz.
- Video/frame timestamp uyumu doğru.
- Retry eski episode'u bozmaz.
- Replay farklı calibration ile blocked.
- Stop/E-stop çalışır.

---

# T8 — Training ve gerçek policy rollout

Bu adım ilk fiziksel HIL oturumunun zorunlu parçası değildir.

## Training

1. Dataset integrity `verified`.
2. LeRobot `repo_id` doğrulanır.
3. ACT baseline preset.
4. Önce kısa smoke training.
5. Checkpoint ve processor manifest çıkar.
6. Training config ve metrics kaydet.

## Rollout

Gerçek policy rollout ancak:

- Dataset/policy feature mapping
- Camera key
- Processor/normalization
- Action shape
- Calibration
- Joint limit
- Control frequency
- Policy horizon/chunking

doğrulandıktan sonra.

## İlk rollout

- 1 episode
- Kısa duration
- Düşük relative target
- Boş/yumuşak görev
- E-stop üzerinde kullanıcı
- Video + joint telemetry

## Kabul kriteri

- Policy output action shape doğru.
- Stale action uygulanmaz.
- Inference timeout safe stop üretir.
- Episode sonucu pass/fail/aborted ayrılır.
- Latency ve outcome distribution kaydedilir.

---

# 6. Test sonrası kapanış

1. Bütün active job'lar terminal state'te.
2. Resource lease listesi boş.
3. Robot güvenli poza getirilmiş.
4. Torque/power kapalı.
5. `HASHTAG_ENABLE_PHYSICAL` kaldırılmış.
6. Dashboard software-only modda yeniden başlatılmış.
7. Calibration ve dataset artifact'leri yedeklenmiş.
8. Audit ve diagnostics bundle alınmış.

## Diagnostics

```text
GET /api/system/diagnostics
```

Paylaşmadan önce secret ve kişisel veri açısından manuel incelenir.

# 7. HIL exit kriteri

Platform ancak şu koşullarda “SO-101 physical baseline geçti” olarak
etiketlenebilir:

- Leader/follower identity tekrarlanabilir.
- Calibration backup/restore doğrulandı.
- Kamera mapping reconnect sonrası doğru.
- Düşük limitli teleop geçti.
- Stop, E-stop ve USB disconnect geçti.
- Tek episode recording ve replay geçti.
- Hiçbir unknown feature mapping yok.
- Test sonucu ve metrikler kalıcı kaydedildi.

Bu kriterlerden biri eksikse fiziksel baseline tamamlanmış sayılmaz.
