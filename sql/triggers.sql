-- Tekrar çalıştırılabilir (idempotent).
-- TRIGGER: oyuncunun piyasa değeri eklendiğinde/değiştiğinde market_values tablosuna otomatik geçmiş kaydı yazar.
-- Uygulamadaki UPDATE ile aynı transaction içinde çalışır: güncelleme geri alınırsa geçmiş kaydı da geri alınır.
-- Aynı gün birden fazla güncelleme yapılırsa o günün kaydı güncellenir (UNIQUE (player_id, valued_at)).
CREATE OR REPLACE FUNCTION log_market_value() RETURNS trigger AS $$
BEGIN
  IF NEW.market_value_eur IS NULL THEN
    RETURN NEW;
  END IF;
  IF TG_OP = 'UPDATE' AND NEW.market_value_eur IS NOT DISTINCT FROM OLD.market_value_eur THEN
    RETURN NEW;
  END IF;
  INSERT INTO market_values (player_id, valued_at, market_value_eur, club_id)
  VALUES (NEW.player_id, CURRENT_DATE, NEW.market_value_eur, NEW.club_id)
  ON CONFLICT (player_id, valued_at)
  DO UPDATE SET market_value_eur = EXCLUDED.market_value_eur, club_id = EXCLUDED.club_id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_market_value ON players;
CREATE TRIGGER trg_market_value
AFTER INSERT OR UPDATE OF market_value_eur ON players
FOR EACH ROW EXECUTE FUNCTION log_market_value();


-- TRIGGER: bir karşılaştırmada en fazla 4 oyuncu olabilir (5. oyuncu eklenirken hata verir).
CREATE OR REPLACE FUNCTION check_comparison_max() RETURNS trigger AS $$
BEGIN
  IF (SELECT count(*) FROM comparison_players WHERE comparison_id = NEW.comparison_id) >= 4 THEN
    RAISE EXCEPTION 'A comparison can have at most 4 players';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_comparison_max ON comparison_players;
CREATE TRIGGER trg_comparison_max
BEFORE INSERT ON comparison_players
FOR EACH ROW EXECUTE FUNCTION check_comparison_max();

-- ERTELENMİŞ (DEFERRED) CONSTRAINT TRIGGER: karşılaştırmada en az 2 oyuncu olmalı.
-- Başlık satırı önce, oyuncular sonra eklendiği için kontrol COMMIT anına ertelenir;
-- kural sağlanmazsa transaction'ın tamamı geri alınır.
CREATE OR REPLACE FUNCTION check_comparison_min() RETURNS trigger AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM comparisons WHERE comparison_id = NEW.comparison_id)
     AND (SELECT count(*) FROM comparison_players WHERE comparison_id = NEW.comparison_id) < 2 THEN
    RAISE EXCEPTION 'A comparison must have at least 2 players';
  END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_comparison_min ON comparisons;
CREATE CONSTRAINT TRIGGER trg_comparison_min
AFTER INSERT ON comparisons
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION check_comparison_min();