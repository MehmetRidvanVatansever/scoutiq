-- Tekrar çalıştırılabilir (idempotent): mevcut veritabanına da güvenle uygulanır.
-- Aktif oyuncu = 2024 yılında en az bir maça çıkan oyuncu (players.is_active, scripts/season_data.py hesaplar).

-- ===== İNDEKSLER =====
CREATE INDEX IF NOT EXISTS idx_players_name    ON players (lower(name));
CREATE INDEX IF NOT EXISTS idx_players_value   ON players (market_value_eur);
CREATE INDEX IF NOT EXISTS idx_players_birth   ON players (date_of_birth);
CREATE INDEX IF NOT EXISTS idx_players_country ON players (country_id);
CREATE INDEX IF NOT EXISTS idx_players_pos     ON players (position_id);
CREATE INDEX IF NOT EXISTS idx_players_club    ON players (club_id);
CREATE INDEX IF NOT EXISTS idx_clubs_comp      ON clubs (competition_id);
CREATE INDEX IF NOT EXISTS idx_wp_player       ON watchlist_players (player_id);
CREATE INDEX IF NOT EXISTS idx_squads_player   ON club_squads (player_id);

-- ===== VIEW 1: oyuncu + ülke + pozisyon + kulüp + lig + gol/asist =====
CREATE OR REPLACE VIEW player_overview AS
SELECT p.player_id, p.name,
       EXTRACT(YEAR FROM age(p.date_of_birth))::int AS age,
       c.name  AS country,
       pos.main_position, pos.sub_position,
       cl.name AS club,
       comp.name AS league,
       p.market_value_eur,
       s.goals, s.assists,
       p.club_id
FROM players p
LEFT JOIN countries c       ON c.country_id = p.country_id
JOIN positions pos          ON pos.position_id = p.position_id
LEFT JOIN clubs cl          ON cl.club_id = p.club_id
LEFT JOIN competitions comp ON comp.competition_id = cl.competition_id
LEFT JOIN player_stats s    ON s.player_id = p.player_id
WHERE p.is_active;

-- ===== VIEW 2: en çok yıldızlanan oyuncular (alt sorgu + GROUP BY + window function) =====
CREATE OR REPLACE VIEW top_starred_players AS
SELECT po.*,
       s.star_count,
       RANK() OVER (ORDER BY s.star_count DESC) AS rank
FROM (SELECT player_id, count(*) AS star_count
      FROM watchlist_players
      GROUP BY player_id) s
JOIN player_overview po ON po.player_id = s.player_id;

-- ===== VIEW 3: kulüp kadrosu = o kulüp adına 2024'te maça çıkanlar + şu an o kulübe kayıtlı aktif oyuncular =====
CREATE OR REPLACE VIEW club_roster AS
SELECT club_id, player_id FROM players WHERE is_active AND club_id IS NOT NULL
UNION
SELECT club_id, player_id FROM club_squads;

-- ===== VIEW 4: kulüp özeti (GROUP BY + toplama fonksiyonları) =====
CREATE OR REPLACE VIEW club_overview AS
SELECT cl.club_id, cl.name,
       comp.name AS league,
       co.name   AS country,
       count(p.player_id)       AS player_count,
       sum(p.market_value_eur)  AS total_value,
       round(avg(EXTRACT(YEAR FROM age(p.date_of_birth)))::numeric, 1) AS avg_age
FROM clubs cl
LEFT JOIN competitions comp ON comp.competition_id = cl.competition_id
LEFT JOIN countries co      ON co.country_id = comp.country_id
LEFT JOIN club_roster r     ON r.club_id = cl.club_id
LEFT JOIN players p         ON p.player_id = r.player_id
GROUP BY cl.club_id, cl.name, comp.name, co.name;