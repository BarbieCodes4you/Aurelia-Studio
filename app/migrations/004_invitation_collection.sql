-- The invitation collection replaces the original designs in the catalogue. The original templates
-- stay in the table (every event that uses one keeps rendering, and the admin can switch any back on);
-- they are only hidden from the choices. Heritage stays and moves after the new designs, which
-- catalog.ensure_catalog() adds with sort 0-7.
UPDATE templates SET active = 0
 WHERE slug IN ('atelier', 'folio', 'bloom', 'champagne', 'linea', 'confetti', 'pulse', 'aurora', 'laureate', 'cradle');
UPDATE templates SET sort = 8 WHERE slug = 'heritage';
