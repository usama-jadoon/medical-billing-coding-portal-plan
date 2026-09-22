-- Initial PostgreSQL setup script for Medical Billing & Coding Portal
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Schema indices and performance optimizations
-- Ensure database encoding is UTF-8
SET client_encoding = 'UTF8';
