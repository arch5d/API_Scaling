CREATE TABLE IF NOT EXISTS articles (
  id BIGSERIAL PRIMARY KEY,
  title VARCHAR(200) NOT NULL,
  slug VARCHAR(220) NOT NULL UNIQUE,
  body TEXT NOT NULL,
  author_id BIGINT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS articles_created_at_id_idx
  ON articles (created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS articles_author_id_idx
  ON articles (author_id);
