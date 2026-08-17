# Uyumluluk Matrisi

**Son doğrulama:** 30 Temmuz 2026
**Kanal:** development

## 1. Doğrulanan ortamlar

### 1.1 Linux geliştirme ve HIL makinesi (birincil)

**Ubuntu 24.04.4 LTS · x86_64 · kernel 6.8 · Wayland/GNOME**

| Bileşen | Sürüm | Sonuç |
|---|---|---|
| Python | `3.12.3` | Geçti |
| Node.js / npm | `24.12.0` / `11.6.2` | Frontend build geçti |
| uv | `0.11.26` | Sync/build geçti |
| FFmpeg | `6.1.1` | Bulundu |
| LeRobot | `0.6.0` | Import, 9 console script ve draccus parser contract'ı geçti |
| Torch | `2.11.0` | Import geçti |
| OpenCV | `4.13.0` (headless) | Kamera probe ve MJPEG akışı geçti |
| MuJoCo | `3.10.0` | Contract simulation geçti |
| Strands Agents | `1.48.0` | Import/API contract geçti |
| Strands Robots | Kurulmadı | Bilinen LeRobot conflict nedeniyle (bkz. §3) |

**Bu makineye özgü iki not:**

- **Wayland oturumu global klavye yakalayamaz.** LeRobot'un `TerminalKeyListener`
  dışındaki tuş yolları bu oturumda çalışmaz; bu yüzden fiziksel komutlar PTY
  üzerinden sürülür ve operatör tuşları `POST /api/jobs/{id}/input` ile gönderilir.
  Doctor bunu `session.keyboard` uyarısı olarak raporlar.
- **Seri port erişimi `dialout` grubu ister.** Kullanıcı 30 Temmuz 2026'da gruba
  eklendi; oturum yenilenene kadar komutlar `sg dialout -c '...'` ile sarılmalıdır.

### 1.2 macOS arm64 (23 Temmuz 2026 anlık görüntüsü)

Python `3.12.11`, Node `24.6.0`, uv `0.8.14`, FFmpeg `7.1.1`, LeRobot `0.6.0`,
Torch `2.11.0`, MuJoCo `3.10.0`, Strands Agents `1.48.0` ile doğrulanmıştı.
Fiziksel yüzey (PTY, seri port, kamera) bu makinede **tekrar doğrulanmadı**.

### 1.3 Jetson Orin Nano — kasıtlı olarak farklı

Orin'de çalışan ortam Python `3.10` + LeRobot `0.4.4` + `strands-robots 0.4.1`'dir
ve **bilinçli olarak yükseltilmemiştir**. Bu uygulama `>=3.12` ve LeRobot `0.6`
ister; Orin'e ayrı bir py3.12 ortamı kurmak JetPack 6.2 için py3.12 torch wheel'i
bulmayı gerektirir. Karar ve gerekçe: [Kararlar ve Riskler](KARARLAR_VE_RISKLER_TR.md) K-014.

Bu matris geliştirme makinesi doğrulamasıdır; bütün müşteri işletim sistemleri
için destek garantisi değildir.

## 2. Doğrulanan LeRobot console scripts

Proje environment'ında mevcut olduğu doğrulanan komutlar:

```text
lerobot-find-port
lerobot-find-cameras
lerobot-setup-motors
lerobot-calibrate
lerobot-teleoperate
lerobot-record
lerobot-replay
lerobot-train
lerobot-rollout
```

Hashtag adapter yalnız argüman listesi kullanır; shell string üretmez.

## 3. Strands Robots kararı

Yayımlanmış `strands-robots==0.4.1`, LeRobot için `<0.6.0` aralığı tanımlar.
Platformun doğruladığı LeRobot ise `0.6.0`'dır.

Bu nedenle:

- Stable environment'a `strands-robots==0.4.1` eklenmedi.
- Doküman/main özelliği installed capability kabul edilmedi.
- Agent runtime için bağımsız `strands-agents==1.48.0` kullanıldı.
- Strands Robots daha sonra uyumlu release veya açık commit pin'i ile ayrı
  preview channel'da test edilecek.

## 4. Package extras

```text
hashtag-robotics
├── core
├── [agents]  Strands Agents
├── [sim]     MuJoCo
├── [so101]   LeRobot 0.6
└── [dev]     test/lint araçları
```

Geliştirme doğrulaması:

```bash
uv sync --extra dev --extra agents --extra sim --extra so101
```

Core wheel, ağır training/sim paketlerini zorunlu olarak kurmaz.

## 5. Release compatibility kuralı

Her upgrade'te:

1. Yeni lock resolve edilir.
2. `hashtag-robotics doctor` çalıştırılır.
3. LeRobot console script listesi doğrulanır.
4. Typed command builder testleri geçer.
5. MuJoCo contract test edilir.
6. Frontend build edilir.
7. Wheel temiz Python 3.12 environment'ına kurulur.
8. HIL gereken değişiklik release blocker olarak işaretlenir.

Adım 1-7 `.github/workflows/ci.yml` içinde otomatiktir. `software` işi ruff,
test, typecheck, wheel ve temiz ortama kurulumu her push'ta koşar; ağır
`lerobot-contract` işi LeRobot'un kendi parser'ıyla argüman sözleşmesini
ayrı olarak doğrular, böylece Torch indirmesi hızlı sinyali geciktirmez.

## 6. Destek iddiası olmayan yüzeyler

Bu sürüm henüz şu ortamları doğrulamadı:

- Windows + Feetech
- Ubuntu + CUDA
- Intel macOS
- RealSense
- ROS 2
- Isaac/Newton
- Uzak GPU gerçek inference
- Strands Robots preview

Doctor'da görünmesi destek garantisi değildir; test matrisi sonucu ayrıca
gereklidir.
