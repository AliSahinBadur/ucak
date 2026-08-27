# CATIA → Adams kütle/CG hattı: nasıl çalışıyor

Bu belge kademeli: Seviye 0 beş dakikada kullanmanız için, Seviye 4 kodu
değiştirmeniz için. Aradaki her seviye bir öncekini varsayar.

---

# Seviye 0 — Beş dakikada

## Ne yapıyor

CATIA V5'te **açık olan** araç montajını tarar, alt yapı bazında kütle ve
ağırlık merkezi çıkarır, araç/varyant/revizyon olarak saklar, önceki
revizyonla karşılaştırır ve onayınızdan sonra Adams/Car için `.cmd` dosyası
yazar. Mümkün olduğunda atalet değerlerini de çıkarır ve saklar.

Elle hazırladığınız şu tablonun yerine geçer:

```
ALT YAPI | KÜTLE [kg] | X [mm] | Y [mm] | Z [mm]
```

## Kurulum

Mühendisin bilgisayarında, CATIA'nın kurulu olduğu makinede:

```
64-bit Python 3.10+
pip install pywin32
```

Skill klasörünü kopyalayın, bir çalışma klasörü açın ve örnek ayar
dosyalarını oraya kopyalayın:

```
copy assets\subassembly_map.example.json   <ws>\subassembly_map.json
copy assets\transform_profile.example.json <ws>\transform_profile.json
copy assets\adams_map.example.json         <ws>\adams_map.json
```

## CATIA olmadan deneyin

Her komut `--source fake` ile sentetik bir araç üzerinde çalışır. Önce bunu
yapın; hattın davranışını CATIA lisansı harcamadan öğrenirsiniz.

```
python -m cmc selftest
python -m cmc calibrate --source fake --length 100 --width 200 --height 300 --density 7850
python -m cmc extract   --source fake --vehicle ARAC --variant BASE --revision R01
python -m cmc rollup
python -m cmc show
```

Sentetik araç bilerek 2046.402 kg olarak kurgulandı ve tekerlekler aks
ağacının **içinde** duruyor, yani çift sayım tuzağını gerçekten içeriyor.
`show` çıktısı şuna benzer:

```
ALT YAPI                   KUTLE [kg]         X [mm]         Y [mm]         Z [mm]
Tekerlek Grubu                248.000      1900.0000         0.0000      -340.0000
Ön Aks                        210.000       510.0000       -13.3333      -323.3333
...
* Arka Aks + Süspansiyon      498.489      3302.1915        -6.0182      -323.7625
TOPLAM                       2046.402      2003.7667        -6.1181      -250.7992
```

`Ön Aks` 210 kg: tekerlekler dahil değil. `Tekerlek Grubu` 248 kg: dördü de
tam bir kez sayılmış.

## Gerçek CATIA ile

1. Kalibrasyon parçasını CATIA'da açın, `calibrate` çalıştırın (makine başına
   bir kez).
2. Araç montajını açın, `extract` → `rollup` → `diff` → `preview`.
3. Önizlemeyi okuyun. Kabul ediyorsanız `export --approve <kod>`.

---

# Seviye 1 — Boru hattı

Yedi komut, her biri tek bir JSON nesnesi basar ve bir sonrakini söyler.

| Komut | Ne yapar | Ürettiği dosya |
|---|---|---|
| `doctor` | Ortam kontrolü, `gen_py` temizliği | — |
| `calibrate` | Birimleri ve atalet konvansiyonunu **ölçer** (ilk sefer) | `units_profile.json` |
| `attach` | CATIA oturumuna bağlanır, doğrular (sonraki seferler) | `session.json` |
| `extract` | Ağacı tarar, yaprakları kök eksene taşır | `runs/<id>/components.json` |
| `rollup` | Alt yapı bazında toplar, üç invariantı doğrular | `runs/<id>/rollup.json` |
| `diff` | Önceki revizyonla karşılaştırır | `runs/<id>/diff.json` |
| `preview` | Değişiklik önizlemesi + onay kodu | `runs/<id>/preview.txt` |
| `export` | Onaydan sonra Adams komut dosyası | `runs/<id>/export.cmd` |

