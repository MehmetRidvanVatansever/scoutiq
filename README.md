# ScoutIQ – Football Scouting and Transfer Analysis System

*Türkçe açıklama aşağıdadır.*

A player search, comparison and watchlist application built with Flask + PostgreSQL.
Data: Kaggle "Transfermarkt Dataset" (davidcariboo/player-scores). The site lists **players who played at least one match in 2024**;
goals and assists are all-time totals. Each player page shows the market value history (chart) and the career / previous clubs.

## Setup
1. Create an empty database named `scoutiq` in PostgreSQL.
2. Put `players.csv`, `clubs.csv`, `competitions.csv`, `appearances.csv`, `player_valuations.csv`, `transfers.csv` from Kaggle into the `data/` folder.
3. `pip install -r requirements.txt`
4. Set your password in PowerShell: `$env:DB_PASSWORD="your_password"` (needed in every new terminal).
5. `python scripts/load_data.py` (creates the 19 tables, loads the data, creates indexes, views, triggers and functions; **deletes existing data**)
6. `python app.py` → http://127.0.0.1:5000 (the first registered user becomes admin, later ones scout)

Optional environment variables: `DB_NAME`, `DB_USER`, `DB_HOST`, `DB_PORT`, `SECRET_KEY`.
To apply the SQL files to an existing database without deleting data: `python scripts/apply_sql.py` (all) or `python scripts/apply_sql.py sql/<file>.sql`

## Folders
- `app.py` builds the Flask app and registers the Blueprints · `config.py` settings and constants
- `db.py` database connection + `query` / `execute` / `transaction` · `decorators.py` `login_required` / `admin_required` · `utils.py` shared helpers
- `routes/` one Blueprint per area: `auth`, `players`, `reports`, `history`, `watchlist`, `clubs`, `compare`, `admin`
- `sql/schema.sql` tables and constraints · `sql/indexes.sql` · `sql/views.sql` · `sql/triggers.sql` · `sql/functions.sql`
- `scripts/load_data.py` data cleaning and loading · `scripts/season_data.py` 2024 calculation · `scripts/history_data.py` value history and transfers · `scripts/common.py` shared script helpers
- `scripts/apply_sql.py` applies the SQL files without deleting data (no argument = indexes, views, triggers, functions)
- `scripts/migrate_history.py` adds the value history + transfer tables to an existing database (user/report data is kept)
- `scripts/migrate_2024.py` one-off script for migrating from an older version (not needed for a new install)
- `templates/` HTML templates (`_macros.html` shared parts, `partials/` parts of the player and admin pages) · `static/` CSS · `docs/` documentation (English and Turkish)

---

## Türkçe

Flask + PostgreSQL ile geliştirilmiş oyuncu arama, karşılaştırma ve izleme listesi uygulaması.
Veriler: Kaggle "Transfermarkt Dataset" (davidcariboo/player-scores). Sitede **2024 yılında en az bir maça çıkan** oyuncular listelenir;
gol ve asist tüm zamanların toplamıdır. Oyuncu sayfasında piyasa değeri geçmişi (grafik) ve kariyer / önceki kulüpler gösterilir.

### Kurulum
1. PostgreSQL'de `scoutiq` adında boş bir veritabanı oluştur.
2. Kaggle'dan `players.csv`, `clubs.csv`, `competitions.csv`, `appearances.csv`, `player_valuations.csv`, `transfers.csv` dosyalarını `data/` klasörüne koy.
3. `pip install -r requirements.txt`
4. PowerShell'de şifreni tanımla: `$env:DB_PASSWORD="sifren"` (her yeni terminalde tekrar gerekir).
5. `python scripts/load_data.py` (19 tabloyu kurar, verileri yükler, indeks, view, trigger ve fonksiyonları oluşturur; **mevcut verileri siler**)
6. `python app.py` → http://127.0.0.1:5000 (ilk kayıt olan kullanıcı admin olur, sonrakiler scout)

Mevcut veritabanına veri silmeden SQL dosyalarını uygulamak için: `python scripts/apply_sql.py` (hepsi) ya da `python scripts/apply_sql.py sql/<dosya>.sql`
Klasörlerin açıklaması yukarıdaki İngilizce bölümle aynıdır; dokümantasyon `docs/` klasöründe iki dilde bulunur.
