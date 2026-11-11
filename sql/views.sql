-- Tekrar çalıştırılabilir (idempotent): mevcut veritabanına da güvenle uygulanır.
-- Aktif oyuncu = 2024 yılında en az bir maça çıkan oyuncu (players.is_active, scripts/season_data.py hesaplar).

-- View'lar her çalıştırmada silinip yeniden kurulur (sütun eklenebilsin diye).
DROP VIEW IF EXISTS top_starred_players, club_overview, club_roster, player_overview, player_career CASCADE;

-- ===== VIEW 1: oyuncu + ülke + pozisyon + kulüp + lig + gol/asist =====
CREATE VIEW player_overview AS
SELECT p.player_id, p.name,
       EXTRACT(YEAR FROM age(p.date_of_birth))::int AS age,
       c.name  AS country,
       pos.main_position, pos.sub_position,
       cl.name AS club,
       comp.name AS league,
       p.market_value_eur,
       s.goals, s.assists,
       p.club_id,
       p.date_of_birth
FROM players p
LEFT JOIN countries c       ON c.country_id = p.country_id
JOIN positions pos          ON pos.position_id = p.position_id
LEFT JOIN clubs cl          ON cl.club_id = p.club_id
LEFT JOIN competitions comp ON comp.competition_id = cl.competition_id
LEFT JOIN player_stats s    ON s.player_id = p.player_id
WHERE p.is_active;

-- ===== VIEW 2: en çok yıldızlanan oyuncular (alt sorgu + GROUP BY + window function) =====
CREATE VIEW top_starred_players AS
SELECT po.*,
       s.star_count,
       RANK() OVER (ORDER BY s.star_count DESC) AS rank
FROM (SELECT player_id, count(*) AS star_count
      FROM watchlist_players
      GROUP BY player_id) s
JOIN player_overview po ON po.player_id = s.player_id;

-- ===== VIEW 3: kulüp kadrosu = o kulüp adına 2024'te maça çıkanlar + şu an o kulübe kayıtlı aktif oyuncular =====
CREATE VIEW club_roster AS
SELECT club_id, player_id FROM players WHERE is_active AND club_id IS NOT NULL
UNION
SELECT club_id, player_id FROM club_squads;

-- ===== VIEW 4: kulüp özeti (GROUP BY + toplama fonksiyonları) =====
CREATE VIEW club_overview AS
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

-- ===== VIEW 5: oyuncunun kariyeri / önceki takımları (transferlerden, LEAD + ROW_NUMBER window function) =====
-- Her transfer, oyuncunun yeni kulübe katıldığı tarihtir; bir sonraki transfer tarihi o kulüpten ayrılış tarihidir.
-- İlk transferin "geldiği kulüp" de (katılış tarihi bilinmeden) listeye eklenir.
CREATE VIEW player_career AS
WITH t AS (
  SELECT player_id, from_club_id, to_club_id, transfer_date, season, fee_eur,
         ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY transfer_date, transfer_id) AS rn,
         LEAD(transfer_date) OVER (PARTITION BY player_id ORDER BY transfer_date, transfer_id) AS next_date
  FROM transfers
), stints AS (
  SELECT player_id, to_club_id AS club_id, transfer_date AS joined_at, next_date AS left_at, season, fee_eur
  FROM t
  UNION ALL
  SELECT player_id, from_club_id, NULL, transfer_date, NULL, NULL
  FROM t WHERE rn = 1
)
SELECT s.player_id, s.club_id, c.name AS club, s.joined_at, s.left_at, s.season, s.fee_eur,
       (c.competition_id IS NOT NULL) AS has_league
FROM stints s
JOIN clubs c ON c.club_id = s.club_id;
