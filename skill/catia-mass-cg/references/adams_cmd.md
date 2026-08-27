# Adams/Car aktarımı

## Üretilen komut biçimi

Her alt yapı için iki komut yazılır: CG marker'ının konumu ve parçanın kütle
özellikleri.

```
! Arka Aks -> .vehicle.ges_rear_axle.gel_beam
marker modify &
   marker_name = .vehicle.ges_rear_axle.gel_beam.cm &
   location = 2800.625000, -9.375000, -353.750000
part modify rigid_body mass_properties &
   part_name = .vehicle.ges_rear_axle.gel_beam &
   mass = 320.000000 &
   ixx = ... & iyy = ... & izz = ... &
   ixy = ... & izx = ... & iyz = ... &
   cm_marker = .vehicle.ges_rear_axle.gel_beam.cm
```

**İlk kullanımdan önce kendi Adams sürümünüzün komut referansıyla
doğrulayın.** Sürümler arasında argüman adları eklendi ve değişti. Sitenizin
kullandığı biçim farklıysa `cmc/export.py` içindeki `render_cmd`
fonksiyonunu düzenleyin; hesaplama katmanına dokunmanız gerekmez.

Adams'ta CG, parçanın `cm` marker'ı ile tanımlanır. Bu yüzden marker'ın
konumu ayrıca yazılır ve `cm_marker` argümanı onu işaret eder.

## Koordinat dönüşümü

```
p_adams = R · p_catia + t
```

`R` işaretli permütasyon matrisi olmalı, determinantı **+1**. Determinant -1
ayna dönüşümüdür ve sağ el koordinat sistemini bozar; `transform.load` bunu
reddeder.

Konvansiyonu ezberden yazmayın. Araç programları arasında orijinin yeri ve
X'in yönü değişir, ve yanlış işaret sessizce çalışan bir model üretir.
Bunun yerine profili **doğrulayın**: koordinatı hem CATIA'da hem Adams'ta
bilinen en az iki nokta seçin (tipik olarak ön ve arka tekerlek merkezi),
`landmarks` listesine yazın. `preview` her çalıştığında profil bu noktalarla
sınanır ve 1 mm'den fazla sapma varsa export durur.

İki nokta gerekir çünkü tek nokta yanlış eksen yönünü yakalayamaz. İki nokta
arasındaki mesafe her iki sistemde aynı çıkmıyorsa eşleme yanlıştır.

## Atalet

Adams, atalet değerlerini CG'ye göre (yani `cm` marker'ında) bekler. Hat
içinde atalet her zaman **tensör** biçiminde ve CG'ye göre saklanır:

```
T = [[ Ixx, Ixy, Ixz ],
     [ Ixy, Iyy, Iyz ],
     [ Ixz, Iyz, Izz ]]        Ixy = -∫xy dm
```

Bu biçim `T' = R T Rᵀ` ile döner ve paralel eksen teoremini olağan haliyle
sağlar. CATIA'dan gelirken ve Adams'a giderken sınırlarda dönüştürülür.

`transform_profile.json` içindeki `adams_product_of_inertia_sign`:

- `1` → Adams `ixy` girdisi `∫xy dm` bekliyor (yaygın varsayım)
- `-1` → Adams `ixy` girdisi tensörün köşegen dışı terimini bekliyor

Bu değeri kendi sürümünüzün komut referansından doğrulayın. Doğrulamanın
pratik yolu: bilinen ve asimetrik bir parçayı Adams'a yükleyip Adams'ın
raporladığı atalet değerlerini elle hesapladığınızla karşılaştırmak.

Kalibrasyon atalet konvansiyonunu çözemediyse `.cmd` dosyasına atalet satırı
yazılmaz; yerine nedenini söyleyen bir yorum satırı konur. Kütle ve CG
aktarımı normal şekilde devam eder.

## Onay kapısı

`preview` yazılacak dosyanın tamamının SHA-256 özetinden bir onay kodu
üretir. `export` bu kodu ister ve içeriği yeniden üretip özetini
karşılaştırır. Önizlemeden sonra veri değişmişse kod tutmaz ve export
`E_STALE_APPROVAL` ile durur.

Bunun sebebi bürokrasi değil: `mass_properties` komutu, bir araç dinamiği
mühendisinin elle ayarlamış olabileceği değerlerin üzerine yazar ve hata
sessizdir. Model çalışmaya devam eder, sadece başka türlü davranır.

Onay kodu uydurulamaz; sadece kullanıcının gördüğü önizlemeden kopyalanabilir.
