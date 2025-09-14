-- 南海舆情报告系统 - 数据库表结构
-- 请在Supabase SQL Editor中执行以下SQL语句

-- 1. 上传记录表
CREATE TABLE upload_records (
  id SERIAL PRIMARY KEY,
  filename VARCHAR(255) NOT NULL,
  file_path VARCHAR(500) NOT NULL,
  file_size INTEGER NOT NULL,
  upload_time TIMESTAMP DEFAULT NOW(),
  status VARCHAR(50) DEFAULT 'uploaded',
  error_message TEXT,
  report_path VARCHAR(500)
);

-- 2. 处理状态表
CREATE TABLE processing_status (
  id SERIAL PRIMARY KEY,
  upload_id INTEGER REFERENCES upload_records(id) ON DELETE CASCADE,
  current_step VARCHAR(50) NOT NULL,
  status VARCHAR(50) DEFAULT 'processing',
  progress FLOAT DEFAULT 0.0,
  message TEXT,
  error_message TEXT,
  created_time TIMESTAMP DEFAULT NOW(),
  updated_time TIMESTAMP DEFAULT NOW()
);

-- 3. 原始数据表
CREATE TABLE raw_data (
  id SERIAL PRIMARY KEY,
  upload_id INTEGER REFERENCES upload_records(id) ON DELETE CASCADE,
  url TEXT,
  source_name VARCHAR(255),
  author_username VARCHAR(255),
  title TEXT,
  hit_sentence TEXT,
  language VARCHAR(50),
  original_data JSONB,
  created_time TIMESTAMP DEFAULT NOW()
);

-- 4. 处理后数据表
CREATE TABLE processed_data (
  id SERIAL PRIMARY KEY,
  upload_id INTEGER REFERENCES upload_records(id) ON DELETE CASCADE,
  data_type VARCHAR(50) NOT NULL,
  structured_data JSONB NOT NULL,
  created_time TIMESTAMP DEFAULT NOW()
);

-- 5. 报告生成表
CREATE TABLE report_generations (
  id SERIAL PRIMARY KEY,
  upload_id INTEGER REFERENCES upload_records(id) ON DELETE CASCADE,
  report_path VARCHAR(500) NOT NULL,
  report_type VARCHAR(50) DEFAULT 'docx',
  generation_time TIMESTAMP DEFAULT NOW(),
  file_size INTEGER
);

-- 创建索引以提高查询性能
CREATE INDEX idx_upload_records_status ON upload_records(status);
CREATE INDEX idx_processing_status_upload_id ON processing_status(upload_id);
CREATE INDEX idx_raw_data_upload_id ON raw_data(upload_id);
CREATE INDEX idx_processed_data_upload_id ON processed_data(upload_id);
CREATE INDEX idx_report_generations_upload_id ON report_generations(upload_id);

-- 启用行级安全策略（RLS）
ALTER TABLE upload_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_status ENABLE ROW LEVEL SECURITY;
ALTER TABLE raw_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE processed_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_generations ENABLE ROW LEVEL SECURITY;

-- 为匿名用户创建访问策略（开发阶段，生产环境需要更严格的策略）
CREATE POLICY "Enable all operations for anon users on upload_records" ON upload_records FOR ALL TO anon USING (true);
CREATE POLICY "Enable all operations for anon users on processing_status" ON processing_status FOR ALL TO anon USING (true);
CREATE POLICY "Enable all operations for anon users on raw_data" ON raw_data FOR ALL TO anon USING (true);
CREATE POLICY "Enable all operations for anon users on processed_data" ON processed_data FOR ALL TO anon USING (true);
CREATE POLICY "Enable all operations for anon users on report_generations" ON report_generations FOR ALL TO anon USING (true);