## Çalışma klasörü

```
<ws>/
  units_profile.json       calibrate üretir, elle düzenlenmez
  subassembly_map.json     hangi parça hangi alt yapıya ait
  transform_profile.json   CATIA -> Adams dönüşümü + doğrulama noktaları
  adams_map.json           alt yapı -> Adams parça adı
  memory.sqlite            revizyon hafızası
  runs/<id>/               her ölçümün ham ve işlenmiş çıktıları
```

## Hafıza

`memory.sqlite` üç tablo tutar:

- `measurement` — araç, varyant, revizyon, kaynak dosya yolu ve SHA-256'sı,
  CATIA sürümü, work mode, birim profili, ölçen kullanıcı, tarih, toplam
  kütle ve CG
- `bucket` — alt yapı bazında kütle, CG, atalet
- `component` — **her yaprak parça**: yol, parça numarası, alt yapı, kütle,
  CG, atalet, malzeme, yoğunluk, işaretler

Parça seviyesini saklamanın sebebi: altı ay sonra "arka aks neden 12 kg
arttı" sorusunun cevabı bir parça adı olmalı, omuz silkme değil.

Kaynak dosyanın SHA-256'sı sayesinde "aynı dosya mı ölçülmüş" sorusu
tartışmasız cevaplanır.

## Atalet neden şimdiden saklanıyor

Mevcut Adams akışınız yalnız kütle ve CG kullanıyor. Yine de Ixx, Iyy, Izz,
Ixy, Ixz, Iyz her ölçümde saklanıyor, çünkü eski bir revizyonu yeniden
ölçmek genellikle imkânsızdır: CATProduct çoktan ilerlemiştir.

---

# Seviye 2 — Tasarım kararları

## Neden LLM hiçbir sayı hesaplamıyor

Bir dil modeli 16 satırlık bir tabloyu toplayabilir ve genellikle doğru
yapar. "Genellikle" burada yeterli değil, çünkü hata sessiz: 2046.402 yerine
2046.042 yazan bir tablo tamamen makul görünür.

Dolayısıyla bütün aritmetik `cmc` içinde ve her sonucu bağımsız bir kaynağa
karşı sınanıyor. Ajanın işi komut çalıştırmak, uyarıları iletmek ve insana
karar sordurmak.

Küçük modellerde (4B sınıfı) bu ayrım daha da katı olmalı:

- Ajan ham ağacı hiç görmez. `components.json` diske yazılır, ajana sadece
  özet gider. 2000 parçalık JSON'u küçük bir modelin bağlamına sokarsanız
  hem bozar hem uydurur.
- Uyarılar en fazla 5 tane gösterilir, toplam sayı ayrı alanda. `warnings_total`
  ve `warnings_shown` bu yüzden ayrı.
- Bütün kullanıcı metinleri script içinde hazır Türkçe cümlelerdir. Model
  cümle kurmaz, kopyalar.
- Komutlar sabit ve az argümanlıdır. Model komut kuramaz, kopyalar.

## Neden her komut aynı JSON zarfını basıyor

```json
{
  "status": "ok",
  "step": "rollup",
  "message_tr": "9 alt yapı hesaplandı. Toplam 2046.402 kg ...",
  "next_command": "python -m cmc diff --run 2026-08-27T09-04-54",
  "warnings_total": 2,
  "warnings_shown": 2,
  "warnings": [ ... ]
}
```

Model yalnız iki alanı okumak zorunda: `message_tr` ve `next_command`.
Sıradaki adımı hatırlamak zorunda değil, script söylüyor. Uzun bir akışta
küçük modelin unutacağı ilk şey sıradır.

Hata durumunda `status: "error"`, `code` ve `hint_tr` gelir, `next_command`
boştur. Skill kuralı: hata gördüğünde dur. Kendi başına çözmeye çalışan bir
ajan, sessizce yanlış veri üreten bir ajandır.

