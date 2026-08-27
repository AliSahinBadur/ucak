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
| `extraction.sparse_pages` | Metni çıkarılamayan veya çok zayıf sayfalar | OCR kontrolü ister |
| `content.embedded_paths` | Metne taşınmış yerel/ağ dosya yolları | Bilgi seviyesinde kontrol ister |

## Aşama 1 Kabul Ölçütleri

- Mevcut tablo/şekil numaralandırma soruları aynı şekilde çalışır.
- Genel "raporu kontrol et" sorusu kalite akışına yönlenir.
- Sonuç hem okunabilir cevap hem de yapılandırılmış `review` verisi döndürür.
- Her sorun kararlı bir `rule_id`, önem seviyesi ve mümkünse sayfa kanıtı taşır.
- Motor LLM, embedding modeli veya internet olmadan çalışır.
- Eksik metin, doğrudan kesin içerik hatası yerine insan kontrolü gerektiren
  bulgu olarak işaretlenir.
