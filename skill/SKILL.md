---
name: catia-mass-cg
description: CATIA V5'te açık olan araç montajından alt yapı bazında kütle, ağırlık merkezi (CG) ve atalet değerlerini çıkarır, araç/varyant/revizyon bazında saklar, önceki revizyonla karşılaştırır ve onaydan sonra Adams/Car için .cmd dosyası üretir. Kullanıcı CATIA, CATProduct, kütle, ağırlık merkezi, CG, COG, atalet, Adams, Adams/Car, cmd aktarımı, araç ağırlık dağılımı, aks/süspansiyon kütlesi ya da revizyon karşılaştırması konularından herhangi birini andığında bu skill'i kullan. "CATIA'dan kütle çek", "CG hesapla", "Adams'a aktar", "geçen revizyona göre ne değişti" gibi ifadeler bu skill'i tetikler.
---

# CATIA kütle / CG / atalet hattı

## Değişmez kurallar

1. **Hiçbir sayıyı sen hesaplama.** Toplama, ortalama alma, birim çevirme,
   koordinat dönüştürme yasak. Bütün aritmetik `cmc` komutlarında yapılıyor ve
   sonuçları CATIA'nın kendi değerleriyle çapraz kontrol ediliyor. Senin
   yaptığın bir toplama bu kontrolden geçmez.
2. **Python kodu yazma, script düzenleme.** Sadece aşağıdaki `cmc`
   komutlarını çalıştır.
3. **Her komutun çıktısındaki `next_command` alanını çalıştır.** Boşsa dur.
4. **Kullanıcıya `message_tr` alanını göster.** Kendi cümleni kurma; sayıları
   yeniden yazma, kopyala.
5. **`status` "error" ise dur.** `message_tr` ve `hint_tr` alanlarını göster,
   başka komut deneme, aynı komutu tekrarlama. Hata mesajı zaten ne
   yapılacağını söylüyor.
6. **`export` komutunu kullanıcı açıkça onaylamadan çalıştırma.** Onay kodunu
   uydurma; `preview` çıktısındaki koddan kopyala.

## Komut sırası

```
python -m cmc doctor
python -m cmc calibrate --length <L> --width <W> --height <H> --density <kg/m3>   # ilk sefer
python -m cmc attach                                                              # sonraki seferler, calibrate yerine
python -m cmc extract --vehicle <ARAC> --variant <VARYANT> --revision <REV>
python -m cmc rollup   --run <id>
python -m cmc diff     --run <id>
python -m cmc preview  --run <id>
python -m cmc export   --run <id> --approve <onay_kodu>
```

`doctor` hangisinin çalışacağını `next_command` alanında söyler: kalibrasyon
yoksa `calibrate`, varsa `attach`. Ezberleme, alandaki komutu çalıştır.

Yardımcı komutlar: `show` (sonuç tablosu), `history` (geçmiş ölçümler),
`selftest` (iç tutarlılık testleri).

Bütün komutlar `--source fake` ile CATIA olmadan da çalışır; deneme ve
eğitim için bunu kullan.

## Adım adım ne yapacaksın

**doctor** ile başla. Python 64-bit mi, pywin32 var mı, hangi ayar dosyaları
eksik onu söyler.

**calibrate** sadece bir kez, her makinede. Kullanıcıdan kalibrasyon bloğunun
ölçülerini ve yoğunluğunu iste; blok CATIA'da açık olmalı. Ölçüleri sen
uydurma. Çıktıda `inertia_usable: false` ise kullanıcıya söyle: atalet
aktarımı kapalı olacak, kütle ve CG çalışmaya devam eder.

**attach** kalibrasyon zaten yapılmışsa `doctor`'ın önereceği adımdır.
Ölçüm yapmaz, sadece açık CATIA oturumuna bağlanır ve hangi dökümanın aktif
olduğunu doğrular. Kalibrasyon bloğu istemez.

**extract** için üç bilgi lazım: araç adı, varyant, revizyon. Kullanıcı
vermediyse sor, tahmin etme. Ölçülecek CATProduct CATIA'da açık ve aktif
olmalı.

**rollup** alt yapı bazında toplar ve üç şeyi doğrular: her parça tam olarak
bir alt yapıya atanmış mı, toplam kütle CATIA'nın montaj kütlesiyle aynı mı,
alt yapılardan geri hesaplanan CG CATIA'nınkiyle aynı mı. Bu kontroller
düşerse hata verir ve devam edilmez, doğrusu budur.

**diff** önceki revizyonla karşılaştırır. Önceki revizyon yoksa bu normaldir.

**preview** değişiklik önizlemesi ve bir onay kodu üretir. `preview_text`
alanını kullanıcıya olduğu gibi göster ve sor: "Bu değişiklikleri onaylıyor
musunuz?" Kullanıcı açıkça onaylarsa `command_after_approval` alanındaki
komutu çalıştır. Onaylamazsa dur.

**export** .cmd dosyasını yazar ve iş biter.

## Sık karşılaşılan hatalar

| Kod | Anlamı | Kullanıcıya söylenecek |
|---|---|---|
| `E_ATTACH_NOT_FOUND` | CATIA'ya bağlanılamadı | CATIA açık mı; CATIA ve agent aynı kullanıcı ve aynı yetki seviyesinde mi |
| `E_WORKMODE` | Montaj sıfır kütle veriyor | Visualization mode veya cache açık; Design mode gerekiyor |
| `E_NO_PROFILE` | Kalibrasyon yok | Önce `calibrate` |
| `E_UNMAPPED` | Bir parça hiçbir alt yapıya atanmamış | `subassembly_map.json` dosyasına desen eklenmeli |
| `E_INVARIANT_MASS` / `E_INVARIANT_CG` | Toplam CATIA ile tutmuyor | Veri kullanılamaz, geliştiriciye bildir |
| `E_LANDMARK_MISMATCH` | Adams dönüşüm profili doğrulanamadı | Eksen eşlemesi yanlış, profil düzeltilmeli |
| `E_APPROVAL` | Onay kodu tutmadı | Önizlemedeki kodu birebir kullan |
| `E_STALE_APPROVAL` | Önizlemeden sonra veri değişmiş | `preview` tekrar çalıştırılıp kullanıcıya gösterilmeli |

## Ayar dosyaları

Çalışma klasöründe bulunmalı. Örnekleri `assets/` içinde:

- `subassembly_map.json` — hangi parça hangi alt yapıya ait (tekerleklerin
  akslarda ikinci kez sayılmasını bu dosya engeller)
- `transform_profile.json` — CATIA'dan Adams'a koordinat dönüşümü ve onu
  doğrulayan iki referans nokta
- `adams_map.json` — alt yapı → Adams parça adı eşlemesi
- `units_profile.json` — `calibrate` üretir, elle düzenlenmez

Kullanıcı bu dosyaları düzenlemeni isterse yardımcı olabilirsin, ama
`units_profile.json` hariç: o ölçümle üretilir, elle yazılmaz.

## Daha fazla bilgi

- `references/catia_api_gotchas.md` — CATIA V5 otomasyon tuzakları, sürüm
  farkları, bağlantı sorunları
- `references/adams_cmd.md` — üretilen komut formatı ve koordinat konvansiyonu
- `EXPLAINER.md` — hattın nasıl çalıştığının tam açıklaması (insan için)
