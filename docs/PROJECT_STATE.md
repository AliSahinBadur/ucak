# Proje durumu

Son güncelleme: 2026-09-03

## Genel durum

- Aktif sürüm: `v0.50.212`
- Kalan ana dal: `main`
- Kanonik kod tabanı: `Big_Agent`
- Frontend yapısı: FastAPI tarafından sunulan HTML/CSS/JS; React kullanılmıyor.
- Çalışma ağacında henüz commit edilmemiş geliştirmeler bulunabilir. Değişiklikleri geri almadan önce `git status --short` kontrol edilmelidir.

## Ürünler

| Ürün | Varyant | Standart port | Durum |
| --- | --- | ---: | --- |
| SmartCAE AI | `big_agent` | `8002` | Aktif, v2 arayüz ana deneyim |
| RaporHub | `raporhub` | `8003` | Aktif, ayrı landing ve ürün teması |
| Repocto | `repocto` | `8004` | Aktif, kurumsal hafıza ve klasör tarama deneyimi |
| Smart AIOS | Ayrı `cog_izolator_web` projesi | `8001` | Operasyon kabuğu ve uygulama başlatma alanı |

## Paylaşılan altyapı

Üç ürün varyantı aynı FastAPI uygulamasını, API uçlarını ve `app/services/` katmanını kullanır. Belge yükleme, katalog, arama, embedding, RAG, rapor karşılaştırma, rapor kontrolü ve rapor yazımı ortak geliştirilir. `APP_VARIANT` yalnızca ürün kimliği ve deneyim seçimini yapar.

Workstation hedefinde bütün ürünlerin aynı rapor havuzuna erişmesi isteniyor:

```text
C:\SmartAIOS\Big_Agent\data
```

SmartCAE süreci bu yolu `BIG_AGENT_DATA_DIR` ile; RaporHub ve Repocto süreçleri mevcut yapı gereği `RAPORHUB_DATA_DIR` ile alır. Ortak veri için iki değişken aynı klasöre yönlendirilmelidir.

## Workstation LLM tercihi

- Kullanıcının workstation `ollama list` çıktısında model `qwen3.5:9b` olarak doğrulandı (6.6 GB, ID: `6488c96fa5fa`); bundan sonraki workstation LLM kullanımı için bu model tercih edilecek.
- Mevcut başlatma dosyaları `LLM_MODEL_NAME`, `CHAT_LLM_MODEL_NAME`, `REPORT_LLM_MODEL_NAME` ve `CATIA_SKILL_MODEL_NAME` ortam değişkenlerini koruyor. Workstation'da bu dört ayar `qwen3.5:9b` olacak; kodun yerel varsayılanı değiştirilmedi.
- Workstation'da ayarların uygulanması ve çalışan süreçlerin yeni modeli kullanması henüz doğrulanmadı. Embedding modeli değişmeyecek.
- Kullanıcının sonraki workstation logunda genel sohbet için `httpx.ReadTimeout` görüldü. Mevcut genel sohbet varsayılanı 45 saniye; ilk adım olarak workstation'da `LLM_TIMEOUT_SECONDS`, `CHAT_LLM_TIMEOUT_SECONDS` ve `REPORT_LLM_TIMEOUT_SECONDS` değerlerinin 180 saniyeye alınması önerildi. Bu ayarın uygulanması ve sorunu çözmesi henüz doğrulanmadı; yavaşlığın donanım, model yüklemesi veya eşzamanlı istek kaynaklı olduğu logdan tek başına belirlenemez.
- `v0.50.212`: Ortak Ollama çağrıları native düşünmeyi `think: false` ile açıkça kapatır; uygulamanın Thinking/LLM bağlam çözümlemesi ayrı olarak korunur. Genel sohbet talimatları artık kullanıcı metnine gömülmek yerine ayrı `system` mesajı olarak gönderilir. Boş/geçersiz model cevabı yanıt sayılmaz; genel sohbet hatası sabit bir cevapla gizlenmeden HTTP 503 döner.
- Thinking'in atlanması ile denenip başarısız olması API'de `thinking_attempted` ile ayrılır. Başarısız bağlam çözümü aynı istekte tekrar çağrılmaz. Genel sohbette özgün kullanıcı mesajı korunur.

## SmartCAE AI

