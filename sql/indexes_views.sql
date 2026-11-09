CREATE INDEX idx_players_name    ON players (lower(name));
CREATE INDEX idx_players_value   ON players (market_value_eur);
CREATE INDEX idx_players_birth   ON players (date_of_birth);
CREATE INDEX idx_players_country ON players (country_id);
CREATE INDEX idx_players_pos     ON players (position_id);
CREATE INDEX idx_players_club    ON players (club_id);
CREATE INDEX idx_clubs_comp      ON clubs (competition_id);

CREATE VIEW player_overview AS
SELECT p.player_id, p.name,
       EXTRACT(YEAR FROM age(p.date_of_birth))::int AS age,
       c.name  AS country,
       pos.main_position, pos.sub_position,
       cl.name AS club,
       comp.name AS league,
       p.market_value_eur,
       s.goals, s.assists
FROM players p
LEFT JOIN countries c     ON c.country_id = p.country_id
JOIN positions pos        ON pos.position_id = p.position_id
LEFT JOIN clubs cl        ON cl.club_id = p.club_id
LEFT JOIN competitions comp ON comp.competition_id = cl.competition_id
LEFT JOIN player_stats s  ON s.player_id = p.player_id;