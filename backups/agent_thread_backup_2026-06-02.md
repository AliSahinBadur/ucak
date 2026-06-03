# Agent Thread Backup - 2026-06-02

Bu dosya, acilmayan eski `agent` Codex thread'inden kurtarilan proje hafizasidir.

- Eski thread id: `019d95df-1575-7321-8d80-1893652dc3c2`
- Eski thread basligi: `agent`
- Workspace: `C:\Users\ISU34977\PyCharmMiscProject`
- Ana proje: `C:\Users\ISU34977\PyCharmMiscProject\Big_Agent`
- Yedek tarihi: `2026-06-02`
- Not: Bu dosya birebir ham transcript degildir. Eski thread cok uzun oldugu ve cok sayida ekran goruntusu/base64 icerigi barindirdigi icin burada devam etmek icin gerekli kararlar, surumler, komutlar, mimari ve acik isler korunmustur.

## Kisa Durum

Proje adi fiilen `Big_Agent / RaporHub` haline geldi.

Ana hedef:

- Muhendislik raporlarini PDF/DOCX olarak sisteme almak.
- Metni parse etmek, temizlemek, chunk'lara bolmek.
- DB'ye yazmak.
- Embedding uretmek.
- Keyword / semantic / hybrid / fuzzy arama yapmak.
- Benzer rapor bulmak.
- Rapor katalogu uzerinden coklu belge secmek.
- Tek veya coklu belgeye soru sormak.
- Kisa/uzun taslak rapor ve PDF cikti uretmek.

Son bilinen olgunluk seviyesi:

- Uygulama local FastAPI olarak calisiyor.
- UI tek sayfada upload, search, QA, report writer, catalog ve multi-doc QA alanlarini tasiyor.
- En son konusulan surum: `v0.49.0` civari.
- En son QA regression durumu: `22/22 passed`.
- Katalog tarafinda yaklasik `1531-1532` satir import edilmis durumda.
- En son katalog gorunumunde `15` rapor ingested, `15` rapor embedded olarak gorunuyordu.

## Mimari

Ana akisin omurgasi:

```text
PDF/DOCX
-> ingest
-> parser
-> cleaner
-> chunker
-> SQLite / SQLAlchemy
-> embeddings
-> search / QA / report writer / catalog
```

Baslica dosyalar:

- `app/main.py`: FastAPI endpoint'leri ve HTML/JS UI.
- `app/api_models.py`: API response/request modelleri.
- `app/version.py`: surum bilgisi.
- `app/config.py`: model, DB, data path ve embedding ayarlari.
- `app/db/models.py`: SQLAlchemy modelleri.
- `app/db/session.py`: DB session.
- `app/parsers/pdf_parser.py`: PDF text extraction.
- `app/parsers/docx_parser.py`: DOCX text/table/heading extraction.
- `app/processing/text_cleaner.py`: metin temizleme.
- `app/processing/chunker.py`: chunk uretimi.
- `app/services/ingest_service.py`: dosya ingest.
- `app/services/embedding_service.py`: token-hash ve sentence-transformers provider.
- `app/services/embedding_reindex_service.py`: mevcut chunk'lari yeniden embed etme.
- `app/services/search_service.py`: keyword/semantic/hybrid/fuzzy/reranking.
- `app/services/qa_service.py`: retrieval-grounded QA.
- `app/services/report_writer_service.py`: taslak rapor ve PDF/Word benzeri cikti.
- `app/services/storage_service.py`: DB dosya yolu tutarlilik kontrolu.
- `app/services/catalog_service.py`: Excel katalog import/search/QA.
- `app/services/catalog_ingest_service.py`: katalogdaki rapor satirlarindan gercek dosya ingest.
- `app/services/multi_document_qa_service.py`: secili coklu dokuman QA.
- `scripts/run_qa_checks.py`: regression QA test kosucusu.
- `test_cases/qa_cases.json`: QA regression test seti.

Baslica tablolar:

- `documents`
- `document_pages`
- `document_chunks`
- `chunk_embeddings`
- `report_catalog_entries`

## Baslangic Kararlari

Ilk hedef MVP idi:

- PDF/DOCX ingest
- text extraction
- cleaning
- chunking
- DB persistence
- keyword search
- semantic/hybrid search
- similar reports

Ilk surum kapsam disi birakilanlar:

- OCR
- image-to-text
- summarization
- Q&A
- lessons learned
- revision comparison

Gelistirme sirasi:

