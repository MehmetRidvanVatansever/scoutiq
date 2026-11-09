# ScoutIQ – Futbol Gözlemciliği ve Transfer Analiz Sistemi

Flask + PostgreSQL ile geliştirilmiş oyuncu arama, karşılaştırma ve izleme listesi uygulaması.

## Kurulum
1. PostgreSQL'de `scoutiq` adında boş bir veritabanı oluştur.
2. Kaggle "Transfermarkt Dataset" (davidcariboo/player-scores) içinden `players.csv`, `clubs.csv`,
   `competitions.csv`, `appearances.csv` dosyalarını `data/` klasörüne koy.
3. `pip install -r requirements.txt`
4. PowerShell'de şifreni tanımla: `$env:DB_PASSWORD="sifren"` (her yeni terminalde tekrar gerekir).
5. `python scripts/load_data.py` (tabloları kurar, verileri yükler, indeks ve view oluşturur)
6. `python app.py` → http://127.0.0.1:5000 (ilk kayıt olan kullanıcı admin olur)

## Klasörler
- `app.py` Flask uygulaması · `db.py` bağlantı · `sql/` şema, indeks, view · `scripts/` veri yükleme
- `templates/` HTML · `static/` CSS · `docs/` dokümantasyon ve diyagramlar
