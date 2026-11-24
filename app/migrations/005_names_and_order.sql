-- Matcha becomes "Pilates and matcha" (unless the admin renamed it), and the catalogue leads with
-- Festive, Pilates and matcha and Heritage (the traditional wedding, now with an edition per culture).
-- New templates (Teddy, Reveal, Memorial) are added by catalog.ensure_catalog() in the same order.
UPDATE templates SET name = 'Pilates and matcha', direction = 'Pink stripes, olive bow, matcha' WHERE slug = 'matcha' AND name = 'Matcha';
UPDATE templates SET direction = 'Traditional wedding, an edition per culture',
  description = 'A gatefold that opens on a beaded medallion, in an edition for each culture: Ndebele, Zulu, Xhosa, Pedi, Venda, Tsonga and Swati, each with its own pattern, emblem and word for the wedding.',
  tags = '["traditional","7 cultures","animated gatefold"]'
 WHERE slug = 'heritage' AND direction = 'African traditional luxury';
UPDATE templates SET direction = 'Champagne pop and a golden ticket',
  description = 'A champagne bottle pops, bubbles fizz up the page and gold confetti falls around a golden ticket. For New Year''s, year-end parties, engagements and anniversaries.',
  tags = '["new year","champagne","confetti"]'
 WHERE slug = 'cheers' AND direction = 'Retro champagne toast';
UPDATE templates SET sort = 0 WHERE slug = 'festive';
UPDATE templates SET sort = 1 WHERE slug = 'matcha';
UPDATE templates SET sort = 2 WHERE slug = 'heritage';
UPDATE templates SET sort = 3 WHERE slug = 'nguni';
UPDATE templates SET sort = 4 WHERE slug = 'terracotta';
UPDATE templates SET sort = 5 WHERE slug = 'ribbon';
UPDATE templates SET sort = 6 WHERE slug = 'weave';
UPDATE templates SET sort = 9 WHERE slug = 'glitter';
UPDATE templates SET sort = 10 WHERE slug = 'cheers';
