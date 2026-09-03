# Rapor Kontrol Skill'i

## Amaç

Rapor Kontrol skill'i, teknik raporu bir kontrol mühendisine sunulmadan önce
deterministik kurallar ve daha sonraki aşamalarda kanıt zorunlu LLM kontrolleriyle
incelemeyi amaçlar. Skill, CAE analizini yeniden çözmez ve fiziksel uygunluk onayı
vermez.

## Aşamalar

0. **Kural sözleşmesi:** Kontrol profilleri, bulgu formatı ve kabul ölçütleri.
1. **Temel kontrol motoru:** LLM kullanmadan yapı, numaralandırma, referans,
   sayısal yazım ve çıkarım kalitesi kontrolleri.
2. **Görsel kanıt:** PDF koordinatları, tablo/şekil konumları ve tıklanabilir
   vurgular.
3. **Anlamsal kontrol:** Kapsam-sonuç uyumu, bölüm çelişkileri ve sonuçların
   kanıtlarla desteklenmesi.
4. **Disiplin profilleri:** Genel, Durability, CFD, NVH ve Test/Validasyon
   profilleri.
5. **Denetim akışı:** İnsan onayı, revizyon karşılaştırması ve dışa aktarma.

## Mevcut Durum

- Aşama 1 tamamlandı ve SmartCAE AI içindeki `Rapor kontrolü` skill'ine bağlandı.
- Aşama 2 başladı: kontrol bulguları önem seviyesi ve düzeltme önerisiyle kaynak
  kartlarında gösteriliyor; PDF kanıtları ilgili sayfada renkli işaretlenebiliyor.
- Aşama 3 başladı: Ollama yapılandırılmış JSON çıktısıyla kapsam-sonuç uyumu,
  rapor içi dayanak ve metin içi çelişki adayları aranıyor. Yalnızca belirtilen
  sayfada birebir doğrulanabilen alıntılar bulguya dönüşüyor; uydurma veya eksik
  kanıtlı sonuçlar eleniyor.
- Aşama 4 tamamlandı: katalog disiplini veya rapor kimliğinden otomatik olarak
  NVH, CFD, Durability ve Test/Validasyon profili seçiliyor. Genel kurallara ek
  olarak disipline özgü yöntem, sınır şartı, ölçüm düzeni, sayısal kanıt, kabul
  kriteri ve sonuç izlenebilirliği kontrol ediliyor.
- Aşama 5 başladı: kaynak kartlarındaki bulgular insan tarafından `Onayla` veya
  `Geçersiz` kararıyla işaretlenebiliyor. Kararlar doküman ve bulgu kimliğiyle
  veritabanında saklanıyor; güncel bulgular ve insan kararları PDF kontrol kaydı
  olarak dışa aktarılabiliyor.
- İki rapor seçildiğinde `Revizyon kontrolü` skill'i, kural ve disiplin profili
  bulgularını yeni, giderilen ve devam eden başlıklar olarak karşılaştırıyor.
  Bu karşılaştırma tam metin redline yerine kontrol bulgularının değişimini izler.

## Aşama 4 Profilleri

| Profil | Ek kontroller |
| --- | --- |
| NVH | Sensör/nokta, eksen, çalışma koşulu, sinyal işleme, standart ve sonuç yorumu |
| CFD | Çözüm modeli, sınır şartları, ağ/mesh, yakınsama/zaman adımı ve birimli sonuç karşılaştırması |
| Durability | Malzeme, yük/mesnet, sonlu eleman ağı, bağlantı/temas ve sonuç-kriter bağı |
| Test/Validasyon | Test objesi, ekipman, koşullar, prosedür, kabul kararı ve kalibrasyon/cihaz kimliği |

Profil kontrolleri fiziksel doğruluk kararı vermez. Eksik dokümantasyon
`needs_review` olarak işaretlenir; test cihazı kalibrasyon bilgisi gibi her rapora
uygulanamayabilecek alanlar bilgi seviyesinde gösterilir.

## Disiplin Kural Dosyaları

Disiplin kuralları Python'da değil, disiplin başına bir veri dosyasında durur:
`app/rules/profiles/<profil>.json`. Motor tarafındaki tek işleyici
`_profile_requirement`'tır; her disiplin kuralı aynı kontrolü çalıştırır — her
`requirement_groups` grubunun, listelediği yazımlardan en az biriyle rapor
metninde geçmesi beklenir. Geçmeyen grupların adı bulgu mesajına yazılır.

```jsonc
{
  "profile": "nvh",              // dosya adıyla aynı olmalı
  "label": "NVH",                // arayüzde görünen profil adı
  "detect_priority": 10,         // "auto" tespitinde deneme sırası (küçük önce)
  "aliases": ["nvh", "noise vibration harshness"],   // katalog disiplini eşlemesi
  "detect_patterns": ["\\bnvh\\b"],                  // rapor adı/başlığı regex'leri
  "rules": [
    {
      "rule_id": "nvh.measurement_setup",   // profil adıyla başlamak zorunda
      "label": "NVH olcum duzeni ve kosullari",
      "category": "nvh",
      "severity": "warning",                // critical | warning | info
      "message": "NVH olcum duzeni raporda tam izlenemiyor.",
      "suggested_fix": "Sensoru ve olcum noktasini ... acikca yazin.",
      "requirement_groups": [
        { "label": "eksen / olcum yonu", "aliases": ["x ekseni", "olcum yonu"] }
      ]
    }
  ]
}
```

