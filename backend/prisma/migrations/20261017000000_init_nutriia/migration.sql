CREATE SCHEMA IF NOT EXISTS "public";

CREATE TYPE "user_objective" AS ENUM ('weight_loss', 'muscle_gain');
CREATE TYPE "capture_type" AS ENUM ('ean', 'label_photo');
CREATE TYPE "source_status" AS ENUM ('found', 'not_found', 'insufficient');
CREATE TYPE "analysis_verdict" AS ENUM ('recommended', 'attention', 'avoid', 'insufficient');
CREATE TYPE "confidence_state" AS ENUM ('sufficient', 'insufficient');
CREATE TYPE "ingredient_match_type" AS ENUM ('allergen', 'avoided_ingredient', 'preference', 'hidden_term', 'none');

CREATE TABLE "user_profiles" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "name_or_nickname" VARCHAR(120) NOT NULL,
    "email" VARCHAR(320) NOT NULL,
    "age_range" VARCHAR(40),
    "objective" "user_objective" NOT NULL,
    "declared_allergies" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "avoided_ingredients" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "food_preferences" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "onboarding_completed" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "user_profiles_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "products" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "ean" VARCHAR(32),
    "name" VARCHAR(240),
    "brand" VARCHAR(160),
    "serving_information" JSONB,
    "nutrition_table" JSONB,
    "ingredients_raw" TEXT,
    "ingredients_normalized" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "source_reference" TEXT,
    "source_updated_at" TIMESTAMPTZ(6),
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "products_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "product_captures" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "user_id" UUID NOT NULL,
    "product_id" UUID,
    "capture_type" "capture_type" NOT NULL,
    "ean" VARCHAR(32),
    "image_reference" TEXT,
    "captured_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "source_status" "source_status" NOT NULL,

    CONSTRAINT "product_captures_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "analysis_results" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "user_id" UUID NOT NULL,
    "product_id" UUID NOT NULL,
    "cache_key" VARCHAR(64),
    "verdict" "analysis_verdict" NOT NULL,
    "ui_label" VARCHAR(80) NOT NULL,
    "summary" TEXT NOT NULL,
    "critical_alerts" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "reasons" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "matched_restrictions" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "confidence_state" "confidence_state" NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "analysis_results_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "ingredient_matches" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "analysis_result_id" UUID NOT NULL,
    "raw_name" VARCHAR(240) NOT NULL,
    "normalized_name" VARCHAR(240) NOT NULL,
    "match_type" "ingredient_match_type" NOT NULL,
    "matched_profile_term" VARCHAR(240),
    "explanation" TEXT NOT NULL,
    "evidence_reference" TEXT,

    CONSTRAINT "ingredient_matches_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "user_profiles_email_key" ON "user_profiles"("email");
CREATE UNIQUE INDEX "products_ean_key" ON "products"("ean");
CREATE INDEX "products_name_brand_idx" ON "products"("name", "brand");
CREATE INDEX "products_source_updated_at_idx" ON "products"("source_updated_at");
CREATE INDEX "product_captures_user_id_captured_at_idx" ON "product_captures"("user_id", "captured_at" DESC);
CREATE INDEX "product_captures_product_id_captured_at_idx" ON "product_captures"("product_id", "captured_at" DESC);
CREATE INDEX "product_captures_ean_idx" ON "product_captures"("ean");
CREATE UNIQUE INDEX "analysis_results_cache_key_key" ON "analysis_results"("cache_key");
CREATE INDEX "analysis_results_user_id_created_at_idx" ON "analysis_results"("user_id", "created_at" DESC);
CREATE INDEX "analysis_results_product_id_created_at_idx" ON "analysis_results"("product_id", "created_at" DESC);
CREATE INDEX "ingredient_matches_analysis_result_id_idx" ON "ingredient_matches"("analysis_result_id");
CREATE INDEX "ingredient_matches_normalized_name_idx" ON "ingredient_matches"("normalized_name");

ALTER TABLE "product_captures"
    ADD CONSTRAINT "product_captures_user_id_fkey"
    FOREIGN KEY ("user_id") REFERENCES "user_profiles"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "product_captures"
    ADD CONSTRAINT "product_captures_product_id_fkey"
    FOREIGN KEY ("product_id") REFERENCES "products"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "analysis_results"
    ADD CONSTRAINT "analysis_results_user_id_fkey"
    FOREIGN KEY ("user_id") REFERENCES "user_profiles"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "analysis_results"
    ADD CONSTRAINT "analysis_results_product_id_fkey"
    FOREIGN KEY ("product_id") REFERENCES "products"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "ingredient_matches"
    ADD CONSTRAINT "ingredient_matches_analysis_result_id_fkey"
    FOREIGN KEY ("analysis_result_id") REFERENCES "analysis_results"("id") ON DELETE CASCADE ON UPDATE CASCADE;
