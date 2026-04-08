-- 创建默认管理员账号
-- 用户名: admin
-- 密码: admin123

USE novel_system;

-- 删除已存在的 admin 用户
DELETE FROM users WHERE username = 'admin';

-- 创建管理员账号
-- 密码 'admin123' 的 bcrypt 哈希
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
    '管理员',
    '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW',
    TRUE,
    TRUE,
    NOW(),
    NOW()
);

SELECT '管理员账号创建成功！' AS message;
SELECT username, email, is_superuser, is_active FROM users WHERE username = 'admin';