```text
Parsing -> Cleaning -> Chunking -> DB -> Search -> Similar reports -> QA/report writer/catalog
```

`AGENT.md` once eklendi, sonra `AGENTS.md` olarak duzeltildi. Dosya amaci: ajanlarin MVP hedefinden sapmamasini saglamak.

## Surum Akisi

Bu kisim eski thread'teki ana degisiklikleri kronolojik olarak korur.

### v0.1 - v0.7: Temel Ingest ve UI

- `FastAPI + SQLAlchemy` tabanli API kuruldu.
- `POST /ingest`, `GET /search`, `GET /health` eklendi.
- PDF/DOCX parser, cleaner, chunker, DB modelleri kuruldu.
- Dosya duplicate kontrolu `file_hash` ile yapildi.
- Ilk arama keyword tabanliydi.
- Token-hash tabanli gecici embedding servisi eklendi.
- `POST /embeddings/rebuild` endpoint'i eklendi.
- Gercek model icin `sentence-transformers` provider altyapisi hazirlandi.
- Model indirmede Hugging Face SSL/proxy sorunu goruldu.
- Yerel model klasoru ve `EMBEDDING_LOCAL_FILES_ONLY=true` destegi eklendi.
- Dosya saklama adi once hash idi, sonra `Gercek_Dosya_Adi__kisaHash.pdf` formatina cevrildi.
- Swagger batch upload sorunlari nedeniyle ana upload page eklendi.
- `GET /storage/check` eklendi; DB'de olup fiziksel dosyasi olmayan kayitlari buluyor.

### v0.8 - v0.14: Arama Ekrani ve Similar Reports

- Ana sayfa upload + search ekranina donustu.
- Search modlari: `keyword`, `semantic`, `hybrid`.
- `similar_documents` alanlari `/search` cevabina eklendi.
- Sonuc kartlari ve benzer rapor kartlari UI'da gosterildi.
- Tekli upload + toplu upload birlikte eklendi.
- Belge detay sayfasi ve orijinal dosya acma endpoint'i eklendi.
- Sonuc kartlarindaki `document_id undefined` hatasi duzeltildi.
- PDF/DOCX icin `Content-Type` ve `inline` davranisi duzeltildi.
- Arama kalitesi sikilastirildi:
  - semantic min score
  - zayif semantic-only sonuclari filtreleme
  - belge basina tekrar azaltma
  - similar reports icin belge seviyesi aggregation
- Bu asama sonunda Seviye 1 ve Seviye 2 bitmis sayildi.

### v0.18 - v0.27: Retrieval-Grounded QA

- `POST /ask` eklendi.
- Ilk QA extractive/kural tabanliydi, uydurma cevap yerine kaynak chunk'tan cevap secmeye calisiyordu.
- QA response'a `confidence` eklendi.
- Dusuk guvenli cevaplarda daha durust davranmasi saglandi.
- Liste sorulari icin ozel mantik eklendi:
  - `nelerdir`
  - `hangileri`
  - `listesi`
- `Yol Datası Toplama Parkurları nelerdir` sorusu uzerinde cok iterasyon yapildi.
- Ilk problem: sadece baslik donuyordu.
- Sonra yanlis rapor/yanlis liste secildi.
- Sonra `BozukYol / Arnavut Kaldırım / Otoban` listesinin ucuncu maddesi dusuyordu.
- Sebepler:
  - wrong chunk / wrong document retrieval
  - section fazla genis
  - `3 adet senaryo` gibi preamble sayilari liste regex'ini karistiriyor
  - PDF extraction `Şekil` kelimesini bazen `ekil` diye bozuyordu
- v0.27 civarinda liste cikarici su sonucu temiz uretebilir hale geldi:

```text
1. BozukYol (Koy yolu)
2. Arnavut Kaldirim
3. Otoban
```

Not: thread'te Turkce karakterler bazen terminal/encoding yuzunden bozulmustu; kodda bazi alanlarda ASCII tercih edildi.

### v0.28 - v0.30: Model Upgrade ve Qwen

Once mevcut model:

- `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- yaklasik `0.1B` parametre
- `384` embedding dimension
- `128 token` civari truncation siniri
- 50 dil

Alternatifler arastirildi:

- `Alibaba-NLP/gte-multilingual-base`
- `BAAI/bge-m3`
- `intfloat/multilingual-e5-large-instruct`
- `Qwen/Qwen3-Embedding-0.6B`
- `Qwen/Qwen3-Embedding-4B`

Kararlar:

- Ilk pratik Qwen gecisi `Qwen3-Embedding-0.6B` olarak planlandi.
- Sonra 4B de indirildi ve klasor yapisi dogrulandi.
- Qwen embedding modellerinin cevap yazan model degil, retrieval icin kullanildigi netlestirildi.
- `model:` rozeti UI'da surumun yanina eklendi.
- `token-hash-v1` gorunmesi fallback anlamina geliyor.
- `Qwen3-Embedding-0.6B` veya `Qwen3-Embedding-4B` gorunmesi gercek modelin aktif oldugunu gosteriyor.
- Model degistirince mutlaka `POST /embeddings/rebuild` gerekiyor.

Model klasorleri:

```text
C:\Users\ISU34977\PyCharmMiscProject\Big_Agent\models\paraphrase-multilingual-MiniLM-L12-v2
C:\Users\ISU34977\PyCharmMiscProject\Big_Agent\models\Qwen3-Embedding-0.6B
C:\Users\ISU34977\PyCharmMiscProject\Big_Agent\models\Qwen3-Embedding-4B
```

4B klasoru dogrulanmisti:

- `config.json`
- `config_sentence_transformers.json`
- `modules.json`
- `1_Pooling\config.json`
- `tokenizer.json`
- `tokenizer_config.json`
- `model.safetensors.index.json`
- `model-00001-of-00002.safetensors`
- `model-00002-of-00002.safetensors`
- embedding dimension: `2560`

### v0.30 - v0.36: QA, Report Writer, PDF Export

- Synonym-aware retrieval eklendi:
  - `data / veri / verisi / datasi`
  - `parkur / guzergah / rota`
  - `toplama / toplanan / toplanmasi`
- Report writer one alindi:
  - `POST /draft-report`
  - `report_writer_service.py`
  - UI'da report writer bolumu
- Kisa ve detayli taslak rapor butonlari eklendi.
- Search match highlight eklendi.
- PDF export eklendi.
- Turkce karakter PDF sorunu Windows Arial TTF ile cozuldu.
- `Content-Disposition` Turkce filename hatasi ASCII safe filename ile cozuldu.
- Word template benzeri baslik yapisi kullanildi:
  - `KAPSAM`
  - `SONUCLAR`
  - `GIRIS`
  - `TEST VE DEGERLENDIRME YONTEMI`
  - `SONUC`
  - `COZUM ONERILERI`
- Template kaynak dosya:

```text
C:\Users\ISU34977\Desktop\2025-BIG-e-NVH-01.docx
```

- `document_id` scoped QA eklendi:
  - Ask alanina opsiyonel `Belge ID`
  - Search kartlari Belge ID gosteriyor

### v0.38 - v0.41: Fuzzy Search, Performans ve Testler

- Manuel alias yaklasimi yerine fuzzy search eklendi.
- Keyword/fuzzy + semantic + reranking birlikte calismaya basladi.
- UI highlight fuzzy eslesmeleri de desteklemeye basladi.
- `MAX_FUZZY_SCAN_ROWS=1500` gibi limitler konuldu.
- `komfor / konfor / komfort / komfpr` gibi yazim farklari icin tolerans eklendi.
- Onemli performans bug'i:
  - Search sirasinda eksik/uyumsuz embedding boyutunu anlamak icin her chunk'ta `embed_text("probe")` cagriliyordu.
  - Qwen 4B CPU'da bu yuzden arama 2000 saniyeyi buldu.
  - v0.39.1 civari duzeltildi: eksik veya boyut uyumsuz embedding arama aninda skip edildi.
  - `komfor` search yaklasik `0.34 sec` seviyesine indi.
- UI'da upload/search/ask/draft butonlarina timer eklendi.
- Regression test altyapisi eklendi:
  - `test_cases/qa_cases.json`
  - `scripts/run_qa_checks.py`
- Ilk 6 test basariliydi, sonra test seti 22 case'e genisledi.

### v0.42 - v0.44: QA Testleri ve Rapor Katalogu

- QA test seti 22 case'e genisletildi.
- List/aim/equipment gibi hatalar duzeltildi.
- `22 passed` durumuna gelindi.
- Excel katalog altyapisi eklendi:
  - `report_catalog_entries` tablosu
  - `/catalog/import`
  - `/catalog/search`
  - `/ask/catalog`
  - UI'da `Rapor Katalogu ve Coklu Belge QA`
- `LIST_OF_REPORTS.xlsx` ana katalog olarak kullanildi.
- Excel'deki 14 sheet import edildi.
- Thread'te gecen sayilar:
  - 1520 rows seen
  - 1386 created
  - 134 duplicates
  - total 1532
- Sonraki UI'da yaklasik 1531 catalog rows gorundu.
- Catalog matching `Novocitivolt / GEN2` gibi adlarda eslesme yapacak sekilde iyilestirildi.
- Catalog analytic QA eklendi:
  - kac analiz tipi var?
  - hangi analiz tipinden kac tane?
  - ranking / aggregation / comparison

### v0.45 - v0.49: Catalog UI, Multi-Document QA, Embedding Status

- `Büyüt` modal eklendi.
- Ilk multi-document QA katmani eklendi:
  - `multi_document_qa_service.py`
  - `search_service.py`
  - `qa_service.py`
  - `main.py`
  - `api_models.py`
- Modal icinde:
  - secili dokumanlar
  - ikinci asama soru alani
  - karsilastirma tablosu
  - kaynaklar
- Catalog matching fix:
  - `Yuklu Belge: 0` hatasi duzeltildi.
- Katalogdan secili satirlari ingest etme eklendi:
  - `GET /catalog/table`
  - `POST /catalog/ingest-selected`
- UI Excel benzeri hale getirildi:
  - yesil: ingested
  - kirmizi: pending
  - embedding complete / missing status
- `Büyüt` butonundaki JS hatasi:
  - `rawPath.includes("\\")` kaynakliydi
  - duzeltildi.
- Sample ingest per analysis type:
  - SAFETY / NVH / VED gibi tiplerden raporlar alindi
  - v0.47 civari 6 rapor ingest edildi
- En son v0.49 civari:
  - katalog embedding status eklendi
  - 15 ingested
  - 15 embedded
  - QA tests `22/22 passed`

## En Onemli Teknik Kararlar

- OCR ilk MVP'de bilincli olarak ertelendi.
- Ilk oncelik selectable text idi.
- Chunk ana arama birimi olarak secildi.
- Dosya duplicate kontrolu hash ile yapildi.
- Dosya storage adi okunabilir ad + kisa hash oldu.
- `token-hash-v1` sadece fallback/placeholer.
- Gercek semantic kalite icin `sentence-transformers` ve Qwen embedding kullanildi.
- Model degisimi `rebuild` gerektirir.
- QA ilk asamada generative degil, retrieval-grounded/extractive idi.
- Sonra Groq/OpenAI/Qwen generative model fikirleri konusuldu ama ana hat local retrieval olarak kaldi.
- Catalog metadata ile real content ayrimi netlesti:
  - Katalog satiri sadece metadata ise content QA yapamaz.
  - Gercek PDF/DOCX ingest edilirse content QA ve karsilastirma yapabilir.
- Multi-document QA icin once katalogdan rapor secme, sonra secili raporlar uzerinden soru sorma yaklasimi tercih edildi.

## Calistirma Komutlari

Paraphrase MiniLM ile:

```powershell
cd C:\Users\ISU34977\PyCharmMiscProject\Big_Agent
$env:EMBEDDING_PROVIDER="sentence-transformers"
$env:EMBEDDING_MODEL_NAME="C:\Users\ISU34977\PyCharmMiscProject\Big_Agent\models\paraphrase-multilingual-MiniLM-L12-v2"
$env:EMBEDDING_LOCAL_FILES_ONLY="true"
$env:EMBEDDING_DEVICE="cpu"
& 'C:\Users\ISU34977\PyCharmMiscProject\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload
```

Qwen 0.6B ile:

```powershell
cd C:\Users\ISU34977\PyCharmMiscProject\Big_Agent
$env:EMBEDDING_PROVIDER="sentence-transformers"
$env:EMBEDDING_MODEL_NAME="C:\Users\ISU34977\PyCharmMiscProject\Big_Agent\models\Qwen3-Embedding-0.6B"
$env:EMBEDDING_LOCAL_FILES_ONLY="true"
$env:EMBEDDING_DEVICE="cpu"
& 'C:\Users\ISU34977\PyCharmMiscProject\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload
```

Qwen 4B ile:

```powershell
cd C:\Users\ISU34977\PyCharmMiscProject\Big_Agent
$env:EMBEDDING_PROVIDER="sentence-transformers"
$env:EMBEDDING_MODEL_NAME="C:\Users\ISU34977\PyCharmMiscProject\Big_Agent\models\Qwen3-Embedding-4B"
$env:EMBEDDING_LOCAL_FILES_ONLY="true"
$env:EMBEDDING_DEVICE="cpu"
& 'C:\Users\ISU34977\PyCharmMiscProject\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload
```

Embedding rebuild:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/embeddings/rebuild
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

Ana UI:

```text
http://127.0.0.1:8000/
```

LAN'dan acmak icin:

```powershell
cd C:\Users\ISU34977\PyCharmMiscProject\Big_Agent
& 'C:\Users\ISU34977\PyCharmMiscProject\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Sonra ayni agdaki kisi:

```text
http://<senin-ipv4-adresin>:8000/
```

QA regression:

```powershell
cd C:\Users\ISU34977\PyCharmMiscProject\Big_Agent
& 'C:\Users\ISU34977\PyCharmMiscProject\.venv\Scripts\python.exe' scripts\run_qa_checks.py
```

## Model Notlari

MiniLM:

- Hafif, baslangic icin iyi.
- 384 dimension.
- Kisa context sebebiyle uzun rapor chunk'larinda sinirli.

Qwen3-Embedding-0.6B:

- Dengeli secenek.
- Mevcut modele gore kalite artisi beklenir.
- CPU'da yonetilebilir ama MiniLM'den agir.

Qwen3-Embedding-4B:

- Daha guclu retrieval potansiyeli.
- CPU'da agir.
- 2560 dimension.
- Search performansinda her chunk'ta model cagrisi yapilmamali.

Groq:

- Embedding replacement olarak degil, cevap uretme/generative QA icin dusunuldu.
- Privacy ve cloud konusu not edildi.
- Retrieval icin lokal Qwen embedding + generation icin Groq olasi mimari olarak konusuldu.

## Bilinen Sorunlar ve Dersler

- Eski thread cok agirlasmis ve son turn interrupted kalmis olabilir.
- Uzun thread + cok sayida screenshot/base64 acilmama sorununu tetiklemis olabilir.
- Search aninda embedding provider tekrar tekrar cagrilmamali.
- Model degisirse eski embedding'ler kullanilmamali; rebuild sart.
- Katalog metadata ile gercek report content karistirilmamali.
- `document_id` scoped QA, yanlis belgeyle yarismayi azaltmak icin kritik.
- Liste sorulari normal sentence extraction ile cozulmuyor; ozel list extraction gerekiyor.
- PDF extraction bazen Turkce karakterleri veya `Şekil` gibi kelimeleri bozuyor.
- `--reload` normal kod degisikliklerinde yeterli; env var/model degisince restart gerekiyor.

