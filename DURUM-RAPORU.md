# SO-101 Control Plane — durum raporu

**Tarih:** 1 Ağustos 2026
**Dal:** `hil-verified-control-plane`, taban `a370c70`
**Sürüm:** `hashtag-robotics` 0.2.0
**Boyut:** 13.582 satır kaynak, 8.869 satır test (37 dosya), 18 iş türü

Bu rapor deponun bu daldan sonraki hâlini özetler: neyin gerçek donanımda
kanıtlandığını, neyin yalnızca yazılımda doğrulandığını ve neyin hâlâ açık
olduğunu ayırarak.

---

## 1. Nereden nereye

`21bf07c` bir iskeletti: iş türleri tanımlıydı, komutlar üretiliyordu, ama hiçbiri
bir kola bağlanmıyordu. Bu dal o iskeleti gerçek donanımda çalışan bir sisteme
dönüştürüyor. Çalışma bir Jetson Orin Nano üzerinde, iki gerçek SO-101 kolu
takılıyken yürütüldü.

| Alan | Önce | Şimdi |
|---|---|---|
| Fiziksel yol | komut üretiliyor, koşmuyor | kurulum→kalibrasyon→teleop→kayıt→replay gerçek kolla geçti |
| Simülasyon | yok | MuJoCo sahnesi leader ile sürülüyor, gerçek kayıtla aynı biçimde dataset yazıyor |
| Veri hattı | dataset kaydı uydurma sonuç dönüyordu | topla→yönet→Hub uçtan uca, durdurulabilir işler |
| Güvenlik | e-stop bayrak | mandallı, yeniden başlatmayı aşan, kolu enerjisiz bıraktığını **okuyarak** doğrulayan zincir |
| Kapı | yok | her push'ta iki iş: lint+test+panel+wheel, ve LeRobot'lu tam süit |

---

## 2. Gerçek donanımda kanıtlananlar

Aşağıdakiler Orin üzerinde, kollar takılıyken ölçüldü. Her fiziksel adım
operatörün tek kullanımlık onayıyla başladı.

- **Teleoperation:** 29,9 Hz, `max_relative_target` uygulanmış, temiz kapanış.
- **Kayıt + replay:** 1 bölüm / 597 kare / 30,00 fps; replay otonom koştu.
- **Acil durdurma:** kolu gerçekten enerjisiz bırakıyor ve bunu servo okumasıyla
  doğruluyor — sessiz bir bus başarı sayılmıyor. Torch yüklenmesini beklemediği
  için tepki süresi 3.522 ms'den 16 ms'ye indi.
- **Cihaz keşfi:** iki kol + kamera salt-okunur olarak bulundu, hiçbir motor
  enerjilenmedi.

**GPU yok.** Orin'de `torch.cuda` yolu bu oturumda ölçülmedi; eğitim ve rollout
tarafı hâlâ CPU varsayımıyla duruyor.

---

## 3. Simülasyon

Sahne gerçek SO-101'i çiziyor ve leader ile sürülüyor. Önemli olan çıktısının
biçimi: sim kaydı gerçek kayıtla **aynı şemayı** yazıyor (`<joint>.pos`,
normalize birimler, HWC görüntü), dolayısıyla ikisi birlikte eğitilebiliyor.
Şema uyuşmazlığı hiçbir hata fırlatmadan politikanın daha az öğrenmesine yol
açtığı için bu testlerle sabitlendi.

Oturumda bulunan ve giderilen bir hata: `shoulder_lift` eşlemesinde 43 derecelik
sapma. Sebebi, eski bir kalibrasyona göre ölçülmüş varsayılan bir affine
dönüşümün, kol yeniden kalibre edildikten sonra da uygulanmaya devam etmesiydi.
Giderildikten sonra sim ve gerçek aralıklar altı eklemin altısında örtüşüyor.
`SimArm.apply` artık sınır dışı komutu kırpıyor ve kayda **kırpılmış** değeri
yazıyor; öncesinde MuJoCo ne reddediyor ne kırpıyordu.

---

## 4. Veri hattı ve ajan yüzeyi

Topla → yönet → Hub zinciri uçtan uca çalıştı ve 86 bölüm / 36.482 kare ile
doğrulandı. Birleştirme, bölüm çıkarma ve Hub'a gönderim artık durdurulabilir
işler. Aynı kaydı iki kez içeren birleştirme reddediliyor; birleşmeyen iki kaydın
hangi alanda ayrıştığı alt anahtarına kadar söyleniyor.

Ajan tarafında plan artık tek bir eylem değil sıralı bir zincir: adımlar arası
sonuç taşınıyor ve koşu, insan onayı isteyen adımda duruyor. Katalog bayatlaması
kalıcı olarak kapatıldı — her iş türü ya katalogda ya da gerekçesiyle
`UNEXPOSED_JOB_KINDS`'te; yeni bir tür eklemek testi kırıyor.

---

## 5. Güvenlik sözleşmesi

- İstemci port/id/limit **gönderemiyor**. Sunucu bunları `robot_profile_id`den
  çözüyor, `ResolvedTargets` işe ve onaya yazılıyor. Onay hem parametre hem hedef
  hash'ine bağlı: kol başka bir porta düşerse iş `targets_changed` ile bloklanıyor.