Dosyalar yüklenirken doğrulanır: bilinmeyen anahtar, eksik alan, geçersiz
`severity`, profil önekiyle başlamayan `rule_id`, boş grup/alias, derlenmeyen
regex ve kod tarafındaki bir `rule_id`'nin tekrar kullanılması içe aktarma
sırasında hata verir. Amaç, bir yazım hatasının sessizce çalışmayan bir kural
bırakmasını engellemektir.

### Yeni bir disiplin kontrolü eklemek

1. İlgili `app/rules/profiles/<profil>.json` dosyasına kuralı ekleyin; yeni bir
   disiplin için dosyayı oluşturun (`label`, `aliases`, `detect_patterns` ve
   `detect_priority` ile birlikte).
2. `test_cases/report_review_cases.json` içine golden case ekleyip
   `scripts/run_report_review_checks.py` ile gerçek bir rapor üzerinde doğrulayın.
3. `tests/test_report_review_rules.py` içine kuralın hangi grubu yakaladığını
   sabitleyen bir test ekleyin — katalogdaki her `rule_id` için bir iddia
   arayan meta test bunu zaten zorunlu kılar.

Python değişikliği gerekmez; `checks_run` sayısı, profil etiketleri, `auto`
tespiti ve kural doğruluğu tablosu dosyadan gelir.

## Bulgu Sözleşmesi

Her bulgu aşağıdaki alanları taşır:

- `rule_id`: Kararlı kural kimliği.
- `category`: Yapı, tablo/şekil, sayısal tutarlılık veya çıkarım kalitesi.
- `severity`: `critical`, `warning` veya `info`.
- `status`: `fail` veya `needs_review`.
- `message`: Sorunun kısa açıklaması.
- `evidence`: Rapor içinden kanıt metni.
- `page_start` / `page_end`: Kanıtın sayfa aralığı.
- `suggested_fix`: Önerilen düzeltme.
- `engine`: Bulguyu üreten motor; `rules` veya `llm:<provider>`.

Kanıt bulunamayan bir LLM değerlendirmesi ileride dahi kesin hata olarak
sunulmaz; `needs_review` veya "doğrulanamadı" sonucuna dönüşür.

## Aşama 1 Kuralları

| Kural | Amaç | Sonuç yaklaşımı |
| --- | --- | --- |
| `metadata.required_fields` | Rapor no, tarih, hazırlayan ve kontrol alanları | Eksikler insan kontrolü ister |
| `structure.required_sections` | Kapsam ve sonuçlar bölümleri | Eksikler insan kontrolü ister |
| `captions.sequence` | Eksik, tekrar ve sıra bozukluğu | Kesin bulunan sorun hata olur |
| `captions.title` | Başlıksız tablo/şekil/resim | Uyarı üretir |
| `captions.references` | Metinde anılmayan öğeler ve karşılıksız referanslar | İnsan kontrolü ister |
| `numbers.decimal_style` | Ölçümlerde virgül/nokta karışıklığı | İnsan kontrolü ister |
| `extraction.no_text` | Hiç okunabilir metin çıkmayan sayfalar | Kesin bulunan sorun hata olur |
| `extraction.ocr_low_quality` | OCR çalıştırıldığı hâlde metni zayıf kalan sayfalar | İnsan kontrolü ister |
| `content.embedded_paths` | Metne taşınmış yerel/ağ dosya yolları | Bilgi seviyesinde kontrol ister |

## Kural Doğruluğu (rule precision)

`ReportReviewDecision` tablosundaki insan kararları kural bazında toplanır:
`confirmed / (confirmed + dismissed)`. `open` bulgular sayılır ama orana
girmez; karar verilmemiş olmak katılmamak değildir. Bir kuralın 10'dan az
kararı varsa oran yerine `insufficient_data` döner — az sayıda karardan
üretilen bir yüzde ölçüm değil gürültüdür.

| Nasıl görüntülenir | Komut / uç nokta |
| --- | --- |
| Golden kontrollerle birlikte | `python scripts/run_report_review_checks.py --precision` |
| Yalnızca tablo | `python scripts/run_report_review_checks.py --precision-only` |
| Arayüz / API | `GET /report-review/rule-precision` |

Katalogdan çıkarılmış bir `rule_id` (örneğin Aşama 0'da ikiye ayrılan
`extraction.sparse_pages`) tabloda `in_catalog: false` ile listelenir; geçmiş
kararlar silinmez, yalnızca işaretlenir.

## Aşama 1 Kabul Ölçütleri

- Mevcut tablo/şekil numaralandırma soruları aynı şekilde çalışır.
- Genel "raporu kontrol et" sorusu kalite akışına yönlenir.
- Sonuç hem okunabilir cevap hem de yapılandırılmış `review` verisi döndürür.
- Her sorun kararlı bir `rule_id`, önem seviyesi ve mümkünse sayfa kanıtı taşır.
- Motor LLM, embedding modeli veya internet olmadan çalışır.
- Eksik metin, doğrudan kesin içerik hatası yerine insan kontrolü gerektiren
  bulgu olarak işaretlenir.
