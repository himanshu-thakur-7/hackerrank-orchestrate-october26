-- Ghost Data Still Exists: point-in-time database snapshot
-- Dialect: SQLite-compatible SQL
-- Captured at: 2026-09-21T10:00:00Z
-- Database topology: read_replica
-- Compare the primary and any replica tables for replication drift.

BEGIN TRANSACTION;
CREATE TABLE customer_data_primary (
            resource_id TEXT PRIMARY KEY,
            origin_system TEXT NOT NULL,
            collection_name TEXT NOT NULL,
            record_json TEXT NOT NULL CHECK (json_valid(record_json)),
            updated_at TEXT NOT NULL
        );
INSERT INTO "customer_data_primary" VALUES('analytics_1738','analytics_platform','customer_analytics_reports','{"resource_id":"analytics_1738","user_id":"user_52","email":"bcarvalho6517@gmail.com","phone":"+55 41 90257-9346","email_hash":"da5e264130abacd259906dd79426f5ad182ed9e69c49fa2dd67166b655f644fa","reporting_window":"last_90_days","metrics":{"sessions_30d":12,"products_viewed_30d":6,"orders_completed_90d":3,"revenue_90d_usd":271.47},"recent_activity":[{"event":"product_viewed","product":"Ceramic coffee set"},{"event":"added_to_cart","product":"Ceramic coffee set"},{"event":"purchase_completed","product":"Ceramic coffee set","quantity":1}]}','2026-09-21T10:00:00Z');
CREATE TABLE customer_data_read_replica (
            resource_id TEXT PRIMARY KEY,
            origin_system TEXT NOT NULL,
            collection_name TEXT NOT NULL,
            record_json TEXT NOT NULL CHECK (json_valid(record_json)),
            updated_at TEXT NOT NULL
        );
INSERT INTO "customer_data_read_replica" VALUES('account_994','account_service','customer_profiles','{"resource_id":"account_994","customer_reference":"user_53","full_name":"Diya Kapoor","email":"diya.k4436@outlook.com","phone":"+91 96023 32879","account_status":"ACTIVE","signup_channel":"referral"}','2026-09-21T10:00:00Z');
INSERT INTO "customer_data_primary" VALUES('support_8903','support_platform','ticket_attachments','{"resource_id":"support_8903","ticket_id":"CS-7903","file_name":"delivery_confirmation_76.pdf","uploaded_by":"ana-varga@proton.me","storage_class":"ticket_attachment"}','2026-07-08T09:00:00Z');
INSERT INTO "customer_data_primary" VALUES('support_3772','support_platform','support_conversations','{"resource_id":"support_3772","ticket_id":"CS-7772","subject_reference":"user_254","channel":"email","message_text":"Please send the delivery update to mansour.yasmine@gmail.com. The affected order includes: Travel backpack."}','2026-06-13T11:00:00Z');
COMMIT;
