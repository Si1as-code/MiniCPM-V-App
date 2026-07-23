-- ============================================================
-- MiniCPM-V 云端数据库 Schema
-- PostgreSQL
-- ============================================================

-- -----------------------------------------------------------
-- 1. 自动更新 updated_at 列的函数和触发器
-- -----------------------------------------------------------

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- -----------------------------------------------------------
-- 2. users 表 - 用户账户
-- -----------------------------------------------------------

CREATE TABLE IF NOT EXISTS users (
    user_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone           VARCHAR(20) UNIQUE,
    email           VARCHAR(255) UNIQUE,
    avatar_url      TEXT,
    display_name    VARCHAR(100),
    password_hash   VARCHAR(255) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_phone ON users (phone);
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- -----------------------------------------------------------
-- 3. user_devices 表 - 用户设备
-- -----------------------------------------------------------

CREATE TABLE IF NOT EXISTS user_devices (
    id              SERIAL PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    device_id       VARCHAR(255) NOT NULL,
    platform        VARCHAR(50),
    push_token      TEXT,
    app_version     VARCHAR(50),
    last_sync_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_devices_user_id ON user_devices (user_id);
CREATE INDEX IF NOT EXISTS idx_user_devices_device_id ON user_devices (device_id);

-- -----------------------------------------------------------
-- 4. sync_log 表 - 数据同步日志
-- -----------------------------------------------------------

CREATE TABLE IF NOT EXISTS sync_log (
    id              SERIAL PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    device_id       VARCHAR(255),
    table_name      VARCHAR(100) NOT NULL,
    record_id       VARCHAR(255),
    operation       VARCHAR(20) NOT NULL CHECK (operation IN ('insert', 'update', 'delete')),
    data            JSONB,
    synced_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sync_log_user_id ON sync_log (user_id);
CREATE INDEX IF NOT EXISTS idx_sync_log_synced_at ON sync_log (synced_at);

-- -----------------------------------------------------------
-- 5. recognition_records_cloud 表 - 云端识别记录
-- -----------------------------------------------------------

CREATE TABLE IF NOT EXISTS recognition_records_cloud (
    id              SERIAL PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    image_hash      VARCHAR(64) NOT NULL,
    image_url       TEXT,
    question        TEXT,
    answer          TEXT,
    confidence      REAL,
    model_version   VARCHAR(50),
    device_id       VARCHAR(255),
    task_type       VARCHAR(50),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_recognition_records_cloud_image_hash ON recognition_records_cloud (image_hash);
CREATE INDEX IF NOT EXISTS idx_recognition_records_cloud_user_id ON recognition_records_cloud (user_id);

CREATE TRIGGER trg_recognition_records_cloud_updated_at
    BEFORE UPDATE ON recognition_records_cloud
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- -----------------------------------------------------------
-- 6. conversations_cloud 表 - 云端对话记录
-- -----------------------------------------------------------

CREATE TABLE IF NOT EXISTS conversations_cloud (
    id              SERIAL PRIMARY KEY,
    cloud_record_id INTEGER NOT NULL REFERENCES recognition_records_cloud(id) ON DELETE CASCADE,
    role            VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content         TEXT NOT NULL,
    token_count     INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------
-- 7. usage_stats_cloud 表 - 云端用量统计
-- -----------------------------------------------------------

CREATE TABLE IF NOT EXISTS usage_stats_cloud (
    id              SERIAL PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    date            DATE NOT NULL,
    local_count     INTEGER NOT NULL DEFAULT 0,
    api_count       INTEGER NOT NULL DEFAULT 0,
    tokens_used     INTEGER NOT NULL DEFAULT 0,
    cost            NUMERIC(10, 6) NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_usage_stats_cloud_user_date ON usage_stats_cloud (user_id, date);