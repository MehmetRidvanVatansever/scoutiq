-- Tekrar çalıştırılabilir (idempotent): mevcut veritabanına da güvenle uygulanır.

-- ===== İNDEKSLER =====
-- Ada göre arama "name ILIKE '%...%'" şeklindedir; başı joker olan bu arama normal B-tree indeksi kullanamaz.
-- pg_trgm (trigram) GIN indeksi bu aramayı hızlandırır.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
DROP INDEX IF EXISTS idx_players_name;
CREATE INDEX IF NOT EXISTS idx_players_name_trgm ON players USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_players_value   ON players (market_value_eur);
CREATE INDEX IF NOT EXISTS idx_players_birth   ON players (date_of_birth);   -- yaş filtresi doğum tarihine çevrilerek sorgulanır
CREATE INDEX IF NOT EXISTS idx_players_country ON players (country_id);
CREATE INDEX IF NOT EXISTS idx_players_pos     ON players (position_id);
CREATE INDEX IF NOT EXISTS idx_players_club    ON players (club_id);
CREATE INDEX IF NOT EXISTS idx_clubs_comp      ON clubs (competition_id);
CREATE INDEX IF NOT EXISTS idx_wp_player       ON watchlist_players (player_id);
CREATE INDEX IF NOT EXISTS idx_squads_player   ON club_squads (player_id);
CREATE INDEX IF NOT EXISTS idx_tr_player       ON transfers (player_id, transfer_date);
CREATE INDEX IF NOT EXISTS idx_tr_from         ON transfers (from_club_id);
CREATE INDEX IF NOT EXISTS idx_tr_to           ON transfers (to_club_id);
-- market_values (player_id, valued_at) için UNIQUE kısıtı zaten indeks oluşturur
