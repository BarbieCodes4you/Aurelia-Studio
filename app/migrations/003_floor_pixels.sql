-- Seating floor plan: pos_y becomes the table card's top edge in pixels from the top of the floor
-- (pos_x stays the card's centre as a percent of the floor's width). The editor now grows the floor to
-- fit every table, so rows of tables are never cut off. Earlier percent values convert against the
-- editor's 640px starting height.
UPDATE seating_tables SET pos_y = ROUND(pos_y * 6.4);
