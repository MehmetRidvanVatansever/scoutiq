-- Tekrar çalıştırılabilir (idempotent). Kulüp bağlantısı quiz'i (Club Link Quiz) tabloları.
-- Mevcut veritabanına veri silmeden eklenir:  python scripts/apply_sql.py

-- Quiz'de sorulan büyük kulüpler (kaynak verideki Transfermarkt kulüp kimlikleri)
CREATE TABLE IF NOT EXISTS quiz_clubs (
  club_id  INT PRIMARY KEY REFERENCES clubs(club_id) ON DELETE CASCADE
);

-- Bir kullanıcının bir oyunu: seri (streak) her doğru cevapta 1 artar, ilk yanlışta oyun biter
CREATE TABLE IF NOT EXISTS quiz_games (
  game_id     SERIAL PRIMARY KEY,
  user_id     INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  started_at  TIMESTAMP NOT NULL DEFAULT now(),
  ended_at    TIMESTAMP,                                   -- NULL: oyun devam ediyor
  streak      INT NOT NULL DEFAULT 0 CHECK (streak >= 0),
  CHECK (ended_at IS NULL OR ended_at >= started_at)
);

-- Oyundaki her soru: iki kulüp ve kullanıcının cevabı
CREATE TABLE IF NOT EXISTS quiz_rounds (
  round_id          SERIAL PRIMARY KEY,
  game_id           INT NOT NULL REFERENCES quiz_games(game_id) ON DELETE CASCADE,
  club_a            INT NOT NULL REFERENCES clubs(club_id),
  club_b            INT NOT NULL REFERENCES clubs(club_id),
  asked_at          TIMESTAMP NOT NULL DEFAULT now(),
  answer_text       VARCHAR(150),                          -- kullanıcının yazdığı
  answer_player_id  INT REFERENCES players(player_id) ON DELETE SET NULL,   -- eşleşen oyuncu (doğruysa)
  is_correct        BOOLEAN,                               -- NULL: henüz cevaplanmadı
  answered_at       TIMESTAMP,
  CHECK (club_a <> club_b),
  CHECK ((is_correct IS NULL) = (answered_at IS NULL))     -- cevap ile cevap zamanı birlikte dolar
);

-- Kısmi UNIQUE indeksler ile iş kuralları:
-- bir kullanıcının aynı anda tek açık oyunu olur
CREATE UNIQUE INDEX IF NOT EXISTS uq_quiz_one_active_game ON quiz_games (user_id) WHERE ended_at IS NULL;
-- bir oyunda aynı anda tek cevaplanmamış soru olur
CREATE UNIQUE INDEX IF NOT EXISTS uq_quiz_one_open_round ON quiz_rounds (game_id) WHERE is_correct IS NULL;
-- bir oyuncu aynı oyunda yalnızca bir kez cevap olarak kullanılabilir
CREATE UNIQUE INDEX IF NOT EXISTS uq_quiz_player_once ON quiz_rounds (game_id, answer_player_id) WHERE answer_player_id IS NOT NULL;
-- lider tablosu için
CREATE INDEX IF NOT EXISTS idx_quiz_games_user ON quiz_games (user_id, streak);

-- Büyük kulüpler: Real Madrid, Barcelona, Atlético, Man City, Man United, Liverpool, Chelsea, Arsenal, Tottenham,
-- Bayern, Dortmund, Juventus, Inter, Milan, PSG, Galatasaray, Fenerbahçe, Beşiktaş.
-- Veritabanında bulunmayan kimlik varsa atlanır.
INSERT INTO quiz_clubs (club_id)
SELECT club_id FROM clubs
WHERE club_id IN (418, 131, 13, 281, 985, 31, 631, 11, 148, 27, 16, 506, 46, 5, 583, 141, 36, 114)
ON CONFLICT DO NOTHING;
