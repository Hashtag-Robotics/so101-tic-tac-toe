# Strands ile SmolVLA Tic-Tac-Toe Agent

Bu agent modeli yeniden eğitmez. Varsayılan olarak
`HashtagRobotics/smolvla-tic-tac-toe-games-1-15-120k` reposunun revision-pinned yerel 120K
checkpoint'ini, eğitimde kullanılan 18 sabit görev üzerinden fiziksel olarak değerlendirir.

## Sorumluluk ayrımı

- Strands vision agent: iki kamerayı kontrol eder, boş tahtada X'e kilitlenir, ilk hamleyi yapar,
  insanın O karşı hamlesini beş saniyede bir gözler, yasal/stratejik cevabı seçer,
  rollout'u canlı izler ve sonucu sınıflandırır.
- SmolVLA: yalnızca seçilen eğitim prompt'u için robot action'larını üretir.
- Deterministik controller: agent/human rolleri, değişmeyen sembol, tek-hücre insan hamlesi, oyun
  fazı, dolu hücre, koordinat dönüşümü, tek aktif rollout, checkpoint, zaman aşımı, kayıt ve fiziksel
  onay kurallarını uygular.
- İnsan operatör: ilk hareketten önce süpürme alanını ve E-STOP'u kontrol edip o oyun oturumunu
  terminalden bir kez onaylar. Fiziksel E-STOP'un yerini hiçbir yazılım aracı tutmaz.

Agent'a genel `shell`, Python, servo veya joint aracı verilmez. Agent yalnızca
`play_tic_tac_toe_move(model_cell, board_camera, rationale)` aracını görür. Controller kilitli
sembolü hücreyle birleştirir, kesin eğitim prompt'unu üretir ve alttaki
`ttt-rollouts/X-1..X-9` veya `ttt-rollouts/O-1..O-9` launcher'larından birini seçer.

## Koordinat sözleşmesi

Top kamera, robot/model görev koordinatına göre 180 derece dönüktür:

| Top kamera hücresi | SmolVLA prompt/model hücresi |
|---:|---:|
| 1 | 9 |
| 2 | 8 |
| 3 | 7 |
| 4 | 6 |
| 5 | 5 |
| 6 | 4 |
| 7 | 3 |
| 8 | 2 |
| 9 | 1 |

Örneğin agent top kamera görüntüsünün sol üstüne X koymak isterse `X-9`, yani
`put the red X in the bottom right cell` eğitim görevini çağırır. Bu dönüşüm tool açıklamasında
ve controller hedef doğrulamasında sabittir; LLM'nin serbest koordinat üretmesine bırakılmaz.

## Kurulum

Repo kökünde:

```zsh
uv pip install --python .venv/bin/python -e '.[agents,dev,so101]'
```

Genel `strands-agents-tools` bu akışın bağımlılığı değildir. Üretim runner'ı da Strands Robots'un
genel amaçlı Robot tool'unu agent'a vermez; local policy ve fiziksel güvenlik sözleşmesi tek domain
tool'un arkasında kalır.

Opsiyonel native Strands Robots kontratını donanım olmadan kurup incelemek için:

```zsh
uv sync --extra dev --extra strands-robots
uv run python scripts/inspect_ttt_strands_robots.py
```

Bu komut `Robot` oluşturmaz, model indirmez, seri port aramaz ve kamera açmaz. Inspector mevcut
`HashtagRobotics/smolvla-tic-tac-toe-games-1-15-120k` repo/revision/checkpoint sözleşmesini,
provider `lerobot_local`, policy type `smolvla`, 50-action chunk,
`top -> observation.images.camera1`, `wrist -> observation.images.camera2` ve `strict_keys=True`
olarak raporlar. Policy loader yalnız mevcut revision-pinned fetch scriptinin indirdiği yerel
checkpoint dizinini kabul eder; serbest veya unpinned Hub modeli yüklemez.

Native sim factory açıkça `mode="sim"` ve `mesh=False` kullanır; `auto` moda izin verilmez. Native
gerçek donanım factory'si kalıcı fiziksel ayar ile çağrı-bazlı açık onayı birlikte ister ve bu masa
üzerinde HIL doğrulanana kadar `agent.py` tarafından seçilmez. Pinli Strands Robots `0.5.1`
`lerobot_local` yüklemesi için `STRANDS_TRUST_REMOTE_CODE=1` environment gate'ini ister; proje bunu
kendiliğinden set etmez.

## Standart Strands provider ayarı

Vision ve tool-use destekleyen bir modeli standart Strands provider yüzeyinden seç. Örneğin yerel
Ollama için:

```zsh
export HASHTAG_AGENT_MODEL="ollama:<vision-model>"
export HASHTAG_AGENT_MODEL_HOST="http://localhost:11434"

# Provider'a gönderilen opsiyonlar JSON olmalıdır.
export HASHTAG_AGENT_MODEL_OPTIONS='{"temperature":0}'

# Bu kalıcı gate tek başına robotu çalıştırmaz. Python giriş noktası --physical ekler
# ve ilk fiziksel hamlede oyun oturumu için tek seferlik insan onayı gerekir.
export HASHTAG_ENABLE_PHYSICAL=true

# İsteğe bağlı ajan sınırları.
export HASHTAG_TTT_AGENT_MOVE_TIMEOUT_SECONDS=120
export HASHTAG_TTT_AGENT_START_TIMEOUT_SECONDS=300
export HASHTAG_TTT_AGENT_SAVE_TIMEOUT_SECONDS=120
export HASHTAG_TTT_AGENT_MAX_MOVE_OBSERVATIONS=24
export HASHTAG_TTT_AGENT_MAX_TURNS=96

# Donanım profilini repoya ekleme:
export HASHTAG_TTT_HARDWARE_CONFIG=".local-data/ttt-hardware.json"
```

Bedrock ve Anthropic de mevcut Strands runtime tarafından desteklenir. İlgili provider client'ını
Strands dokümantasyonuna göre kur ve provider'ın standart SDK credential zincirini kullan. Credential'ı
komut satırına, `.env` dosyasına, repo dosyasına veya loga yazma; OS secret store kullan.

Provider'ın vision image bloklarını ve tool calling'i gerçekten desteklemesi gerekir. Provider/model
hatası ilk agent turunda, robot hareketinden önce durmalıdır. Buna rağmen provider erişilebilirliği
fiziksel güvenlik kapısı değildir; deterministic controller ve operatör onayı aynen uygulanır.

## Ön kontrol

Bu komut model çağrısı, kamera açma veya robot hareketi yapmaz:

```zsh
python agent.py --inspect
```

Çıktıda şunların doğru olması gerekir:

- `launcher_count: 18`
- `checkpoint_present: true`
- `camera_helper_executable: true`
- doğru HF repo revision ve checkpoint yolu
- seçtiğin Strands model ayarı
- Ollama kullanıyorsan doğru local provider host'u

## Fiziksel çalıştırma

Repo kökünden sanal ortamı ayrıca aktive etmeden çalıştır:

```zsh
python agent.py
```

Giriş dosyası proje `.venv` Python'ını otomatik seçer, `--physical` seçeneğini ekler ve varsayılan
olarak `games-1-15 / 120000` modelini seçer.

Strands agent başlayınca terminal şunu sorar:

```text
Agent'a doğal dille ne yapmak istediğini söyle:
```

`Benimle XOX oyna` gibi doğal bir istek ver. Agent kendi kendine oyun başlatmaz. Otomasyon için aynı istek
`--command "XOX oyna"` ile verilebilir.

Games 1–5 80K baseline'a açıkça dönmek gerekirse
`--model-variant games-1-5-80k --checkpoint 080000` birlikte verilir. Model variant belirtilmezse
120K Games 1–15 local modelinden çıkılmaz.

İlk agent hamlesinde terminal bu oyun oturumu için tek seferlik onay ister:

```text
FİZİKSEL OYUN OTURUMU | checkpoint 120000
İlk SmolVLA hamlesi: <agent'ın seçtiği X hücresi ve eğitim prompt'u>
'Bu oyun boyunca denetimli otomatik robot hamlelerini onaylıyorum' yaz:
```

Tam eşleşme verilmezse robot süreci başlamaz. Bu onaydan sonra aynı oyun içindeki hamleler tekrar
sorulmaz. İnsan hamlesinden sonra controller, elin robotun doğrudan hareket yolundan çekildiğini iki
ayrı kamera gözleminde en az iki saniye arayla doğrulamadan agent sırasını açmaz. Görüntüde uzakta bir
elin bulunması tek başına acil durdurma sebebi değildir; yakın temas veya çarpışma riski E-STOP
sözleşmesini korur.

`no_motion`, kavrama başarısızlığı, `dropped_piece` veya `unclear` sonucunda üst kamera tahtanın
değişmediğini doğrularsa controller aynı mantıksal hamle için en fazla üç otomatik retry planlar.
Her retry öncesinde tam tahta yeniden okunur ve iki temiz workspace görüntüsü gerekir. Retry sırasında
agent başka hücre seçemez. Yanlış hücre, yanlış parça, değişmiş tahta veya üç retry sonunda
başarısızlık normal hamle akışını durdurur.

XOX Strands agent'ına `emergency_stop` tool'u verilmez ve `finish_active_move` içinde `unsafe` veya
`aborted` sonucu kabul edilmez. Görüntüde insan eli ya da elde tutulan nesne bulunması agent için
yalnızca tanı verisidir; aktif rollout'u sonlandırmaz. Dashboard emergency stop, Ctrl-C/Ctrl-D,
watchdog teardown ve fiziksel E-STOP operatör tarafında bağımsız olarak aktif kalır.

## Agent'ın çalışma döngüsü

