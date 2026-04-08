-- 创建管理员账号脚本
-- 在 MySQL 命令行中执行

-- 1. 先创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS novel_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE novel_system;

-- 2. 创建用户表
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
    email VARCHAR(255) NOT NULL UNIQUE COMMENT '邮箱',
    nickname VARCHAR(100) COMMENT '昵称',
    hashed_password VARCHAR(255) NOT NULL COMMENT '密码哈希',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    is_superuser BOOLEAN DEFAULT FALSE COMMENT '是否超级用户',
    avatar VARCHAR(500) COMMENT '头像URL',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL COMMENT '最后登录时间',
    INDEX idx_username (username),
    INDEX idx_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- 3. 删除已存在的 admin 用户
DELETE FROM users WHERE username = 'admin';

-- 4. 创建管理员账号（密码: admin123）
INSERT INTO users (
    username, 
    email, 
    nickname, 
    hashed_password, 
    is_active, 
    is_superuser,
    created_at,
    updated_at
) VALUES (
    'admin',
    'admin@novelgen.com',
    'Admin',
    '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW',
    TRUE,
    TRUE,
    NOW(),
    NOW()
);

-- 5. 验证
SELECT '管理员账号创建成功！' AS message;
SELECT username, email, is_superuser, is_active FROM users WHERE username = 'admin';
