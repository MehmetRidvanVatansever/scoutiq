-- Tekrar çalıştırılabilir (idempotent). Saklı fonksiyonlar (stored functions).
-- Fonksiyonlar, onları çağıran transaction'ın içinde çalışır: herhangi bir adım hata verirse hepsi geri alınır.

-- 1) Kullanıcı kaydı: ilk kayıt olan kullanıcı admin, sonrakiler scout olur.
-- users tablosu kilitlenir; böylece aynı anda gelen iki kayıt ikisi birden "ilk kullanıcı" sayılamaz.
CREATE OR REPLACE FUNCTION register_user(p_username VARCHAR, p_email VARCHAR, p_hash VARCHAR)
RETURNS VARCHAR AS $$
DECLARE
  v_role VARCHAR;
BEGIN
  LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE;
  v_role := CASE WHEN EXISTS (SELECT 1 FROM users) THEN 'scout' ELSE 'admin' END;
  INSERT INTO users (username, email, password_hash, role_id)
  VALUES (p_username, p_email, p_hash, (SELECT role_id FROM roles WHERE name = v_role));
  RETURN v_role;
END;
$$ LANGUAGE plpgsql;

-- 2) Oyuncu ekleme: oyuncu + istatistik satırı + denetim kaydı tek seferde, yeni id'yi döndürür.
-- Kaynak veriden gelen id'ler sıralı olmadığı için yeni id max(player_id)+1 ile verilir; tablo kilidi
-- transaction sonuna kadar tutulduğundan aynı anda iki ekleme aynı id'yi alamaz.
-- Değer girildiyse trg_market_value trigger'ı market_values tablosuna ilk kaydı otomatik yazar.
CREATE OR REPLACE FUNCTION add_player(p_admin INT, p_name VARCHAR, p_country INT, p_position INT,
                                      p_club INT, p_dob DATE, p_foot VARCHAR, p_height INT,
                                      p_value BIGINT)
RETURNS INT AS $$
DECLARE
  v_id INT;
BEGIN
  IF trim(coalesce(p_name, '')) = '' THEN
    RAISE EXCEPTION 'Player name cannot be empty';
  END IF;
  LOCK TABLE players IN SHARE ROW EXCLUSIVE MODE;
  SELECT COALESCE(max(player_id), 0) + 1 INTO v_id FROM players;
  INSERT INTO players (player_id, name, country_id, position_id, club_id, date_of_birth,
                       foot, height_cm, market_value_eur, is_active)
  VALUES (v_id, trim(p_name), p_country, p_position, p_club, p_dob, p_foot, p_height, p_value, TRUE);
  INSERT INTO player_stats (player_id) VALUES (v_id);
  INSERT INTO audit_log (user_id, action, table_name, record_id) VALUES (p_admin, 'INSERT', 'players', v_id);
  RETURN v_id;
END;
$$ LANGUAGE plpgsql;

-- 3) Quiz – yeni soru: oyunda henüz kullanılmamış ortak oyuncusu olan rastgele bir kulüp çifti seçer.
-- Bir önceki soruyla aynı çift sorulmaz. Sorulacak çift kalmadıysa oyunu bitirir ve NULL döndürür.
CREATE OR REPLACE FUNCTION quiz_next_round(p_game INT) RETURNS INT AS $$
DECLARE
  v_a INT; v_b INT; v_id INT;