1. Seçilen standart Strands provider ve vision-capable model başlatılır.
2. Açık insan komutundan sonra robot hareket etmeden iki kameradan güncel snapshot alır. İki kameradan
   biri okunamazsa oyun başlamaz.
3. Top kamera tahtasını `.../.../...` biçiminde çözer ve boş olduğunu doğrular.
4. Controller agent'ı X'e, insanı O'ya kilitler ve ilk hamleyi agent yapar; move tool sembol
   parametresi kabul etmez, dolayısıyla agent O hareketi seçemez.
5. Boş board doğrulandıktan sonra agent ilk hücreyi kendi XOX stratejisiyle dokuz boş hücre arasından
   seçer. Varsayılan merkez veya hard-coded açılış hamlesi yoktur.
6. Agent model/robot koordinatında 1–9 hücresini tek move tool'a verir. Controller kilitli sembolle
   18 sabit launcher'dan doğru olanı deterministik olarak seçer.
7. Controller oyun fazını, kilitli sembolü, son onaylı tahtayı ve hedef hücrenin boşluğunu tekrar kontrol
   eder; ilk fiziksel hamlede oyun oturumu onayı ister, sonraki hamlelerde tekrar sormaz.
8. Seçilen launcher, revision-pinned checkpoint ile başlar ve kayıt alır.
9. Rollout kameraları açıkken agent ikinci kamera handle'ı açmaz; LeRobot'un canlı `top.jpg` ve
   `wrist.jpg` relay dosyalarını okur.
10. Agent hareket sırasında 2–3 saniye aralıklarla sonucu izler; başarı, yanlış hücre, yanlış parça,
   hareketsizlik, düşürme veya belirsizlik olarak kaydeder.
11. Başarılı agent hamlesinden sonra insanı bekler ve iki kamerayı beş saniyede bir kontrol eder.
12. Tahta değişmediyse beklemeye devam eder. Tam bir boş hücre insan sembolüne değiştiğinde
    `acknowledge_human_move` controller tarafından doğrulanır; silinen/çoklu/yanlış sembollü değişim
    robot sırasını açmaz.
13. Agent ancak bundan sonra bir sonraki hamlesini düşünür ve aynı döngü oyun sonuna kadar sürer.

## Tanı kayıtları

Her çalıştırma aşağıdaki dizine yazılır:

```text
.local-data/ttt-agent-sessions/<session-id>/
├── audit.jsonl
├── observations/
│   ├── observation-001-top.jpg
│   └── observation-001-wrist.jpg
├── moves/<attempt-id>/
│   ├── live/top.jpg
│   ├── live/wrist.jpg
│   └── terminal.log
└── strands-trace.json
```

`strands-trace.json` içindeki kamera byte'ları dosyaya gömülmez; yalnızca byte uzunlukları ve ayrı
snapshot yolları tutulur. Her hamle için şunlar kalıcıdır:

- checkpoint/revision
- exact training task
- agent'ın önce/sonra tahta transkripsiyonu
- model ve top-kamera hücre eşlemesi
- agent rationale ve outcome
- hareket süresi ve gözlem sayısı
- rollout dataset/log yolları
- terminaldeki error/RTC/camera incident özeti

## Bilinen sınırlar

- Tahta hücrelerinin X/O olarak okunması vision agent'ın yargısıdır. Controller biçimi, kilitli rolleri,
  son onaylı tahta farkını, tek-hücre insan hamlesini ve dolu hedefi doğrular fakat bağımsız klasik-CV
  doğrulayıcısı değildir. Belirsizlikte hareket etmemesi system prompt ile zorunlu tutulur.
- Bu agent mevcut SmolVLA/rollout davranışını ölçer; daha önce görülen non-guided 50-action chunk
  geçiş problemini düzeltmez. Bu özellikle korunmuştur ki checkpoint davranışı ile execution-pipeline
  davranışı aynı kayıt üzerinde teşhis edilebilsin.
- Her tool task'e ait eğitim başlangıç joint pozuna gider, fakat agent oyunu mevcut fiziksel tahta ile
  sürdürür. Terminal logunda eğitim preset referansı bulunabilir; agent mevcut tahtayı değiştirmez.
- Bir model provider image tool-result bloklarını veya tool calling'i desteklemiyorsa agent fiziksel
  harekete başlamadan hata vermelidir. Böyle bir modeli yalnızca metin modeli olarak kullanma.
- Strands Robots native SO-101/SmolVLA adaptörü opsiyonel olarak mevcuttur; fakat stock hardware
  kamera yolu OpenCV device/index bekler. Mevcut AVFoundation UID, recorder, başlangıç pozu, chunk,
  terminal log ve E-STOP davranışıyla HIL eşdeğerliği henüz kanıtlanmadığından production runner'ı
  değiştirmez. Geçiş ancak aynı 18 görev üzerinde kontrollü karşılaştırma sonrasında yapılacaktır.
