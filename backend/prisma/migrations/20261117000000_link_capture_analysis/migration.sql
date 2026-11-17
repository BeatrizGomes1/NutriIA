-- Additive: legacy captures keep NULL links and are never guessed/backfilled.
ALTER TABLE product_captures ADD COLUMN request_id UUID;
ALTER TABLE product_captures ADD COLUMN analysis_id UUID;
ALTER TABLE product_captures ADD COLUMN analysis_origin VARCHAR(16);
ALTER TABLE product_captures ADD COLUMN processing_status VARCHAR(16);
CREATE UNIQUE INDEX product_captures_request_id_key ON product_captures(request_id);
ALTER TABLE product_captures ADD CONSTRAINT product_captures_analysis_id_fkey
    FOREIGN KEY (analysis_id) REFERENCES analysis_results(id) ON DELETE SET NULL;