BEGIN
  WITH used AS (SELECT answer_player_id AS pid FROM quiz_rounds
                WHERE game_id = p_game AND answer_player_id IS NOT NULL),
       last AS (SELECT club_a, club_b FROM quiz_rounds WHERE game_id = p_game
                ORDER BY round_id DESC LIMIT 1),
       pc AS (SELECT * FROM player_clubs WHERE club_id IN (SELECT club_id FROM quiz_clubs)
              AND player_id NOT IN (SELECT pid FROM used))
  SELECT a.club_id, b.club_id INTO v_a, v_b
  FROM pc a
  JOIN pc b ON b.player_id = a.player_id AND b.club_id > a.club_id
  WHERE NOT EXISTS (SELECT 1 FROM last l WHERE least(l.club_a, l.club_b) = a.club_id
                                           AND greatest(l.club_a, l.club_b) = b.club_id)
  GROUP BY a.club_id, b.club_id
  ORDER BY random()
  LIMIT 1;

  IF v_a IS NULL THEN
    UPDATE quiz_games SET ended_at = now() WHERE game_id = p_game AND ended_at IS NULL;
    RETURN NULL;
  END IF;
  IF random() < 0.5 THEN   -- kulüplerin ekrandaki sırası da rastgele olsun
    SELECT v_b, v_a INTO v_a, v_b;
  END IF;
  INSERT INTO quiz_rounds (game_id, club_a, club_b) VALUES (p_game, v_a, v_b) RETURNING round_id INTO v_id;
  RETURN v_id;
END;
$$ LANGUAGE plpgsql;

-- 4) Quiz – cevap: hangi sorunun cevaplandığı (p_round) da gönderilir.
-- Oyun satırı FOR UPDATE ile kilitlenir; kilit alındıktan sonra soru hâlâ açık değilse (ör. form iki kez gönderildi)
-- 'Question already answered' hatası verilir, böylece ikinci gönderim bir sonraki soruyu cevaplamış sayılmaz.
-- Yazılan ad, iki kulüpte de oynamış ve bu oyunda henüz kullanılmamış oyuncularla pg_trgm benzerliğiyle
-- karşılaştırılır (en az 4 harf, word_similarity >= 0.55; ör. "mesi" → Lionel Messi).
-- Doğruysa seri 1 artar; yanlışsa oyun biter. Hepsi tek transaction'dır.
DROP FUNCTION IF EXISTS quiz_answer(INT, INT, VARCHAR);
CREATE OR REPLACE FUNCTION quiz_answer(p_user INT, p_round INT, p_text VARCHAR)
RETURNS TABLE (o_correct BOOLEAN, o_player_id INT, o_player_name VARCHAR, o_streak INT) AS $$
DECLARE
  v_round quiz_rounds%ROWTYPE;
  v_text  VARCHAR := lower(trim(coalesce(p_text, '')));
  v_pid   INT;
  v_name  VARCHAR;
  v_streak INT;
BEGIN
  PERFORM 1 FROM quiz_games g
  WHERE g.game_id = (SELECT r.game_id FROM quiz_rounds r WHERE r.round_id = p_round)
    AND g.user_id = p_user AND g.ended_at IS NULL
  FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'No active game';
  END IF;
  SELECT * INTO v_round FROM quiz_rounds WHERE round_id = p_round AND is_correct IS NULL;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Question already answered';
  END IF;

  IF length(v_text) >= 4 THEN
    SELECT p.player_id, p.name INTO v_pid, v_name
    FROM players p
    WHERE p.player_id IN (SELECT a.player_id FROM player_clubs a
                          JOIN player_clubs b ON b.player_id = a.player_id
                          WHERE a.club_id = v_round.club_a AND b.club_id = v_round.club_b)
      AND p.player_id NOT IN (SELECT answer_player_id FROM quiz_rounds
                              WHERE game_id = v_round.game_id AND answer_player_id IS NOT NULL)
      AND word_similarity(v_text, lower(p.name)) >= 0.55
    ORDER BY word_similarity(v_text, lower(p.name)) DESC, similarity(v_text, lower(p.name)) DESC
    LIMIT 1;
  END IF;

  UPDATE quiz_rounds
  SET answer_text = left(trim(p_text), 150), answer_player_id = v_pid,
      is_correct = (v_pid IS NOT NULL), answered_at = now()
  WHERE round_id = v_round.round_id;

  IF v_pid IS NOT NULL THEN
    UPDATE quiz_games SET streak = streak + 1 WHERE game_id = v_round.game_id RETURNING streak INTO v_streak;
  ELSE
    UPDATE quiz_games SET ended_at = now() WHERE game_id = v_round.game_id RETURNING streak INTO v_streak;
  END IF;
  RETURN QUERY SELECT (v_pid IS NOT NULL), v_pid, v_name, v_streak;
END;
$$ LANGUAGE plpgsql;
