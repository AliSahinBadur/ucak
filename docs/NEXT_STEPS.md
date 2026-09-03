# Sıradaki işler

Son güncelleme: 2026-09-02

## Öncelikli

1. CATIA skill'ini gerçek CATIA bağlantısı ve gerçek birim kalibrasyonuyla uçtan uca doğrula.
2. Ölçüm sonucunun ana sohbette önizleme ve onay kartına dönüştüğünü canlı arayüzde kontrol et.
3. SmartCAE geniş UI sözleşme testindeki eski `resizeChatInput` assertion uyuşmazlığını incele ve testi güncel davranışla hizala.
4. Mevcut commit edilmemiş değişiklikler için hedefli testleri tamamlayıp kullanıcıya git durumunu özetle.

## İdeathon varsayım ve deney kanvası

1. SmartCAE AI ve Repocto için önemli/bilinmeyen varsayımları En Riskli Varsayım Kanvası'na yerleştir.
2. İlk deneyde iki pilot ekibin mevcut yöntem ile uygulamayı kullanarak aynı gerçek rapor görevlerini tamamlamasını karşılaştır.
3. Taslak başarı ölçütlerini görev tamamlama oranı, doğru kaynağa ulaşma, işlem süresi, kaynak doğruluğu ve kullanıcı güven puanı olarak belirle.
4. Deney sonunda sonuç, gözlem, öğrenim ve devam/değiştir/durdur kararını Deney Tasarım Günlüğü'ne kaydet.

## Ortak altyapı

1. Workstation başlatma komutlarında SmartCAE AI, RaporHub ve Repocto veri yollarının aynı `C:\SmartAIOS\Big_Agent\data` klasörüne yönlendirildiğini doğrula.
2. Ortak backend değişiklikleri için üç `APP_VARIANT` değerini kapsayan hafif smoke test ekle.
3. RAG v1/v2/v3 cevap kalitesini aynı soru setiyle ölçülebilir hâle getir.

## Flowport entegrasyonu

IT tarafından bildirilen kısıt: Rapor deposuna doğrudan dosya sistemi erişimi verilmeyecek; belgeler Flowport API üzerinden Base64 içerik olarak sağlanabilecek.

1. API sözleşmesinde belge kimliği, dosya adı, uzantı/MIME, revizyon, güncellenme tarihi, checksum, Base64 içerik, silinme/arşiv durumu ve sayfalama alanlarını netleştir.
2. Base64 içeriği giriş sınırında katı doğrulamayla decode eden; boyut, uzantı, dosya imzası ve checksum kontrolü yapan bir Flowport adaptörü ekle.
3. Decode edilen dosyayı güvenli geçici alandan mevcut `IngestService` hattına ver; Base64 metnini veritabanında saklama.
4. Mevcut hash tabanlı duplicate kontrolünü koru; Flowport belge kimliği ve revizyonunu incremental senkronizasyon için ayrıca kaydet.
5. Kalıcı orijinal dosya saklama ve silinen/arşivlenen Flowport belgelerinin yerel yaşam döngüsü politikasını IT ile kararlaştır.

## Repocto

1. Büyük ve iç içe klasörlerde tarama sınırı, izinli kök ve hata mesajlarını gerçek ağ yolu üzerinde doğrula.
2. Doküman ağacı, klasör haritası, filtreleme ve belge profili akışını kullanıcı testiyle değerlendir.
3. Ortak rapor havuzunda bulunan belgelerle Repocto arama/RAG akışını doğrula.

## Dokümantasyon bakımı

1. Yeni kalıcı kararları `DECISIONS.md` dosyasına ekle.
2. Port, veri yolu, sürüm veya ürün durumu değiştiğinde `PROJECT_STATE.md` dosyasını aynı değişiklik içinde güncelle.
3. Tamamlanan maddeleri bu dosyadan kaldır veya tamamlandı olarak proje durumuna taşı.