- Yeni SmartCAE v2 arayüzü ana arayüzdür; eski arayüz ayrı geçişle korunur.
- Kaynak paneli daraltılıp genişletilebilir ve belge önizlemesi panel içinde açılır.
- Sistem durumu kutusu embedding modelini ve sunucuda yapılandırılan sohbet LLM modelini ayrı satırlarda gösterir.
- Genel sohbet ilerlemesinde güven yüzdesi gösterilmez; hazır uygulama yanıtı ile model yanıtı ayrılır. Thinking gerekli olmadığı için atlandığında başarısızlık uyarısı gösterilmez.
- RAG sürümü seçilebilir: v1 klasik, v2 beta ve v3 Haystack.
- Sohbet ekranında skill ve örnek soru alanları bulunur.
- Skill merkezi; rapor kontrolü, revizyon kontrolü, tablo/şekil kontrolü ve CATIA kütle/CG kartlarını içerir.
- Skill kartlarında kısa kullanım yönergeleri gösterilir.
- Kaynak kartları dosya türü, sayfa, kategori, skor, hazırlayan, tarih ve rapor konusu gibi standart metadata sunar.

## Repocto

- `APP_VARIANT=repocto` ile aynı uygulamadan açılır.
- Ayrı Repocto landing sayfası ve yeniden tasarlanmış ürün görünümü vardır.
- Kök klasör yolu alıp izin verilen kökler altında PDF, DOCX ve PPTX belgelerini özyinelemeli tarar.
- Doküman ağacı, klasör haritası, filtreler ve salt okunur belge profili üretir.
- Ortak RAG ve rapor verisi üzerinde kurumsal hafıza deneyimi sağlar.

## RaporHub

- `APP_VARIANT=raporhub` ile aynı uygulamadan açılır.
- Ayrı landing sayfası ve ürün teması vardır.
- Ortak arama, RAG, katalog ve rapor servislerini kullanır.

## Skill ve CATIA durumu

- Rapor kontrolü kural tabanlı ve LLM destekli kanıtlı inceleme üretir.
- Revizyon kontrolü yeni, giderilen ve devam eden bulguları eşleştirir.
- Tablo/şekil kontrolü numara, başlık ve metin içi referansları inceler.
- CATIA kütle/CG skill'i ana sohbet akışına bağlıdır; komut harness'ı, önizleme ve insan onayı kullanır.
- Küçük modelin eksik bıraktığı güvenli `run`/`calibrate` alt komutları yalnızca açıkça ayırt edilebildiğinde tamamlanır.
- Özel CATIA modeli belirtilmezse skill, kurulu sohbet modelini kullanır; böylece olmayan `qwen3:4b-instruct` etiketi yeni kurulumlarda 404 üretmez.
- Gerçek kullanım öncesinde CATIA bağlantısı ve birim kalibrasyonu canlı ortamda doğrulanmalıdır.
- Kullanıcının sonraki sohbet denemesinde model, `calibrate` aracını çağırmadan işlemi tamamladığını söyledi ve uydurma bir bağlantı üretti; `E_NO_PROFILE` devam etti. Bu sohbet akışı henüz düzeltilmedi. Daha büyük model kullanımı tek başına çözüm sayılmamalıdır.

## Son doğrulama

- Skill merkezi kart sözleşme testi geçti.
- Fake CATIA komutları `doctor -> calibrate -> run -> PREVIEW_READY` sırasıyla doğrulandı; bu test serbest sohbetin güvenilir çalıştığını kanıtlamaz. Onay ve `.cmd` dışa aktarımı yapılmadı.
- `v0.50.212` için ortak sağlayıcı, genel sohbet hata akışı, Thinking ve üç varyantı kapsayan 35 hedefli test ile 10 alt test geçti. Yerel `qwen2.5:3b` ile `selam`, `naber`, yaş sorusu ve yazım hatalı yaş sorusu gerçek LLM cevabı aldı; workstation `qwen3.5:9b` henüz canlı doğrulanmadı.
- Tarayıcıda Thinking açıkken `selam` için gerçek model cevabı, güven yüzdesinin gizlenmesi ve Thinking'in gereksiz olduğu durumun doğru gösterilmesi doğrulandı. Yerel 3B modelin cevap kalitesi ayrıca değerlendirilmelidir; başarılı HTTP/araç akışı cevap doğruluğunu kanıtlamaz.
- Geniş SmartCAE UI sözleşme testinde `resizeChatInput` dinleyicisine ait eski bir assertion uyuşmazlığı bulunuyor; çalışma zamanı arızası olduğu henüz gösterilmedi.
