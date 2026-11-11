# ScoutIQ – Futbol Gözlemciliği ve Transfer Analiz Sistemi

Flask + PostgreSQL ile geliştirilmiş oyuncu arama, karşılaştırma ve izleme listesi uygulaması.
Veriler: Kaggle "Transfermarkt Dataset" (davidcariboo/player-scores). Sitede **2024 yılında en az bir maça çıkan** oyuncular listelenir;
gol ve asist tüm zamanların toplamıdır.

## Kurulum
1. PostgreSQL'de `scoutiq` adında boş bir veritabanı oluştur.
2. Kaggle'dan `players.csv`, `clubs.csv`, `competitions.csv`, `appearances.csv` dosyalarını `data/` klasörüne koy.
3. `pip install -r requirements.txt`
4. PowerShell'de şifreni tanımla: `$env:DB_PASSWORD="sifren"` (her yeni terminalde tekrar gerekir).
5. `python scripts/load_data.py` (17 tabloyu kurar, verileri yükler, indeks ve view'ları oluşturur; **mevcut verileri siler**)
6. `python app.py` → http://127.0.0.1:5000 (ilk kayıt olan kullanıcı admin olur, sonrakiler scout)

İsteğe bağlı ortam değişkenleri: `DB_NAME`, `DB_USER`, `DB_HOST`, `DB_PORT`, `SECRET_KEY`.

## Klasörler
- `app.py` Flask uygulaması · `db.py` veritabanı bağlantısı
- `sql/schema.sql` tablolar ve kısıtlar · `sql/indexes_views.sql` indeksler ve view'lar
- `scripts/load_data.py` veri temizleme ve yükleme · `scripts/season_data.py` 2024 hesaplaması
- `scripts/apply_sql.py` bir .sql dosyasını veri silmeden uygular (ör. view güncellemesi)
- `scripts/migrate_2024.py` eski sürümden geçiş için tek seferlik betik (yeni kurulumda gerekmez)
- `templates/` HTML şablonları (`_macros.html` ortak parçalar) · `static/` CSS · `docs/` dokümantasyon  