## Neden onay kapısı token'lı

`preview` yazılacak dosyanın tamamının SHA-256 özetinden 16 haneli bir kod
üretir. `export` bu kodu ister, içeriği yeniden üretir ve özetleri
karşılaştırır.

Model kodu uyduramaz; sadece kullanıcının gördüğü önizlemeden kopyalayabilir.
Önizlemeden sonra veri değiştiyse kod tutmaz ve export durur.

Gerekçe: `part modify rigid_body mass_properties`, bir araç dinamiği
mühendisinin elle ayarlamış olabileceği değerlerin üzerine yazar. Model
çalışmaya devam eder, sadece başka türlü davranır. Bu tür hatalar aylar sonra
fark edilir.

## Neden konvansiyonlar veri, kod değil

Koordinat dönüşümü, birim ölçekleri ve atalet konvansiyonu JSON dosyalarında.
Kodda gömülü değil. Sebep: bunların doğru değeri kuruluma, sürüme ve araç
programına göre değişir. Kodda gömülü bir konvansiyon, bir gün sessizce
yanlış olur ve kimse nereye bakacağını bilmez.

## Çift sayım neden kontrol listesiyle çözülmüyor

"Tekerlekleri iki kez saymadığımızı kontrol et" bir prosedürdür ve
prosedürler unutulur. Bunun yerine alt yapı eşlemesi bir **partisyon** olarak
tanımlandı: her yaprak occurrence tam olarak bir alt yapıya gider, ve
atanmamış tek bir parça varsa toplam üretilmez.

Tekerlek o zaman ya aksın içindedir ya tekerlek grubunun, ikisi birden
olamaz. Yapı gereği.

Eşleşme öncelik kuralı:

1. `**` içermeyen desen, içerene yeğ tutulur
2. sonra daha çok harf içeren desen
3. sonra dosyadaki yazım sırası

Bu yüzden `/Vehicle/*/Wheel_*` deseni `/Vehicle/FrontAxle.1/**` desenini
yener ve tekerlekler akstan çıkar.

Kararın nerede alındığı görünür olsun diye `rollup.json` içinde
`bucket_conflicts` listesi tutulur: birden fazla alt yapıya uyan her parça,
kazanan desenle birlikte listelenir. Sentetik araçta bu liste tam olarak dört
satırdır, dört tekerlek.

---

# Seviye 3 — Matematik

## Dönüşüm zinciri

`Analyze.GetGravityCenter` bir alt üründe çağrıldığında sonuç o ürünün kendi
eksen takımındadır. Kök eksene taşımak için occurrence dönüşümleri
zincirlenir:

```
p_parent = R_child · p_child + T_child
```

kökten yaprağa birleştirilerek:

```
(R, T) = (R_parent · R_child,  R_parent · T_child + T_parent)
```

`Position.GetComponents` 12 sayı verir: ilk 9'u rotasyon matrisi **sütun
sütun** (x, y, z eksenlerinin görüntüleri), son 3'ü öteleme.

Öteleme de bir uzunluktur, dolayısıyla birim ölçeğiyle çarpılır. Bunu
unutmak, parçaları doğru ama montajı 1000 kat yanlış yerde gösterir.

## Ağırlık merkezi

```
M   = Σ mᵢ
CG  = Σ mᵢ · rᵢ / M
```

Yalnız yapraklardan. Ara düğümlerin `Analyze` sonuçları toplamaya hiç
karışmaz; sadece çapraz kontrol için okunur.

## Atalet: tek bir kanonik biçim

Hat içinde atalet daima **tensör** olarak, CG'ye göre saklanır:

```
T = [[ Ixx, Ixy, Ixz ],
     [ Ixy, Iyy, Iyz ],
     [ Ixz, Iyz, Izz ]]        Ixy = -∫xy dm
```

Bu biçim `T' = R T Rᵀ` ile döner ve paralel eksen teoremini olağan haliyle
sağlar. CATIA'dan gelirken ve Adams'a giderken sınırlarda çevrilir. Tek bir
iç konvansiyon, iki sınır çevirisi: işaret hatası için tek bir yer kalır ve
orası test edilir.

