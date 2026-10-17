# OtoFiyat'ı çevrimiçi yayımlama ve haftalık güncelleme

Bu klasör GitHub deposunun kökü olarak yüklenmelidir. Site yayımlandığında herkese açık olur.

## İlk kurulum

1. GitHub'da herkese açık bir depo oluşturun ve bu klasördeki dosyaları yükleyin.
2. Depo ayarlarından **Pages** bölümünü açın. Yayımlama kaynağını ana dal ve kök klasör olarak seçin.
3. **Actions → General → Workflow permissions** bölümünde iş akışlarının yazma iznini etkinleştirin.
4. **Actions → Weekly official price check** akışını bir kez elle çalıştırın. Ardından her pazartesi Türkiye saatiyle yaklaşık 08.00'de çalışır.

GitHub Actions zamanlanmış işleri yoğunlukta geciktirebilir. Akışın raporu Actions çalıştırmasının `official-price-check-report` çıktısında bulunur.

## Fiyat güvenilirliği

Güncelleyici yalnızca markanın resmî Türkiye sayfasında model adıyla aynı satırda tek bir TL tutarı görürse kaydı günceller. Sayfa engelliyse, JavaScript ile sonradan yükleniyorsa veya aynı satırda kampanya ve liste fiyatı gibi birden fazla tutar varsa mevcut kaydı korur ve bunu rapora yazar. Bu nedenle desteklenen sayfa biçimleri arttıkça fiyat kapsaması da genişletilmelidir.

Uygulamadaki kayan bant yeni ve önceki fiyat akışını karşılaştırır. Rapor, hangi markaların kaynağına ulaşılamadığını ve hangi modeller için tek bir fiyat belirlenemediğini gösterir.
