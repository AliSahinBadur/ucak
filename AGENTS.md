# Big_Agent çalışma kuralları

## Proje yapısı

`Big_Agent`, üç ürün varyantının ortak ve kanonik kod tabanıdır:

- `APP_VARIANT=big_agent`: SmartCAE AI
- `APP_VARIANT=raporhub`: RaporHub
- `APP_VARIANT=repocto`: Repocto

API, veritabanı modelleri, belge yükleme, katalog, arama, RAG, karşılaştırma,
rapor yazımı ve ortak servisler paylaşılır. Ürün kimliği ve ürüne özel ekranlar
varyant üzerinden seçilir. Ortak bir servis değiştiğinde etkilenen bütün varyantlar
kontrol edilmelidir.

## Kullanıcıyla çalışma biçimi

- Kullanıcı Türkçe ve kısa iletişim ister.
- Kod değişikliğinden önce yapılacak işi bir veya iki cümleyle açıkla.
- Değişiklikten sonra hedefli testi çalıştır ve sonucu kısa biçimde bildir.
- Kullanıcının açık talebi olmadan commit veya push yapma; git komutlarını kullanıcıya ver.
- Kullanıcı sunucuyu kendisi başlatmak istediğinde süreci arka planda başlatma.
- Uzun veya maliyetli test gerekiyorsa önce haber ver.

## Kod ve arayüz kuralları

- Uygulama FastAPI tabanlıdır; ana eski arayüz `app/main.py` içinde inline HTML/CSS/JS içerir.
- Mevcut yapıyı okumadan React veya yeni bir frontend çatısı ekleme.
- SmartCAE AI v2 dosyaları `app/ui/smartcae_v2/` altındadır.
- Repocto arayüzü `app/ui/repocto_landing/` ve `app/ui/repocto_styles.py` içindedir.
- RaporHub arayüzü `app/ui/raporhub_landing/` ve ortak varyant stillerini kullanır.
- Ortak iş mantığını `app/services/` altında tut; ürüne özel görünümü servis katmanına taşıma.
- Manuel dosya değişikliklerinde `apply_patch` kullan.
- Kullanıcının veya başka bir çalışmanın mevcut değişikliklerini geri alma.
- Her çalışma zamanı kodu ya da arayüz değişikliğinde `app/version.py` değerini bir artır.
- Sadece dokümantasyon değişikliğinde sürüm artırmak gerekmez.

## Veri ve güvenlik

- `data`, model, veritabanı, yüklenen belgeler ve ekran görüntüleri GitHub'a eklenmez.
- Veri yolu ortam değişkenleriyle seçilir; sabit kullanıcı yolu kodlama.
- Workstation kurulumunda hedef, ürünleri aynı rapor havuzuna yönlendirmektir:
  `C:\SmartAIOS\Big_Agent\data`.
- SmartCAE için `BIG_AGENT_DATA_DIR`, RaporHub ve Repocto için mevcut yapıda
  `RAPORHUB_DATA_DIR` kullanılır. Aynı veri isteniyorsa ikisi de aynı klasörü göstermelidir.
- Farklı ekipler için veri izolasyonu istendiğinde ayrı veri klasörleri ve ayrı süreçler kullanılır.
- Kaynak dışı LLM cümlesi üretmektense kanıt yok yanıtı tercih edilir.
- Dosya yolları ve yerel ağ ayrıntıları arayüzde gereksiz yere ifşa edilmez.

## Ürün sınırları

### Ortak backend

- Belge yükleme ve çıkarım: PDF, DOCX, PPTX; gerektiğinde OCR.
- Keyword, semantic ve hybrid arama.
- RAG v1, RAG v2 ve deneysel RAG v3/Haystack seçimi.
- Kaynaklı soru-cevap, karşılaştırma, benzerlik ve rapor kontrolü.
- Rapor yazımı ve dışa aktarım.

### SmartCAE AI

- Mühendislik çalışma alanı ve kaynaklı sohbet.
- Skill merkezi: rapor kontrolü, revizyon kontrolü, tablo/şekil kontrolü ve CATIA kütle/CG.
- Yeni v2 arayüz ana deneyimdir; eski arayüz erişilebilir kalır.

### Repocto

- Ortak backend üzerinde ayrı ürün kimliği ve arayüz.
- Kök klasörü özyinelemeli tarayıp belge ağacı, klasör haritası, filtreler ve belge profili üretir.
- Kurumsal hafıza ve doküman keşfi odağındadır.

### RaporHub

- Ortak backend üzerinde ayrı tanıtım ve ürün arayüzü.
- Rapor arama, kaynaklı sohbet ve kurumsal hafıza deneyimine odaklanır.

## Kalite beklentileri

- Dar değişiklikte ilgili hedefli testleri çalıştır.
- Ortak backend değişikliğinde en az SmartCAE AI, RaporHub ve Repocto varyant sözleşmelerini kontrol et.
- Arama yanlış sonuç döndürmektense güçlü eşleşme yoksa boş dönmelidir.
- CATIA gibi dış sisteme yazan skill'lerde güvenli komut listesi ve insan onayı korunmalıdır.
- Gerçek CATIA kaynağı ile fake/test kaynağını arayüzde açıkça ayır.

## Kalıcı proje hafızası

- `docs/PROJECT_STATE.md`: çalışan ürünler, sürüm, portlar ve güncel durum.
- `docs/DECISIONS.md`: kalıcı mimari ve ürün kararları.
- `docs/NEXT_STEPS.md`: doğrulanmış açık işler ve sıradaki adımlar.
- Önemli bir karar, tamamlanan aşama, yeni risk veya değişen port/veri yolu oluştuğunda
  kullanıcıdan ayrıca istemesini beklemeden ilgili dosyayı güncelle.
- Sohbet geçmişini tek kaynak kabul etme; yeni çalışmaya başlarken bu dosyaları ve kodu oku.
