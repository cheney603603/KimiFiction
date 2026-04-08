-- 初始化数据库
-- 创建必要的表和索引

-- 确保使用正确的字符集
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- users表
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

-- novels表
CREATE TABLE IF NOT EXISTS novels (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(255) NOT NULL COMMENT '小说标题',
    genre VARCHAR(100) COMMENT '小说类型',
    style_prompt TEXT COMMENT '风格提示词',
    total_chapters INT DEFAULT 0 COMMENT '总章节数',
    current_chapter INT DEFAULT 0 COMMENT '当前章节序号',
    total_words INT DEFAULT 0 COMMENT '总字数',
    status ENUM('planning', 'writing', 'paused', 'completed') DEFAULT 'planning' COMMENT '状态',
    target_chapters INT DEFAULT 100 COMMENT '目标章节数',
    words_per_chapter INT DEFAULT 3000 COMMENT '每章目标字数',
    genre_analysis TEXT COMMENT '类型分析结果JSON',
    world_setting TEXT COMMENT '世界观设定JSON',
    is_deleted BOOLEAN DEFAULT FALSE COMMENT '是否已删除',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_is_deleted (is_deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='小说项目表';

-- chapters表
CREATE TABLE IF NOT EXISTS chapters (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    novel_id BIGINT NOT NULL COMMENT '所属小说ID',
    chapter_number INT NOT NULL COMMENT '章节序号',
    title VARCHAR(255) NOT NULL COMMENT '章节标题',
    content LONGTEXT NOT NULL COMMENT '章节正文',
    summary TEXT COMMENT '本章摘要',
    key_events JSON COMMENT '关键事件列表',
    characters_present JSON COMMENT '出场角色列表',
    word_count INT DEFAULT 0 COMMENT '字数统计',
    status ENUM('draft', 'review', 'published') DEFAULT 'draft' COMMENT '状态',
    generation_params JSON COMMENT '生成参数',
    quality_score FLOAT COMMENT '质量评分',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_novel_chapter (novel_id, chapter_number),
    INDEX idx_novel_status (novel_id, status),
    FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='章节表';

-- characters表
CREATE TABLE IF NOT EXISTS characters (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    novel_id BIGINT NOT NULL COMMENT '所属小说ID',
    name VARCHAR(100) NOT NULL COMMENT '角色名称',
    role_type ENUM('protagonist', 'antagonist', 'supporting', 'minor') DEFAULT 'supporting' COMMENT '角色类型',
    profile JSON COMMENT '详细人设',
    current_status TEXT COMMENT '当前状态JSON',
    arc_progress FLOAT DEFAULT 0 COMMENT '角色弧光进度 0-1',
    first_appearance INT DEFAULT 1 COMMENT '首次出场章节',
    last_appearance INT COMMENT '最后出场章节',
    appearance_count INT DEFAULT 0 COMMENT '出场次数',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_novel_role (novel_id, role_type),
    INDEX idx_first_appearance (first_appearance),
    FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色表';

-- outlines表
CREATE TABLE IF NOT EXISTS outlines (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    novel_id BIGINT NOT NULL COMMENT '所属小说ID',
    volume_number INT NOT NULL COMMENT '第几卷',
    volume_title VARCHAR(255) NOT NULL COMMENT '卷标题',
    outline_type VARCHAR(50) DEFAULT 'main' COMMENT '大纲类型: main/detail',
    arcs JSON COMMENT '剧情弧数组',
    content TEXT COMMENT '大纲内容JSON(用于细纲等)'
    key_points TEXT COMMENT '关键节点',
    target_chapters INT DEFAULT 100 COMMENT '预计章节数',
    actual_chapters INT DEFAULT 0 COMMENT '实际章节数',
    summary TEXT COMMENT '卷摘要',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_novel_volume (novel_id, volume_number),
    FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='剧情大纲表';

-- memory_nodes表
CREATE TABLE IF NOT EXISTS memory_nodes (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    novel_id BIGINT NOT NULL COMMENT '所属小说ID',
    node_type ENUM('plot_point', 'character_moment', 'world_building', 'mystery', 'conflict', 'relationship') NOT NULL COMMENT '节点类型',
    title VARCHAR(255) NOT NULL COMMENT '节点标题',
    content TEXT NOT NULL COMMENT '节点内容',
    chapter_range VARCHAR(50) NOT NULL COMMENT '涉及章节范围',
    specific_chapter INT COMMENT '具体章节号',
    importance_score FLOAT DEFAULT 0.5 COMMENT '重要性 0-1',
    related_characters TEXT COMMENT '关联角色JSON',
    related_locations TEXT COMMENT '关联地点JSON',
    embedding_id VARCHAR(255) NOT NULL COMMENT '向量库ID',
    is_resolved BOOLEAN DEFAULT FALSE COMMENT '是否已解决',
    resolved_chapter INT COMMENT '解决章节',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_novel_type (novel_id, node_type),
    INDEX idx_importance (importance_score),
    INDEX idx_unresolved (novel_id, is_resolved),
    FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='记忆节点表';

SET FOREIGN_KEY_CHECKS = 1;
