# Ollama ile çalıştırma

Ollama sadece modeli servis eder. Döngü, araç kısıtı ve güvenlik kapıları
`runner/agent.py` içinde.

## Kurulum

```bash
ollama serve                        # ayrı terminalde açık kalsın
ollama pull qwen3:4b-instruct
```

`qwen3:4b-instruct` (Qwen3-4B-Instruct-2507) düşünme modu olmayan, araç
çağrısı şablonu gelen resmi etiket. Nicemleme etiketleri
`ollama.com/library/qwen3/tags` altında; Q5_K_M varsa onu tercih edin, Q4
altında araç çağrısı formatı gözle görülür bozuluyor.

Python tarafında ek paket gerekmiyor; `agent.py` standart kütüphaneyle
Ollama'nın `/api/chat` ucuna konuşuyor.

## Etkileşimli koşu

CATIA olmadan, sentetik montajla:

```bash
python runner/agent.py --workspace /tmp/ws --skill . --fake
```

Gerçek CATIA ile, mühendisin bilgisayarında:

```bash
python runner/agent.py --workspace C:\cmc-ws --skill .
```

Çalışma klasöründe `subassembly_map.json`, `transform_profile.json` ve
`adams_map.json` bulunmalı (örnekleri `assets/` altında).

Konuşma başlar; `q` ile çıkılır. Her komut ve sonucu ekrana basılır:

```
> araç montajından kütle çıkar, ARAC-X / BASE / R04

[model] Ortamı kontrol ediyorum.
[cmc] python -m cmc doctor
      -> ok  Ortam uygun. Python 64-bit, pywin32 var.
```

## Harness ne garanti ediyor

Model iyi davranmasa bile şunlar tutar:

| Kapı | Ne engeller |
|---|---|
| Komut izin listesi | `cmc` dışı her şey. Kabuk komutu, Python, dosya silme |
| Argüman izin listesi | Tanımsız bayraklar |
| Yer tutucu kontrolü | `--vehicle <ARAC>` gibi doldurulmamış şablonların çalışması |
| İnsan onay kapısı | Kullanıcı bu oturumda onaylamadan `export` |
| Bağlam kırpma | 2000 parçalık JSON'un modelin bağlamına girmesi |

Bunlar `cmc` içindeki kontrollerin yerine geçmez, üstüne biner. Onay kodu
zaten `cmc` tarafında doğrulanıyor; harness'taki kapı, modelin kodu bir
yerden kopyalayıp kapıyı atlamasına karşı ikinci katman.

Kapıların çalıştığını görmek için senaryo dosyasıyla deneyebilirsiniz:

```bash
printf 'kütle çıkar\n150x80x40\nq\n' | python runner/agent.py \
    --workspace /tmp/ws --skill . --fake --stub runner/stub-misbehaving.jsonl
```

Bu senaryo bilerek kötü davranan bir model taklit eder: yer tutucu bırakır,
kabuk komutu dener, onaysız export ister. Üçü de reddedilmeli.

## Değerlendirme

```bash
python runner/run_evals.py --workspace /tmp/evalws --skill . --fake --repeat 3
```

`evals/evals.json` içindeki vakaları koşturur ve nesnel kontrolleri puanlar:
hangi komut çalıştı, hangisi çalışmamalıydı, model soru sordu mu. Sonuçlar
`eval-results.json` dosyasına yazılır.

`--repeat 3` önemli: küçük modellerde davranış koşudan koşuya değişir. Tek
koşuda geçmesi bir şey söylemez, üç koşuda geçmesi bir şey söyler.

Ölçülen davranışlar, küçük modelde en sık bozulan sıraya göre:

1. Yer tutucu değerleri kendi uydurmak (`<ARAC>` yerine "ARAC" yazmak)
2. Onay almadan export'a geçmek
3. Hata gördüğünde durmak yerine başka komut denemek
4. Sayıları kendi hesaplayıp `message_tr` yerine kendi cümlesini kurmak

## Model başarısız olursa

Harness'ı gevşetmeyin. Sırasıyla şunları deneyin:

1. **Nicemlemeyi yükseltin.** Q4 → Q5_K_M en ucuz kazanç.
2. **`SKILL.md` kurallarını sıkılaştırın.** Düşen davranış için açık bir
   madde ekleyin; küçük model ima anlamaz.
3. **`num_ctx` artırın.** Uzun akışta bağlam taşarsa model ilk kuralları
   unutur. Varsayılan 8192, gerekirse 16384.
4. **Adımı ikiye bölün.** Model bir komutta iki karar veriyorsa, komutu
   ikiye ayırmak modeli değiştirmekten daha güvenilir.
5. **Modeli büyütün.** 4B'de tutmayan bir davranış 8B'de tutuyorsa, bu bir
   prompt sorunu değil kapasite sorunudur.

Hiçbiri tutmazsa: hattın tamamı zaten komut satırından elle
çalıştırılabilir. Model bir kolaylık katmanı, zorunluluk değil.
