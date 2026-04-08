"""Pytest 配置文件"""
import sys
import pytest
from pathlib import Path

# 添加 backend 到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# pytest-asyncio 配置
pytest_plugins = ["pytest_asyncio"]


def pytest_configure(config):
    """Pytest 配置钩子"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )


# ─────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────

@pytest.fixture
def mock_novel_id():
    """模拟小说ID"""
    return 1


@pytest.fixture
def mock_chapter_content():
    """模拟章节内容（测试用）"""
    return """
    李云站在城门口，望着远处的群山。他从未想过自己会踏上这条路。

    三个月前，他还是一个普通的书生，每天只知道埋头苦读圣贤书。然而一场突如其来的变故，彻底改变了他的命运。

    "少爷，我们该走了。"身后传来老管家低沉的声音。

    李云深吸一口气，转身离去。他的心中充满了对未来的迷茫，但也有着一丝难以言说的期待。

    城内的街道依然热闹，吆喝声、讨价还价声不绝于耳。他穿过熙熙攘攘的人群，每一步都仿佛踩在自己的心上。

    "爹，娘，孩儿不孝，不能在你们膝下尽孝了。"他在心中默念。

    城外的风景逐渐开阔起来，远处是一片金黄的麦田，微风吹过，掀起层层波浪。李云忽然觉得，或许离开这座困了他十八年的城，未必不是一件好事。

    前方还有更长的路要走，还有更多的人要遇见，还有更精彩的故事等待着他。
    """


@pytest.fixture
def mock_chapter_outline():
    """模拟章节大纲"""
    return {
        "chapter_number": 5,
        "title": "离别",
        "summary": "李云在城门口告别过去，踏上未知的旅程。三个月前的变故让他不得不离开家园，心中充满迷茫但也有期待。",
        "key_events": [
            "李云在城门口回顾过去",
            "与老管家告别",
            "穿过热闹的街道",
            "看到城外风景，心态转变",
        ],
        "scenes": ["城门口", "城内街道", "城外麦田"],
        "word_count_target": 3000,
    }


@pytest.fixture
def mock_characters():
    """模拟角色列表"""
    return [
        {
            "name": "李云",
            "role_type": "protagonist",
            "profile": {
                "age": 18,
                "personality": "沉稳内敛，富有责任感",
                "background": "普通书生，因变故被迫离开家园",
                "goals": ["寻找真相", "保护家人"],
                "dialogue_style": "简洁有力，偶有文雅用词",
            }
        },
        {
            "name": "老管家",
            "role_type": "supporting",
            "profile": {
                "age": 60,
                "personality": "忠诚可靠",
                "background": "李家三代老仆",
                "dialogue_style": "恭敬谦卑",
            }
        }
    ]


@pytest.fixture
def mock_world_setting():
    """模拟世界观设定"""
    return {
        "name": "九州大陆",
        "era": "乱世",
        "power_systems": [
            {
                "name": "内功",
                "description": "通过修炼体内真气提升实力，共分九重境界",
            }
        ],
        "major_factions": ["青云门", "玄冥教", "天机阁"],
    }


@pytest.fixture
def mock_redis():
    """模拟 Redis 客户端"""
    from unittest.mock import AsyncMock
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.scan_iter = AsyncMock(return_value=iter([]))
    return redis


@pytest.fixture
def mock_vector_store():
    """模拟向量存储"""
    from unittest.mock import AsyncMock, MagicMock
    store = MagicMock()
    store.search = AsyncMock(return_value=[])
    store.add_document = AsyncMock(return_value=True)
    store.delete_by_filter = AsyncMock(return_value=True)
    store.count_documents = AsyncMock(return_value=0)
    return store


@pytest.fixture
def mock_embedding_service():
    """模拟嵌入服务"""
    from unittest.mock import AsyncMock, MagicMock
    service = MagicMock()
    service.get_embedding = AsyncMock(return_value=[0.1] * 1536)
    return service


@pytest.fixture(scope="session")
def backend_path():
    """Backend 目录路径"""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def project_root():
    """项目根目录"""
    return Path(__file__).parent.parent.parent
