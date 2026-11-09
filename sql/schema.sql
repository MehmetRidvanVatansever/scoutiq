DROP TABLE IF EXISTS audit_log, player_notes, search_history, comparison_players,
  comparisons, scout_reports, watchlist_players, watchlists, users, roles,
  player_stats, players, clubs, competitions, positions, countries CASCADE;

-- ===== VERI TABLOLARI =====
CREATE TABLE countries (
  country_id  SERIAL PRIMARY KEY,
  name        VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE positions (
  position_id    SERIAL PRIMARY KEY,
  main_position  VARCHAR(30) NOT NULL,
  sub_position   VARCHAR(40) NOT NULL,
  UNIQUE (main_position, sub_position)
);

CREATE TABLE competitions (
  competition_id  VARCHAR(10) PRIMARY KEY,
  name            VARCHAR(100) NOT NULL,
  country_id      INT REFERENCES countries(country_id)
);

CREATE TABLE clubs (
  club_id         INT PRIMARY KEY,
  name            VARCHAR(100) NOT NULL,
  competition_id  VARCHAR(10) REFERENCES competitions(competition_id)
);

CREATE TABLE players (
  player_id         INT PRIMARY KEY,
  name              VARCHAR(150) NOT NULL,
  country_id        INT REFERENCES countries(country_id),
  position_id       INT NOT NULL REFERENCES positions(position_id),
  club_id           INT REFERENCES clubs(club_id),
  date_of_birth     DATE,
  foot              VARCHAR(10),
  height_cm         INT CHECK (height_cm > 0),
  market_value_eur  BIGINT CHECK (market_value_eur >= 0)
);

CREATE TABLE player_stats (
  player_id  INT PRIMARY KEY REFERENCES players(player_id) ON DELETE CASCADE,
  goals      INT NOT NULL DEFAULT 0 CHECK (goals >= 0),
  assists    INT NOT NULL DEFAULT 0 CHECK (assists >= 0)
);

-- ===== SISTEM TABLOLARI =====
CREATE TABLE roles (
  role_id  SERIAL PRIMARY KEY,
  name     VARCHAR(20) NOT NULL UNIQUE
);

CREATE TABLE users (
  user_id        SERIAL PRIMARY KEY,
  username       VARCHAR(50) NOT NULL UNIQUE,
  email          VARCHAR(120) NOT NULL UNIQUE,
  password_hash  VARCHAR(255) NOT NULL,
  role_id        INT NOT NULL REFERENCES roles(role_id),
  created_at     TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE watchlists (
  watchlist_id  SERIAL PRIMARY KEY,
  user_id       INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  name          VARCHAR(80) NOT NULL,
  UNIQUE (user_id, name)
);

CREATE TABLE watchlist_players (
  watchlist_id  INT REFERENCES watchlists(watchlist_id) ON DELETE CASCADE,
  player_id     INT REFERENCES players(player_id) ON DELETE CASCADE,
  added_at      TIMESTAMP NOT NULL DEFAULT now(),
  PRIMARY KEY (watchlist_id, player_id)
);

CREATE TABLE scout_reports (
  report_id    SERIAL PRIMARY KEY,
  user_id      INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  player_id    INT NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
  rating       INT NOT NULL CHECK (rating BETWEEN 1 AND 10),
  report_text  TEXT NOT NULL,
  created_at   TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE comparisons (
  comparison_id  SERIAL PRIMARY KEY,
  user_id        INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  created_at     TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE comparison_players (
  comparison_id  INT REFERENCES comparisons(comparison_id) ON DELETE CASCADE,
  player_id      INT REFERENCES players(player_id) ON DELETE CASCADE,
  PRIMARY KEY (comparison_id, player_id)
);

CREATE TABLE search_history (
  search_id   SERIAL PRIMARY KEY,
  user_id     INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  filters     JSONB NOT NULL,
  created_at  TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE player_notes (
  note_id     SERIAL PRIMARY KEY,
  user_id     INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  player_id   INT NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
  note        TEXT NOT NULL,
  created_at  TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE audit_log (
  log_id      SERIAL PRIMARY KEY,
  user_id     INT REFERENCES users(user_id) ON DELETE SET NULL,
  action      VARCHAR(20) NOT NULL,
  table_name  VARCHAR(50) NOT NULL,
  record_id   INT,
  created_at  TIMESTAMP NOT NULL DEFAULT now()
);

INSERT INTO roles (name) VALUES ('admin'), ('scout');