Paralel eksen (Steiner):

```
T_O = T_G + m(|r|² I − r ⊗ r)
T_G = T_O − m(|r|² I − r ⊗ r)
```

Bileşenler halinde, `r = (x, y, z)`:

```
Ixx_O = Ixx_G + m(y² + z²)
Ixy_O = Ixy_G − m·x·y
```

Birleştirme: her parçanın tensörü ortak CG'ye taşınır ve toplanır.

```
T_toplam = Σ [ T_i(kendi CG'sinde) + m_i(|d_i|² I − d_i ⊗ d_i) ],  d_i = r_i − CG
```

## Kalibrasyon çözücüsü

Bilinen blok: L × W × H mm, bir köşesi orijinde, yoğunluk ρ.

```
m           = L·W·H·ρ / 10⁹
CG          = (L/2, W/2, H/2)
Ixx_G       = m(W² + H²)/12
Ixx_orijin  = m(W² + H²)/3
∫xy dm      = m·L·W/4      (orijine göre)
```

Ölçekler oranlardan çözülür ve ondalık bir kata "yapıştırılır"; %1'den fazla
sapma varsa uyarı verilir, çünkü bu genellikle blok tanımının yanlış
girildiğini gösterir.

### Dejenerasyon: köşegen terimleri referans noktasını çözemez

Bu, hattı yazarken kendi testimin yakaladığı hata ve saklanmaya değer:

Bir köşesi orijinde olan blok için, **her üç eksende de**

```
I_orijin / I_cg = (1/3) / (1/12) = 4
```

Yani iki hipotez de köşegen verisine mükemmel uyar ve aradaki sabit 4 katı,
bilinmeyen birim ölçeği sessizce yutar. "Köşegenler tutarlı mı" diye bakan
bir çözücü, referans noktasını yazı tura ile seçer ve dört kat atalet
hatasını hiç fark etmez.

Köşegen dışı terimlerde bu dejenerasyon yok: eksenlere paralel bir bloğun
CG'sinde sıfırdırlar, köşesinde değil. Ve

```
∫xy dm / Ixx
```

oranı **boyutsuz**, yani ölçeği bilmeden referans noktasını verir. İşareti de
konvansiyonu verir:

- oran ≈ 0 → CATIA CG'ye göre raporluyor
- oran ≈ +beklenen → orijine göre, çarpımlar `∫xy dm` biçiminde
- oran ≈ −beklenen → orijine göre, çarpımlar tensör biçiminde

`inertia_ref = "cg"` çıkarsa işaret bu parçadan belirlenemez ve atalet
aktarımı kapatılır. Kütle ve CG akışı etkilenmez.

---

# Seviye 4 — Doğrulama ve genişletme

## Üç invariant

`rollup` şunları zorlar, ihlalde durur:

1. **Her yaprak tam olarak bir alt yapıda.** Atanmamış parça varsa yolları
   listelenir ve toplam üretilmez.
2. **Alt yapı toplamı = CATIA'nın montaj kütlesi** (göreli tolerans 10⁻⁶).
3. **Alt yapılardan geri hesaplanan CG = CATIA'nın montaj CG'si**
   (0.001 mm).

2 ve 3 bizim taramamızdan bağımsız kaynaklardır; değerli olmalarının sebebi
budur. Atlanmış bir dal, unutulmuş bir dönüşüm veya birim hatası bu iki
kontrolden geçemez.

## Elle hesaplanabilir testler

`python -m cmc selftest` sekiz test çalıştırır. Her biri hattın sessizce
yanlış olabileceği bir yola karşılık gelir:

| Test | Neyi yakalar |
|---|---|
| `steiner_round_trip` | paralel eksen işaret hatası |
| `rotation_of_a_diagonal_tensor` | tensör döndürmede eksen karışması |
| `two_point_masses` | dambıl `Izz = 2md²`, birleştirme hatası |
| `transform_chain` | dönüşüm bileşiminde sıra hatası |
| `mirror_is_not_a_rotation` | determinantı −1 olan "dönüşüm" profili |
| `calibration_recovers_known_scales` | çözücünün karışık birimleri geri getirmesi |
| `walk_reproduces_box_inertia` | uçtan uca atalet: kitap formülüyle aynı mı |
| `fake_vehicle_invariants` | tekerlek tam bir kez sayılıyor mu |

Yeni bir makinede sayılara güvenmeden önce çalıştırın.

## Hata modları

| Kod | Ne oldu | Ne yapılır |
|---|---|---|
| `E_ATTACH_NOT_FOUND` | CATIA oturumu bulunamadı | CATIA açık mı; yetki seviyeleri eşleşiyor mu |
| `E_WORKMODE` | Montaj sıfır kütle | Design mode, cache kapalı, malzeme atanmış mı |
| `E_CALIB_CG_MISMATCH` | Blok tanımı ölçümle tutmuyor | L/W/H ve köşe orijinde mi |
| `E_UNMAPPED` | Atanmamış parça | `subassembly_map.json` deseni ekle |
| `E_DUPLICATE_PATH` | Aynı yol iki kez | Montajda yinelenen instance adları |
| `E_INVARIANT_MASS` / `E_INVARIANT_CG` | Bağımsız kontrol düştü | Veri kullanılamaz; tarama hatalı |
| `E_LANDMARK_MISMATCH` | Dönüşüm doğrulanamadı | Eksen eşlemesi yanlış |
| `E_UNMAPPED_BUCKET` | Alt yapının Adams karşılığı yok | Eşle veya `ignore` listesine al |
| `E_APPROVAL` / `E_STALE_APPROVAL` | Onay geçersiz | Önizlemeyi tekrar üret ve göster |

## Küçük modelle çalıştırma (Qwen 4B sınıfı)

- thinking kapalı, `temperature 0`
- Q5_K_M veya üstü nicemleme; Q4 altında araç çağrısı formatı gözle görülür
  bozuluyor
- kod yazma yetkisi verme; izinli tek araç `cmc` alt komutları
- JSON şema kısıtı (GBNF vb.) kullanabiliyorsan kullan
- `SKILL.md` kısa tutuldu; `references/` dosyaları modele yüklenmez, insan
  içindir

## Nereyi değiştirirsiniz

| İstek | Dosya |
|---|---|
| Adams komut biçimi farklı | `cmc/export.py`, `render_cmd` |
| Yeni alt yapı / farklı ağaç | `subassembly_map.json` (kod değişmez) |
| Farklı koordinat konvansiyonu | `transform_profile.json` (kod değişmez) |
| Diff eşikleri | `cmc/diff.py`, `MASS_THRESHOLD_KG`, `CG_THRESHOLD_MM` |
| Invariant toleransları | `cmc/rollup.py`, `MASS_REL_TOL`, `CG_ABS_TOL_MM` |
| Excel/CSV çıktısı | yeni komut; `rollup.json` zaten hazır veri |

Hesaplama katmanına (`geom.py`, `walk.py`, `rollup.py`) dokunuyorsanız
`selftest` çalıştırın ve gerekirse yeni bir elle-hesaplanabilir test ekleyin.

## Bilinen sınırlar

- Atalet konvansiyonu `inertia_ref = "cg"` çıkarsa çarpım terimlerinin
  işareti eksenlere paralel bir blokla belirlenemez; atalet aktarımı kapanır.
  Çözüm, CG'sinde çarpım terimleri sıfır olmayan asimetrik bir kalibrasyon
  parçası eklemektir.
- `.cmd` biçimi kendi Adams sürümünüzle bir kez doğrulanmalıdır.
- Malzeme adı okuma sürümler arasında değişir; okunamaması hata değil, uyarı
  olarak işlenir. Kütle yine de doğrudur, çünkü kütle malzeme adından değil
  `Analyze.Mass`'tan gelir.
