# Mimari ve ürün kararları

## D-001: Tek kanonik kod tabanı

SmartCAE AI, RaporHub ve Repocto ayrı repo kopyaları olarak geliştirilmeyecek. Ortak kod `Big_Agent` içinde tutulacak ve ürün `APP_VARIANT` ile seçilecek.

## D-002: Ortak backend, ayrılmış ürün deneyimi

RAG, arama, belge işleme, veritabanı ve rapor servisleri ortaktır. Ürün markası, landing sayfası, navigasyon ve ürüne özel ekranlar varyant bazında ayrılır. Ortak backend değişikliği bütün varyantlarda test edilir.

## D-003: Mevcut frontend mimarisini koruma

Uygulama FastAPI ile sunulan HTML/CSS/JS yapısında kalacak. Büyük bir mimari karar alınmadan React eklenmeyecek. Yeni arayüzler mevcut statik/inline yapı içinde modüler dosyalara ayrılabilir.

## D-004: Kaynaklı cevap önceliği

LLM yalnızca getirilen ve doğrulanabilir rapor kanıtlarıyla cevap üretmelidir. Alakasız sonuç veya uydurma cevap yerine yeterli kanıt bulunamadığı açıkça söylenir.

## D-005: RAG sürümlerini yan yana koruma

RAG v3/Haystack deneysel olarak eklenirken mevcut RAG v2 değiştirilmeden korunur. Kullanıcı arayüzden sürümü seçebilir ve sürümler ayrı ayrı ölçülebilir.

## D-006: Veri yolu çalışma zamanında seçilir

Kod tabanı ortak olsa da veri paylaşımı ortam değişkenleriyle yönetilir. Workstation senaryosunda SmartCAE AI, RaporHub ve Repocto aynı `C:\SmartAIOS\Big_Agent\data` klasörüne yönlendirilir. İzole ekip testlerinde ayrı veri klasörleri kullanılır.

## D-007: SmartCAE v2 ana arayüzdür

Yeni SmartCAE v2 deneyimi ana arayüz olarak sunulur. Eski arayüz geçiş seçeneğiyle erişilebilir kalır.

## D-008: Skill'ler sohbet içinde çalışır

Mühendislik skill'leri ayrı ve kopuk uygulamalara yönlendirmek yerine ana sohbet bağlamında açılır. Hazır komut, işlem durumu, kanıt ve gerekiyorsa onay kartı aynı akışta gösterilir.

## D-009: CATIA çıktısı onay kapılıdır

CATIA skill'i yalnızca izinli komut harness'ını kullanır. Ölçüm ve fark önizlenir; Adams/Car `.cmd` çıktısı insan onayı olmadan oluşturulmaz. Fake ve gerçek veri kaynağı açıkça gösterilir.

## D-010: Git işlemlerinin sahibi kullanıcıdır

Asistan kullanıcı açıkça istemedikçe commit veya push yapmaz. Gerekli komutları kullanıcıya verir.

## D-011: Repo belgeleri kalıcı hafızadır

Sohbet geçmişi tek kaynak sayılmaz. Ürün durumu, kararlar ve açık işler `docs/` altında güncel tutulur; önemli değişikliklerde kullanıcıdan ayrıca talep beklenmez.