- Acil durdurma `flags` tablosunda mandallanıyor ve yeniden başlatmayı aşıyor;
  açmak için `/api/safety/clear-estop` ya da `hashtag-robotics clear-estop`.
- Hub'a gönderim geri alınamaz bir eylem olduğu için insan onayı olmadan geçmiyor.
  Kimlik bilgisi yoksa iş bloke oluyor; bu davranış ayrı bir testle sabitlendi
  (önce kapıyı doğrulayan hiçbir şey yoktu).

---

## 6. Kapılar

`.github/workflows/ci.yml` her push'ta iki iş koşuyor:

| İş | Kapsam |
|---|---|
| **Lint, tests, dashboard and wheel** | ruff (check + format), pytest, `tsc -b`, `npm run build`, wheel'in kaynakla birebir olduğu, temiz ortama kurulum |
| **Full suite against LeRobot 0.6** | her extra kurulu, tüm süit |

İki ayrıntı deneyerek bulundu ve iş dosyasında gerekçesiyle yazılı:

- **`MUJOCO_GL=osmesa` + `libosmesa6-dev` şart.** Ekransız bir runner'da MuJoCo'nun
  varsayılan GLFW backend'i hata fırlatmıyor, süreci abort ediyor (SIGABRT, exit
  134). Sonuç, eksik kurulum gibi değil çökmüş süit gibi okunuyor.
- **Hızlı iş bilerek torch kurmuyor.** LeRobot gerektiren 6 test
  `conftest.requires_lerobot` ile işaretli; hızlı işte atlanıyor, yavaş işte
  gerçekten koşuyor. Yavaş iş elle tutulan bir dosya listesi değil **tüm süiti**
  koşar — bir testin hızlı işte atlanıp yavaş işte hiç koşmaması tam olarak böyle
  bir listeden doğuyordu.

---

## 7. Paketleme

`opencv-python-headless` ve `huggingface-hub` artık açıkça bildiriliyor. İkisi de
koddan import ediliyordu ama hiçbir extra'da tanımlı değildi; `so101` extra'sındaki
lerobot'un peşinden tesadüfen geliyorlardı. Pratik sonucu: `--extra sim` ile kuran
biri ilk render'da `ModuleNotFoundError` alıyordu. `huggingface-hub` tabanı 1.0,
çünkü lerobot 0.6 öyle istiyor — daha düşüğü `so101` extra'sını çözülemez yapıyor.
opencv'nin headless varyantı seçildi: kod hiç pencere açmıyor (yalnız `imencode` ve
`VideoCapture`) ve lerobot da aynı varyantı çekiyor, dolayısıyla iki `cv2` yan yana
gelmiyor.

`scripts/check_wheel.py` wheel'i geldiği ağaca karşı denetliyor: her modül byte
byte, sürüm, ve panelin yüklediği varlıklar. Eski kapı "`web/index.html` wheel'de
mi?" diye soruyordu; `index.html` her zaman wheel'de olduğu için o kapı iki modül
hiç girmemişken ve sürüm hâlâ 0.1.0 derken de yeşil kalmıştı.

---

## 8. Bu dalda koşulan doğrulamalar

```
ruff check + ruff format --check     temiz (66 dosya)
pytest                               438 passed, 8 skipped
npm run typecheck (tsc -b)           temiz
scripts/build-package.sh             wheel 0.2.0, kaynakla birebir
                                     (28 modül + 3 panel varlığı)
```

Atlanan 8 testin tamamı LeRobot'un yokluğundan: 6'sı `requires_lerobot`, 1'i
`draccus` (komut sözleşmesi), 1'i LeRobot'un kontrol tablosuna karşı çapraz
denetim. Hepsi `Full suite against LeRobot 0.6` işinde koşuyor.

---

## 9. Bilinmesi gerekenler

- **Derlenmiş panel depoda izlenmiyor.** `src/hashtag_robotics/web/`
  `.gitignore`'da; CI `npm run build` ile üretiyor ve wheel'e koyuyor. Node'u
  olmayan makineler (Jetson) için `scripts/build-dashboard.sh` var: esbuild ile
  paketler, ama **tip kontrolü yapmaz**. Oradan çıkan paket o makineye aittir,
  release'e değil.
- **Panelin tip kapısı kolay kaçıyor.** Node'suz bir makinede geliştirilirken
  `tsc` hiç koşmuyor ve arayüz tipleri sunucunun gönderdiği alanların gerisinde
  kalıyor. Bu dalın hazırlığında iki kez oldu; ikisini de CI'daki
  `Dashboard typecheck` adımı yakaladı. Panele dokunan bir değişikliğin bu adımı
  geçtiğini görmeden birleştirilmemesi gerekiyor.
- **`ruff format --check` ayrı bir kapı.** `ruff check` temizken biçimlendirme
  kapısı iki kez düştü; ikisi ayrı şeyler.
- **GPU yolu ölçülmedi.** Yukarıda §2.
- Fiziksel işler `physical.enabled` kapalıyken doğru gerekçelerle bloklanıyor;
  donanımsız bir makinede süit tam koşar.
