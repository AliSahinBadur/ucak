# CATIA V5 otomasyon tuzakları

Bu dosya insan içindir. Ajanın okumasına gerek yok; hata mesajları zaten
gerekli yönlendirmeyi taşıyor.

## İçindekiler

1. Bağlanma
2. Sürüm bağımsızlığı
3. Birimler
4. Design / Visualization mode
5. Dönüşüm zinciri
6. Atalet
7. Malzeme ve yoğunluk
8. Performans

---

## 1. Bağlanma

CATIA V5 otomasyonu Windows COM üzerinden çalışır ve **çalışan bir oturuma**
bağlanır. Uzaktan, servis olarak veya farklı bir masaüstü oturumundan
bağlanılamaz. Agent, mühendisin bilgisayarında, CATIA ile aynı kullanıcı
oturumunda çalışmak zorundadır.

```python
import pythoncom
from win32com.client import dynamic
catia = dynamic.Dispatch(pythoncom.GetActiveObject("CATIA.Application"))
```

Bağlanamama nedenleri, sıklık sırasına göre:

| Belirti | Gerçek neden | Çözüm |
|---|---|---|
| `GetActiveObject` bulamıyor | CATIA yönetici olarak açık, agent değil (veya tersi) | İkisini de aynı yetkiyle başlatın |
| Aynı hata, yetki aynı | Farklı kullanıcı oturumu / RDP oturumu | Aynı oturumda çalıştırın |
| Bağlanıyor, property'ler yok | `gen_py` erken bağlama kalıntısı | `doctor` bunu temizler |
| `ImportError: win32com` | pywin32 yok veya 32-bit Python | 64-bit Python + `pip install pywin32` |

## 2. Sürüm bağımsızlığı (R2021 - R2026)

Bu aralıkta V5Automation arayüzünde kırılma yok. Kırılan şey ortam:

- **Erken bağlama kullanmayın.** `win32com.client.gencache.EnsureDispatch`
  veya `makepy` ile üretilmiş sarmalayıcılar bir type library sürümüne
  çakılır ve başka bir release'de çalışmaz. `dynamic.Dispatch` kullanın.
- **`gen_py` klasörünü temizleyin.** Başka bir araç makepy çalıştırdıysa
  kalıntı, dinamik bağlamayı gölgeleyebilir.
- **64-bit Python.** R2021 ve sonrası tamamen 64-bit.
- **Sürüm bilgisini dallanma için kullanmayın.** `SystemConfiguration.Version`
  ve `Release` bazı kurulumlarda yok. Bu değerler sadece kayıt için
  toplanır; davranış her zaman ölçümle belirlenir.

## 3. Birimler

En pahalı tuzak. `Analyze` üyelerinin birimi ne dokümantasyondan ne de
kullanıcı arayüzü ayarlarından güvenilir şekilde çıkarılabilir. Bir kurulumda
`Volume` m³, `GetGravityCenter` mm dönebilir.

Çözüm tahmin değil ölçüm: `calibrate` komutu ölçüleri ve yoğunluğu bilinen
bir bloğu okur, beklenen değerlerle karşılaştırır ve ölçek katsayılarını
çözer. Katsayı ondalık bir kata (1, 1000, 10⁶ ...) oturmuyorsa uyarı verir,
çünkü bu genellikle blok tanımının yanlış girildiği anlamına gelir.

**Kalibrasyon parçası:** L × W × H mm dikdörtgen blok, kenarları eksenlere
paralel, **bir köşesi parça orijininde**, tek ve bilinen malzeme.

Köşenin orijinde olması şart: CG orijinde olursa uzunluk ölçeği çözülemez ve
atalet referans noktası belirlenemez.

## 4. Design / Visualization mode

Visualization (cgr) modunda geometri yüklenmez, `Analyze.Mass` sessizce 0
döner. Sonuç: hatasız çalışan, tamamen yanlış bir tablo.

`ApplyWorkMode` enum değeri sürümler arasında güvenilir biçimde
belgelenmediği için kod adayları sırayla dener ve **sonucu doğrular**:
mod uygulandıktan sonra kök montaj sıfırdan büyük kütle raporlamıyorsa o
aday reddedilir. Hiçbiri tutmazsa `E_WORKMODE` verilir.

