INSERT INTO articles (title, slug, body, author_id)
SELECT
  'Seed article ' || series_num,
  'seed-article-' || series_num,
  'This is benchmark data for article ' || series_num,
  NULL
FROM generate_series(1, 100000) AS series_num
ON CONFLICT (slug) DO NOTHING;

ANALYZE articles;