## Eski Thread'ten Onemli Kullanici Tercihleri

- Anlatim asiri basitlestirilmesin.
- Dosya/fonksiyon/tablo seviyesinde net soylensin.
- Her anlamli degisiklikte versiyon artsin.
- UI pratik olsun; Swagger sadece teknik test icin kalsin.
- Kullanici dosya path'i elle yazmak istemiyor; popup/arayuz tercih ediyor.
- Rapor kartina basinca HTML detay yerine orijinal PDF/DOCX acilmasi tercih edildi.
- Gercek raporlar ve test dosyalari birbirine karismasin.

## Muhtemel Devam Noktasi

Eski thread'in son aktif projesi v0.49 civari katalog + embedding status + multi-document QA idi.

Devam etmeden once onerilen kontrol:

1. Mevcut kodun gercek durumunu oku.
2. `app/version.py` icindeki surumu kontrol et.
3. `GET /health` ile app version ve model rozetini kontrol et.
4. `scripts/run_qa_checks.py` ile regression kos.
5. Catalog UI'da:
   - toplam satir
   - ingested count
   - embedded count
   - pending count
   kontrol et.
6. Bundan sonra yeni gelistirmeye gec.

En olasi siradaki isler:

- Catalog satirlarindan daha fazla gercek PDF/DOCX ingest etmek.
- Multi-document QA kalitesini olcmek.
- Katalog + content QA ayrimini UI'da daha net yapmak.
- Groq/generative QA entegrasyonunu opsiyonel olarak eklemek.
- Server/LAN deployment hazirligini iyilestirmek.

## Thread Okuma Durumu

Eski `agent` thread'i tum sayfalariyla okundu; `hasMore=false` goruldu.

Bu yedek, sohbetin birebir kopyasi degil; fakat projeyi yeni thread'te devam ettirmek icin gerekli ana karar, kod yolu, komut, surum ve problem hafizasini korur.
