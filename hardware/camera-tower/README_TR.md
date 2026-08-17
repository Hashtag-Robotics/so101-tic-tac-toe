# SO-101 32×32 Kamera Kulesi — Orijinal Kılıflı Oynar Baş V4

Bu sürüm üç adet `200 mm` mast modülüyle nominal `600 mm` kamera yüksekliği
sağlar. Orta modül çıkarıldığında aynı bağlantılarla yaklaşık `400 mm` kurulum
elde edilir. Parçalar PLA Silk+ için geniş yüzeyleri tablaya gelecek şekilde ve
desteksiz basılacak yönde hazırlanmıştır.

V4'te kamera kılıfı V2 geometrisine tamamen geri döndürüldü. PCB yuvası, dört M2
bağlantısı, lens açıklığı, kablo çentiği ve iki küçük menteşe kulağı değişmedi.
Açı hareketi yalnızca logolu üst mastın ucundaki güçlendirilmiş oynar başta olur.
Büyük PLA-CF vida/somun ve elmas delikler kaldırılmıştır.

## Elindeki parçalar için basılacak dosya

V2 kamera kılıfını daha önce bastıysan yalnız bunu bas:

- `so101_cam_tower_silk_v4_tilt_head_upgrade_ams_p2s.3mf` — logolu yeni üst
  mast; Filament 1 ana PLA Silk+, Filament 2 kırmızı PLA Silk+

Aynı plakanın eski bağlantıları bozmayan takma adı:

- `so101_cam_tower_silk_hinge_upgrade_ams_p2s.3mf`

Eski kamera kılıfını, tabanı, `bottom` ve `middle` mastları yeniden basma. V3'ün
büyük PLA-CF vida/somun dosyaları `deprecated-v3-threaded-hinge/` klasörüne
taşındı; onları kullanma.

## Sıfırdan tam set

- `so101_cam_tower_silk_mast_logo_ams_p2s.3mf` — üç mast; en sağdaki üst
  modülde kırmızı Hashtag Robotics inlay
- `so101_cam_tower_silk_base_camera_plate.3mf` — taban ve değişmeyen V2 kamera
  kılıfı
- `so101_cam_tower_silk_mast_plate.3mf` — logosuz üç mast alternatifi

Tek tek ana CAD çıktıları:

- `so101_cam_tower_silk_bottom.stl`
- `so101_cam_tower_silk_middle.stl`
- `so101_cam_tower_silk_top.stl`
- `so101_cam_tower_silk_base.stl`
- `so101_cam_tower_silk_camera.stl`
- `so101_cam_tower_silk_top.step`
- `so101_cam_tower_silk_camera.step`
- `so101_cam_tower_silk_assembly.step`

Parametrik kaynak `so101_cam_tower_silk.py` dosyasındadır.

## Oynar baş mekanizması

- Kamera kılıfı: ilk basılan V2 parça; geometri değiştirilmedi
- Pivot: gerçek dairesel `Ø3.4 mm` delik
- Üst mast başı: `16 mm` genişlik, `16 mm` boy ve arkaya uzanan güçlendirilmiş
  omuz
- Bağlantı: bir adet metal `M3 × 40 mm` cıvata ve M3 nyloc somun
- Kilitleme: kamera açısını elle ayarla, sonra M3 somunu kılıfın iki kulağı
  merkez başı kavrayana kadar sık
- PLA-CF baskı vidası: kullanılmıyor

CAD çarpışma kontrolünde mevcut kamera kılıfı `-90°…+90°` arasında 5° adımlarla
çarpışmasız geçti. USB kablosuna yük bindirmemek için gerçek kullanımda yaklaşık
`±70°` içinde kal.

Somunu kameranın kendi ağırlığıyla dönmeyeceği kadar sık. PLA Silk+ kulaklarda
beyazlama başlayacak kadar sıkma; kuvveti PCB'ye değil yalnız basılı menteşe
kulaklarına uygula.

## Kamerayı bağlama

Mevcut V2 kamera kılıfındaki PCB montajını değiştirme:

1. Kamera PCB'sini lens `18 mm` merkez açıklığından bakacak şekilde dört küçük
   yükseltiye yerleştir.
2. Mevcut dört `M2 × 8–10 mm` vida ve M2 somunla PCB'yi sabitle.
3. Kılıfın iki küçük kulağını yeni üst mast başının iki yanına geçir.
4. Dairesel delikleri hizala ve `M3 × 40 mm` cıvatayı geçir.
5. Kadrajı ayarla, M3 nyloc somunu sık ve USB kablosunu açık arka kanaldan indir.

Kamera arayüzü:

- PCB: `32 × 32 mm`
- M2 delik merkezleri: `28 × 28 mm`
- Baskı deliği: `2.4 mm`
- Lens açıklığı: `18 mm`

## Kırmızı Hashtag Robotics logosu

Logo baskı plakasındaki en sağ mast modülündedir. Kaynak dosya adında tarihsel
olarak `bottom_logo` geçse de fiziksel parça üst masttır. Wordmark `115 mm`
uzunluğunda, `0.30 mm` kalınlaştırılmış ve `0.40 mm` derinliğinde iki katmanlık
flush inlay olarak hazırlanmıştır. Dış yüzeyden normal yönde okunur.

- Filament 1: ana PLA Silk+ rengi
- Filament 2: kırmızı PLA Silk+
- `Auto Arrange`: kullanma
- Logo ve ana gövde: tek çok-parçalı nesne

## Kule montajı

1. `bottom` modülünü tabandaki 34×14 mm sokete yerleştir ve `M3 × 50 mm` ile
   kilitle.
2. `bottom` geçmesini `middle` yuvasına oturt ve `M3 × 40 mm` ile kilitle.
3. `middle` ile `top` arasını ikinci `M3 × 40 mm` ile kilitle.
4. Mevcut kamera kılıfını yeni oynar başa üçüncü `M3 × 40 mm` ile bağla.
5. Tabanı dört M5 vida veya iki sağlam masa kelepçesiyle sabitle.

600 mm kullanımda mast kilitleme cıvataları ve masa sabitlemesi olmadan kuleyi
kullanma.

## PLA Silk+ baskı ayarları

- Nozul: `0.4 mm`
- Katman: `0.20 mm`
- Duvar: `3`
- Üst/alt katman: `4`
- Dolgu: `%15 gyroid`
- Destek: kapalı
- Brim: kapalı
- Yön: 3MF içindeki yönü değiştirme; geniş yüzeyler Z=0'dadır

P2S doğrulama sonuçları:

- Yalnız V4 logolu üst mast: yaklaşık `38.40 g`, `1 sa 13 dk`
- Üç parçalı logolu mast plakası: yaklaşık `120.40 g`, `3 sa 23 dk`
- Taban + V2 kamera kılıfı: yaklaşık `52.17 g`, `1 sa 36 dk`
- Tüm plakalar: `support=off`, uyarı yok, manifold geometri

## Güvenlik

- Taban serbest duruş için tasarlanmadı; masaya vidala veya kelepçele.
- Kamera ve kabloyu SO-101 hareket zarfından uzak tut.
- İlk kadraj ve açı kontrolünü robot motorları kapalıyken yap.
- PLA Silk+ standart PLA+/PETG kadar tok değildir; çatlak veya beyazlama görülen
  menteşe kulağını kullanma.

