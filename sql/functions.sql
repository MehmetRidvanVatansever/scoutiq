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