Ayrıca Tools > Options > Infrastructure > Product Structure > Cache
Management açıksa parçalar cgr olarak yüklenir; kapatılmalıdır.

Kullanılan mod her ölçümde `meta.json` ve veritabanına yazılır. "Bu ölçüm
hangi modda alınmış" sorusu sonradan cevaplanabilir olmalı.

## 5. Dönüşüm zinciri

`Analyze.GetGravityCenter` bir alt üründe çağrıldığında sonuç **o ürünün
kendi eksen takımındadır**. Kök eksene taşımak için occurrence dönüşümleri
kökten yaprağa zincirlenmelidir:

```python
arr = VARIANT(VT_ARRAY | VT_BYREF | VT_R8, [0.0]*12)
product.Position.GetComponents(arr)
c = arr.value        # ilk 9: rotasyon (sütun sütun), son 3: öteleme
```

`p_parent = R · p_child + T`, her seviyede birleştirilerek.

Bu adım atlanırsa tek tek parçalar doğru görünür, montaj CG'si yanlış çıkar.
`rollup` bunu yakalar: alt yapılardan geri hesaplanan CG, CATIA'nın kendi
montaj CG'siyle 0.001 mm içinde tutmak zorundadır.

**Not:** `GetComponents` gibi dizi döndüren çağrılarda pywin32'ye açıkça
BYREF `VARIANT` verilmelidir. Düz Python listesi verilirse çağrı hata
vermez, liste sessizce değişmeden döner ve her şey birim matris sanılır.

## 6. Atalet

`Analyze.GetInertia` 9 elemanlı bir matris döndürür, ama iki şey belirsizdir:

1. **Referans noktası:** parça orijini mi, ağırlık merkezi mi?
2. **Çarpım terimi işareti:** `∫xy dm` mi, tensörün köşegen dışı terimi
   (`-∫xy dm`) mi?

İkisi de kalibrasyonla çözülür ve tahmin edilmez.

Dikkat: köşegen terimleri bu soruyu **çözemez**. Bir köşesi orijinde olan
blok için her eksende `I_orijin = 4 · I_cg` olduğundan iki hipotez de
köşegene mükemmel uyar ve aradaki sabit kat, bilinmeyen birim ölçeği
tarafından yutulur. Dört kat atalet hatası tam olarak böyle gözden kaçar.

Köşegen dışı terimler bu dejenerasyonu taşımaz: eksenlere paralel bir bloğun
CG'sinde sıfırdırlar, köşesinde değil. `köşegen dışı / köşegen` oranı
boyutsuzdur, yani ölçeği bilmeden referans noktasını verir; işareti de
konvansiyonu verir.

Kalibrasyon `inertia_ref = "cg"` çıkarırsa işaret bu parçadan
belirlenemez ve atalet aktarımı kapatılır. Kütle ve CG akışı etkilenmez.

Adams'a giderken iki dönüşüm daha yapılır: tensör `R I Rᵀ` ile döndürülür
(nokta gibi ötelenmez) ve Adams'ın beklediği çarpım konvansiyonuna
çevrilir. Bkz. `adams_cmd.md`.

## 7. Malzeme ve yoğunluk

Malzemesi olmayan parça hata vermez, 0 kg döner. Bu yüzden:

- `mass <= 0` olan her yaprak `zero_mass` ile işaretlenir
- yoğunluk `kütle / hacim` üzerinden türetilir; hesaplanamıyorsa
  `no_density` işaretlenir
- malzeme adı okuma sürümler arasında değiştiği için birkaç yol denenir,
  hiçbiri tutmazsa `no_material` işaretlenir ve bu bir hata değildir

Uyarılar `rollup` çıktısında alt yapı adıyla birlikte listelenir, çünkü
"bir yerde bir parçanın malzemesi yok" kullanışlı bir bilgi değildir.

## 8. Performans

Büyük ağaçlarda tarama sırasında ekran güncellemesi kapatılmalıdır:

```python
catia.RefreshDisplay = False
catia.Interactive = False
```

Her ikisi de `finally` bloğunda geri açılmalı, aksi halde CATIA kullanıcı
için kilitlenmiş görünür. `extract` bunu zaten yapıyor.
