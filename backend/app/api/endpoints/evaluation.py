"""
八维 LLM Rubric 评测 API
（从原 training.py 拆分：RL 体系已移除，评测体系保留，§6.2）

提供八维 Rubric 评测 / 参考作品评测 / 采样评测 / 章节评测 / 评测历史 /
个人语料上传管理（按用户隔离存储）。
路径沿用 /training/evaluation/*。
"""
import asyncio
import json
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from loguru import logger

from app.core.auth import get_current_user, require_auth

router = APIRouter(prefix="/training", tags=["training"])

# 个人语料存储根目录：backend/data/user_uploads/{user_id}/
_UPLOAD_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "data" / "user_uploads"
_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5MB


def _user_upload_dir(user_id: int) -> Path:
    return _UPLOAD_ROOT / str(user_id)


def _safe_filename(name: str) -> str:
    """文件名消毒：保留中文/字母数字，前缀 uuid 防碰撞与穿越。"""
    base = re.sub(r"[^\w一-鿿.\-]", "_", Path(name or "").name).strip("._")
    if not base:
        base = "upload.txt"
    if not base.lower().endswith((".txt", ".md")):
        base += ".txt"
    return f"{uuid.uuid4().hex[:8]}_{base}"


def _guard_user_path(user_dir: Path, filename: str) -> Path:
    """路径防穿越：确保解析后的路径仍在本用户目录内。"""
    file_path = (user_dir / filename).resolve()
    try:
        file_path.relative_to(user_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="非法文件名")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return file_path


def _find_rules_file(project_dir: Path) -> Path:
    """定位评测规则 CSV（项目根目录或 scripts/evaluation/ 下）。"""
    candidates = [
        project_dir / "evaluate_rules_llm.csv",
        project_dir / "scripts" / "evaluation" / "evaluate_rules_llm.csv",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


# ============================================================
# 个人语料上传管理（按用户隔离）
# ============================================================

@router.post("/evaluation/upload", response_model=Dict[str, Any])
async def upload_reference_text(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_auth),
):
    """上传个人参考文本（.txt/.md，≤5MB，UTF-8），按用户隔离存储。"""
    filename = file.filename or ""
    if not filename.lower().endswith((".txt", ".md")):
        raise HTTPException(status_code=400, detail="仅支持 .txt / .md 文本文件")

    content = await file.read()
    size = len(content)
    if size > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"文件过大（限 {_MAX_UPLOAD_BYTES // 1024 // 1024}MB）")
    if not content.strip():
        raise HTTPException(status_code=400, detail="文件内容为空")

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="仅支持 UTF-8 编码文本")

    user_dir = _user_upload_dir(current_user["id"])
    user_dir.mkdir(parents=True, exist_ok=True)
    stored = _safe_filename(filename)
    (user_dir / stored).write_text(text, encoding="utf-8")

    logger.info(f"[Upload] user={current_user['id']} uploaded {stored} ({size} bytes)")
    return {
        "success": True,
        "filename": stored,
        "size_bytes": size,
        "char_count": len(text),
    }


@router.get("/evaluation/my-references", response_model=Dict[str, Any])
async def list_my_references(
    current_user: dict = Depends(require_auth),
):
    """列出当前用户的语料文件（仅元数据）。"""
    user_dir = _user_upload_dir(current_user["id"])
    files = []
    if user_dir.exists():
        for fp in sorted(user_dir.iterdir()):
            if fp.is_file() and fp.suffix.lower() in (".txt", ".md"):
                size = fp.stat().st_size
                files.append({
                    "filename": fp.name,
                    "name": fp.stem,
                    "size_bytes": size,
                    "size_kb": round(size / 1024, 1),
                })
    return {"success": True, "count": len(files), "files": files}


@router.get("/evaluation/my-reference/{filename}", response_model=Dict[str, Any])
async def get_my_reference(
    filename: str,
    current_user: dict = Depends(require_auth),
):
    """读取当前用户的语料文件内容。"""
    user_dir = _user_upload_dir(current_user["id"])
    file_path = _guard_user_path(user_dir, filename)
    content = file_path.read_text(encoding="utf-8")
    return {
        "success": True,
        "filename": filename,
        "content": content,
        "char_count": len(content),
    }


@router.delete("/evaluation/my-reference/{filename}", response_model=Dict[str, Any])
async def delete_my_reference(
    filename: str,
    current_user: dict = Depends(require_auth),
):
    """删除当前用户的语料文件。"""
    user_dir = _user_upload_dir(current_user["id"])
    file_path = _guard_user_path(user_dir, filename)
    file_path.unlink()
    logger.info(f"[Upload] user={current_user['id']} deleted {filename}")
    return {"success": True, "deleted": filename}


class EvaluationRequest(BaseModel):
    novel_id: Optional[int] = None
    text: Optional[str] = None
    genre: str = "玄幻"
    eval_type: str = "llm"  # "llm" | "keyword"


@router.get("/evaluation/references", response_model=Dict[str, Any])
async def list_reference_novels(
    current_user = Depends(get_current_user)
):
    """列出 reference 目录下所有可评测的小说文件（仅元数据，不读取内容）"""
    from pathlib import Path

    # 找到项目根目录 (KimiFiction/)
    # training.py 位置: backend/app/api/endpoints/training.py
    # 需要回到 KimiFiction/ 目录
    project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    ref_dir = project_root / "reference"

    files = []
    if ref_dir.exists():
        for fp in sorted(ref_dir.glob("*.txt")):
            # 只读取文件元数据，不读取内容
            stat = fp.stat()
            name = fp.stem
            author = "?"
            if "作者：" in name:
                parts = name.split("作者：")
                name = parts[0].strip()
                author = parts[1].strip() if len(parts) > 1 else "?"
            elif "by" in name:
                parts = name.split("by")
                name = parts[0].strip()
                author = parts[1].strip() if len(parts) > 1 else "?"

            files.append({
                "filename": fp.name,
                "name": name,
                "author": author,
                "size_kb": round(stat.st_size / 1024, 1),
                "size_bytes": stat.st_size,
                # char_count 和 word_count 标记为需要加载后才能获取
                "char_count": None,
                "word_count": None,
            })

    return {"success": True, "count": len(files), "files": files}


@router.get("/evaluation/reference/{filename}", response_model=Dict[str, Any])
async def get_reference_novel(
    filename: str,
    current_user = Depends(get_current_user)
):
    """读取 reference 目录下指定小说文件的内容"""
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    ref_dir = project_root / "reference"
    file_path = ref_dir / filename

    # 安全检查：确保文件在 reference 目录内
    try:
        file_path.resolve().relative_to(ref_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        content = file_path.read_text(encoding='utf-8')
        return {
            "success": True,
            "filename": filename,
            "content": content,
            "char_count": len(content),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")


@router.post("/evaluation/run", response_model=Dict[str, Any])
async def run_evaluation(
    request: EvaluationRequest,
    current_user = Depends(get_current_user)
):
    """
    运行八维 LLM Rubric 评测

    支持两种模式：
    - eval_type="llm": 调用 DeepSeek API 逐条判断 Yes/No
    - eval_type="keyword": 基于关键词规则评分
    """
    import os, re, json
    from pathlib import Path
    from collections import defaultdict
    import csv as csvmod
    from io import StringIO
    from datetime import datetime

    # 1. 加载规则
    backend_dir = Path(__file__).resolve().parent.parent.parent
    project_dir = backend_dir.parent
    rules_file = _find_rules_file(project_dir)
    if not rules_file.exists():
        return {"success": False, "error": f"规则文件不存在: {rules_file}"}

    # 加载 env
    backend_env = project_dir / "backend" / ".env"
    if backend_env.exists():
        with open(backend_env, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

    dims = {}
    rules = []
    with open(rules_file, "r", encoding="utf-8") as f:
        content = f.read()

    section = None
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("===") or line.startswith("---"):
            continue
        if line == "[dimensions]":
            section = "dims"
            continue
        elif line == "[rules]":
            section = "rules"
            continue
        if not section:
            continue
        try:
            reader = csvmod.reader(StringIO(line), quotechar='"')
            parts = next(reader)
        except:
            continue
        if section == "dims" and len(parts) >= 4:
            try:
                dims[parts[0]] = dict(id=parts[0], name=parts[1], weight=float(parts[2]), desc=parts[3])
            except:
                pass
        elif section == "rules" and len(parts) >= 4:
            did = parts[1].strip()
            w = dims.get(did, {}).get("weight", 0.1)
            rules.append({
                "rule_id": parts[0].strip(),
                "dimension": did,
                "name": parts[2].strip(),
                "desc": parts[3].strip() if len(parts) > 3 else "",
                "weight": w,
            })

    by_dim = defaultdict(list)
    for r in rules:
        by_dim[r["dimension"]].append(r)

    # 2. 获取评测文本
    text = request.text
    if not text:
        return {"success": False, "error": "text 为空"}

    # 截取用于评测的文本（不超过 20000 字）
    def eval_text(t):
        n = len(t)
        if n < 10000:
            return t
        head = t[: int(n * 0.3)]
        mid_start, mid_end = int(n * 0.35), int(n * 0.65)
        tail_start = int(n * 0.7)
        while len(head) + (mid_end - mid_start) + (n - tail_start) > 20000 and (mid_end - mid_start) > 1000:
            mid_end -= 1000
        return head + "\n[...省略中间...]\n" + t[mid_start:mid_end] + "\n[...省略...]\n" + t[tail_start:]

    eval_text_str = eval_text(text)

    # 3. LLM 评测
    provider = os.environ.get("LLM_PROVIDER", "deepseek")
    BATCH = 10
    judgments = []
    api_calls = 0

    if request.eval_type == "llm":
        if provider == "deepseek":
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
                base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            )
            model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
        else:
            return {"success": False, "error": f"不支持的 provider: {provider}"}

        for did, dinfo in dims.items():
            dim_rules = by_dim[did]
            for i in range(0, len(dim_rules), BATCH):
                batch = dim_rules[i : i + BATCH]
                api_calls += 1
                rules_text = "\n".join(
                    f"规则{i2+1} [{r['rule_id']}] {r['name']}:\n  {r['desc']}"
                    for i2, r in enumerate(batch)
                )

                prompt = (
                    f"小说片段:\n{eval_text_str}\n\n"
                    f"**评测规则**:\n{rules_text}\n\n"
                    f'**输出格式** (只输出JSON数组，不要其他文字):\n'
                    f'[{{"rule_id":"R1","answer":"Yes","reason":"判断依据"}},\n'
                    f' {{"rule_id":"R2","answer":"No","reason":"理由"}}]'
                )

                try:
                    resp = await client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": "你是严谨的小说评测专家。只输出JSON数组，answer只能是Yes或No。"},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.1,
                    )

                    text_resp = resp.choices[0].message.content
                    m = re.search(r"\[\s*\{.*?\}\s*\]", text_resp, re.DOTALL)
                    if m:
                        results = json.loads(m.group())
                        for item in results:
                            judgments.append({
                                "rule_id": item.get("rule_id", ""),
                                "dimension": did,
                                "answer": item.get("answer", "No").strip(),
                                "reason": item.get("reason", "")[:200],
                            })
                    else:
                        for r in batch:
                            judgments.append({"rule_id": r["rule_id"], "dimension": did, "answer": "No", "reason": "parse fail"})
                except Exception as e:
                    for r in batch:
                        judgments.append({"rule_id": r["rule_id"], "dimension": did, "answer": "No", "reason": str(e)[:100]})

                await asyncio.sleep(0.3)

    # 4. 计算各维度得分
    dim_results = []
    total_weighted = 0
    total_weight = 0
    judgment_map = {j["rule_id"]: j for j in judgments}

    for did, dinfo in dims.items():
        dim_rules = by_dim[did]
        dim_judgments = [judgment_map.get(r["rule_id"], {"answer": "No", "reason": ""}) for r in dim_rules]
        passed = sum(1 for j in dim_judgments if j.get("answer", "").lower() == "yes")
        score = max(1.0, min(10.0, (passed / len(dim_rules)) * 10)) if dim_rules else 5.0
        dim_results.append({
            "id": did,
            "name": dinfo["name"],
            "weight": dinfo["weight"],
            "weight_pct": round(dinfo["weight"] * 100, 1),
            "total_rules": len(dim_rules),
            "passed": passed,
            "failed": len(dim_rules) - passed,
            "score": round(score, 1),
            "bar": "\u2588" * int(score) + "\u2591" * (10 - int(score)),
            "judgments": [
                {
                    "rule_id": r["rule_id"],
                    "name": r["name"],
                    "answer": judgment_map.get(r["rule_id"], {}).get("answer", "No"),
                    "reason": judgment_map.get(r["rule_id"], {}).get("reason", "")[:80],
                }
                for r in dim_rules
            ],
        })
        total_weighted += score * dinfo["weight"]
        total_weight += dinfo["weight"]

    final_score = round(total_weighted / total_weight, 1) if total_weight > 0 else 0
    rank = "S" if final_score >= 90 else "A" if final_score >= 80 else "B" if final_score >= 70 else "C" if final_score >= 60 else "D" if final_score >= 50 else "F"

    # 5. 保存结果
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = project_dir / "training_runs"
    out_dir.mkdir(exist_ok=True)
    result = {
        "success": True,
        "eval_type": request.eval_type,
        "genre": request.genre,
        "timestamp": ts,
        "total_score": final_score,
        "rank": rank,
        "api_calls": api_calls,
        "dims": dim_results,
        "total_rules": len(rules),
    }

    json_path = out_dir / f"eval_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


@router.get("/evaluation/results", response_model=Dict[str, Any])
async def list_evaluation_results(
    limit: int = 20,
    current_user = Depends(get_current_user)
):
    """列出最近的评测结果"""
    from pathlib import Path
    import json

    backend_dir = Path(__file__).resolve().parent.parent.parent
    project_dir = backend_dir.parent
    out_dir = project_dir / "training_runs"

    results = []
    if out_dir.exists():
        for fp in sorted(out_dir.glob("eval_*.json"), reverse=True)[:limit]:
            try:
                with open(fp, encoding="utf-8") as f:
                    data = json.load(f)
                results.append({
                    "filename": fp.name,
                    "timestamp": data.get("timestamp", ""),
                    "eval_type": data.get("eval_type", ""),
                    "total_score": data.get("total_score", 0),
                    "rank": data.get("rank", ""),
                    "api_calls": data.get("api_calls", 0),
                    "genre": data.get("genre", ""),
                })
            except Exception:
                pass

    return {"success": True, "count": len(results), "results": results}


# ============================================================
# 八维 LLM Rubric 采样评测（逐块评测）
# ============================================================

class SampledEvaluationRequest(BaseModel):
    text: str
    num_blocks: int = 5          # 采样多少个文本块
    max_bytes_per_block: int = 10000  # 每个文本块最大字节数
    eval_type: str = "llm"       # "llm" | "keyword"
    genre: str = "玄幻"
    stream: bool = False         # 是否流式返回进度


def _load_rules_and_dims(project_dir: Path):
    """加载 evaluate_rules_llm.csv 中的维度和规则"""
    import csv as csvmod
    from io import StringIO
    from collections import defaultdict

    rules_file = _find_rules_file(project_dir)
    if not rules_file.exists():
        return None, None, f"规则文件不存在: {rules_file}"

    dims = {}
    rules = []
    with open(rules_file, "r", encoding="utf-8") as f:
        content = f.read()

    section = None
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("===") or line.startswith("---"):
            continue
        if line == "[dimensions]":
            section = "dims"
            continue
        elif line == "[rules]":
            section = "rules"
            continue
        if not section:
            continue
        try:
            reader = csvmod.reader(StringIO(line), quotechar='"')
            parts = next(reader)
        except Exception:
            continue
        if section == "dims" and len(parts) >= 4:
            try:
                dims[parts[0]] = dict(id=parts[0], name=parts[1], weight=float(parts[2]), desc=parts[3])
            except Exception:
                pass
        elif section == "rules" and len(parts) >= 4:
            did = parts[1].strip()
            w = dims.get(did, {}).get("weight", 0.1)
            rules.append({
                "rule_id": parts[0].strip(),
                "dimension": did,
                "name": parts[2].strip(),
                "desc": parts[3].strip() if len(parts) > 3 else "",
                "weight": w,
            })

    by_dim = defaultdict(list)
    for r in rules:
        by_dim[r["dimension"]].append(r)

    return dims, by_dim, None


def _split_into_blocks(text: str, max_bytes: int) -> list:
    """
    按句号（。！？.!?）切分文本，组装成不超过 max_bytes 的文本块。
    返回文本块列表。
    """
    import re

    # 用正则按句号切分，保留分隔符
    sentences = re.split(r'(?<=[。！？.!?])', text)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]

    if not sentences:
        return [text[:max_bytes]] if text.strip() else []

    blocks = []
    current_block = ""

    for sent in sentences:
        candidate = current_block + sent if current_block else sent
        if len(candidate.encode("utf-8")) > max_bytes and current_block:
            blocks.append(current_block)
            current_block = sent
        else:
            current_block = candidate

    if current_block:
        blocks.append(current_block)

    return blocks


def _sample_blocks(blocks: list, num_blocks: int) -> list:
    """
    均匀采样 num_blocks 个文本块。
    如果块数不足，则返回全部。
    """
    import math

    n = len(blocks)
    if n <= num_blocks:
        return list(enumerate(blocks))

    # 均匀采样：将文本分成 num_blocks 段，每段取中间的块
    indices = []
    segment_size = n / num_blocks
    for i in range(num_blocks):
        idx = int(segment_size * i + segment_size / 2)
        idx = min(idx, n - 1)
        indices.append(idx)

    return [(idx, blocks[idx]) for idx in indices]


def _get_llm_client():
    """从 LLMConfigManager 获取 OpenAI 兼容异步客户端"""
    from app.core.llm_config_manager import LLMConfigManager
    from openai import AsyncOpenAI

    config = LLMConfigManager.get_config()
    provider = config.get("provider", "deepseek")

    if provider in ("local_qwen", "local_llama"):
        raise ValueError("本地模型暂不支持采样评测，请切换到 API 模式")

    api_key = config.get("api_key") or ""
    base_url = config.get("base_url") or ""
    model = config.get("model") or "deepseek-chat"

    if not api_key:
        raise ValueError("未配置 API Key，请先在 API 配置页面设置")

    return AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=120.0), model


async def _sampled_eval_generator(request: SampledEvaluationRequest):
    """采样评测核心生成器，逐块评测并 yield NDJSON 进度事件。"""
    import os, re, time
    from pathlib import Path
    from collections import defaultdict
    from datetime import datetime

    backend_dir = Path(__file__).resolve().parent.parent.parent.parent
    project_dir = backend_dir.parent

    # 加载规则
    dims, by_dim, err = _load_rules_and_dims(project_dir)
    if err:
        yield json.dumps({"type": "error", "error": err}, ensure_ascii=False) + "\n"
        return

    # 加载环境变量（兼容）
    backend_env = project_dir / "backend" / ".env"
    if backend_env.exists():
        with open(backend_env, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

    # 1. 切块
    all_blocks = _split_into_blocks(request.text, request.max_bytes_per_block)
    if not all_blocks:
        yield json.dumps({"type": "error", "error": "文本为空或无法切分"}, ensure_ascii=False) + "\n"
        return

    # 2. 采样
    sampled = _sample_blocks(all_blocks, request.num_blocks)

    # 3. 获取 LLM 客户端
    try:
        client, model_name = _get_llm_client()
    except ValueError as e:
        yield json.dumps({"type": "error", "error": str(e)}, ensure_ascii=False) + "\n"
        return
    except Exception as e:
        yield json.dumps({"type": "error", "error": f"LLM 客户端初始化失败: {e}"}, ensure_ascii=False) + "\n"
        return

    total_rules = sum(len(by_dim[d]) for d in dims)
    yield json.dumps({
        "type": "init",
        "total_blocks": len(sampled),
        "total_dims": len(dims),
        "total_rules": total_rules,
    }, ensure_ascii=False) + "\n"

    # 4. 逐块评测
    BATCH = 10
    block_results = []
    total_api_calls = 0

    for block_idx, (orig_idx, block_text) in enumerate(sampled):
        block_judgments = {}  # rule_id -> {answer, reason}

        for did, dinfo in dims.items():
            dim_rules = by_dim[did]
            for i in range(0, len(dim_rules), BATCH):
                batch = dim_rules[i:i + BATCH]
                total_api_calls += 1

                rules_text = "\n".join(
                    f"规则{j2+1} [{r['rule_id']}] {r['name']}:\n  {r['desc']}"
                    for j2, r in enumerate(batch)
                )

                prompt = (
                    f"小说片段:\n{block_text}\n\n"
                    f"**评测规则**:\n{rules_text}\n\n"
                    f'**输出格式** (只输出JSON数组，不要其他文字):\n'
                    f'[{{"rule_id":"R1","answer":"Yes","reason":"判断依据"}},\n'
                    f' {{"rule_id":"R2","answer":"No","reason":"理由"}}]'
                )

                try:
                    resp = await client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": "你是严谨的小说评测专家。只输出JSON数组，answer只能是Yes或No。"},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.1,
                    )

                    text_resp = resp.choices[0].message.content
                    m = re.search(r"\[\s*\{.*?\}\s*\]", text_resp, re.DOTALL)
                    if m:
                        results = json.loads(m.group())
                        for item in results:
                            block_judgments[item.get("rule_id", "")] = {
                                "answer": item.get("answer", "No").strip(),
                                "reason": item.get("reason", "")[:200],
                            }
                    else:
                        for r in batch:
                            block_judgments.setdefault(r["rule_id"], {"answer": "No", "reason": "parse fail"})
                except Exception as e:
                    for r in batch:
                        block_judgments.setdefault(r["rule_id"], {"answer": "No", "reason": str(e)[:100]})

                await asyncio.sleep(0.3)

        # 计算该块的各维度得分
        dim_scores = []
        block_weighted = 0
        block_weight_total = 0

        for did, dinfo in dims.items():
            dim_rules = by_dim[did]
            passed = 0
            rule_details = []
            for r in dim_rules:
                j = block_judgments.get(r["rule_id"], {"answer": "No", "reason": ""})
                is_yes = j.get("answer", "No").lower() == "yes"
                if is_yes:
                    passed += 1
                rule_details.append({
                    "rule_id": r["rule_id"],
                    "name": r["name"],
                    "desc": r["desc"],
                    "answer": j.get("answer", "No"),
                    "reason": j.get("reason", ""),
                })

            score = max(1.0, min(10.0, (passed / len(dim_rules)) * 10)) if dim_rules else 5.0
            dim_scores.append({
                "id": did,
                "name": dinfo["name"],
                "weight": dinfo["weight"],
                "weight_pct": round(dinfo["weight"] * 100, 1),
                "score": round(score, 1),
                "passed": passed,
                "failed": len(dim_rules) - passed,
                "total_rules": len(dim_rules),
                "rules": rule_details,
            })
            block_weighted += score * dinfo["weight"]
            block_weight_total += dinfo["weight"]

        block_score = round(block_weighted / block_weight_total, 1) if block_weight_total > 0 else 0

        block_results.append({
            "block_index": block_idx + 1,
            "original_index": orig_idx,
            "total_blocks": len(sampled),
            "text_preview": block_text[:300] + ("..." if len(block_text) > 300 else ""),
            "text_length": len(block_text),
            "score": block_score,
            "dims": dim_scores,
        })

        yield json.dumps({
            "type": "progress",
            "current_block": block_idx + 1,
            "total_blocks": len(sampled),
            "block_index": orig_idx,
            "block_score": block_score,
            "api_calls": total_api_calls,
            "message": f"已完成第 {block_idx + 1}/{len(sampled)} 块评测",
        }, ensure_ascii=False) + "\n"

    # 5. 汇总：各维度平均分 + 总平均分
    dim_avg = {}
    for did in dims:
        scores = [b["score"] for b in block_results for d in b["dims"] if d["id"] == did]
        dim_avg[did] = round(sum(scores) / len(scores), 1) if scores else 0

    overall_avg = round(sum(b["score"] for b in block_results) / len(block_results), 1) if block_results else 0
    rank = "S" if overall_avg >= 90 else "A" if overall_avg >= 80 else "B" if overall_avg >= 70 else "C" if overall_avg >= 60 else "D" if overall_avg >= 50 else "F"

    # 各维度汇总（平均分）
    dim_summary = []
    total_weighted = 0
    total_weight = 0
    for did, dinfo in dims.items():
        avg_score = dim_avg.get(did, 0)
        dim_summary.append({
            "id": did,
            "name": dinfo["name"],
            "weight": dinfo["weight"],
            "weight_pct": round(dinfo["weight"] * 100, 1),
            "avg_score": avg_score,
            "bar": "\u2588" * int(avg_score) + "\u2591" * (10 - int(avg_score)),
        })
        total_weighted += avg_score * dinfo["weight"]
        total_weight += dinfo["weight"]

    final_score = round(total_weighted / total_weight, 1) if total_weight > 0 else 0
    final_rank = "S" if final_score >= 90 else "A" if final_score >= 80 else "B" if final_score >= 70 else "C" if final_score >= 60 else "D" if final_score >= 50 else "F"

    # 6. 保存结果
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = project_dir / "training_runs"
    out_dir.mkdir(exist_ok=True)

    result = {
        "success": True,
        "eval_type": "sampled_llm",
        "genre": request.genre,
        "timestamp": ts,
        "total_score": final_score,
        "rank": final_rank,
        "api_calls": total_api_calls,
        "sampling": {
            "total_blocks_in_text": len(all_blocks),
            "sampled_blocks": len(sampled),
            "max_bytes_per_block": request.max_bytes_per_block,
        },
        "dims": dim_summary,
        "blocks": block_results,
        "total_rules": total_rules,
    }

    json_path = out_dir / f"eval_sampled_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 7. 保存到数据库
    try:
        from app.core.database import get_session
        from app.models.rubric import SampledEvaluationHistory

        async with get_session() as session:
            # 确定来源类型和名称
            source_type = getattr(request, '_source_type', 'text')
            source_name = getattr(request, '_source_name', None)
            if not source_name:
                # 自动生成来源名称
                if source_type == 'file':
                    source_name = f"参考小说-{ts}"
                else:
                    # 文本摘要：前30个字符
                    text_preview = request.text[:50] if request.text else ""
                    source_name = text_preview[:30] + "..." if len(text_preview) > 30 else text_preview

            # 构建文本预览（前500字符）
            text_preview = request.text[:500] if request.text else None

            history_record = SampledEvaluationHistory(
                source_type=source_type,
                source_name=source_name[:255] if source_name else None,  # 限制长度
                genre=request.genre,
                num_blocks=request.num_blocks,
                max_bytes_per_block=request.max_bytes_per_block,
                total_blocks_in_text=len(all_blocks),
                sampled_blocks=len(sampled),
                total_score=final_score,
                rank=final_rank,
                api_calls=total_api_calls,
                result_data=result,
                text_preview=text_preview,
            )
            session.add(history_record)
            await session.commit()
            result["history_id"] = history_record.id
            logger.info(f"采样评测结果已保存到数据库，ID: {history_record.id}")
    except Exception as e:
        logger.error(f"保存采样评测结果到数据库失败: {e}")
        # 不影响正常返回结果

    yield json.dumps({"type": "result", "data": result}, ensure_ascii=False) + "\n"


@router.post("/evaluation/run-sampled")
async def run_sampled_evaluation(
    request: SampledEvaluationRequest,
    current_user = Depends(get_current_user)
):
    """
    采样评测：将小说文本切成多块，逐块进行八维 LLM Rubric 评测。

    stream=false（默认）: 返回完整 JSON 结果
    stream=true         : 返回 NDJSON 流，事件类型: init / progress / result / error
    """
    if request.stream:
        return StreamingResponse(
            _sampled_eval_generator(request),
            media_type="application/x-ndjson",
        )
    else:
        final_result = None
        async for line in _sampled_eval_generator(request):
            data = json.loads(line)
            if data.get("type") == "result":
                final_result = data["data"]
            elif data.get("type") == "error":
                return {"success": False, "error": data.get("error")}
        return final_result or {"success": False, "error": "未知错误"}


# ============================================================
# 章节八维评分查询接口
# ============================================================

@router.get("/evaluation/chapter/{novel_id}/{chapter_number}", response_model=Dict[str, Any])
async def get_chapter_evaluation(
    novel_id: int,
    chapter_number: int,
    current_user = Depends(get_current_user)
):
    """
    获取指定章节的八维评分结果

    优先从数据库查询已有的Rubric评测记录，如果没有则返回空结果
    """
    from sqlalchemy import select, desc
    from app.core.database import get_session
    from app.models.rubric import RubricEvaluation

    async with get_session() as session:
        # 查询最新的评测记录
        result = await session.execute(
            select(RubricEvaluation)
            .where(
                RubricEvaluation.novel_id == novel_id,
                RubricEvaluation.chapter_number == chapter_number
            )
            .order_by(desc(RubricEvaluation.created_at))
            .limit(1)
        )
        evaluation = result.scalar_one_or_none()

        if not evaluation:
            return {
                "success": True,
                "has_evaluation": False,
                "message": "该章节尚未进行八维评分",
                "novel_id": novel_id,
                "chapter_number": chapter_number,
            }

        # 构建维度得分详情
        dim_scores = []
        if evaluation.dimension_scores:
            for dim_id, dim_data in evaluation.dimension_scores.items():
                dim_scores.append({
                    "id": dim_id,
                    "name": dim_data.get("name", dim_id),
                    "weight": dim_data.get("weight", 0.1),
                    "weight_pct": round(dim_data.get("weight", 0.1) * 100, 1),
                    "score": dim_data.get("score", 0),
                    "bar": "█" * int(dim_data.get("score", 0)) + "░" * (10 - int(dim_data.get("score", 0))),
                })

        # 计算等级
        total_score = evaluation.total_score
        rank = "S" if total_score >= 9 else "A" if total_score >= 8 else "B" if total_score >= 7 else "C" if total_score >= 6 else "D" if total_score >= 5 else "F"

        return {
            "success": True,
            "has_evaluation": True,
            "novel_id": novel_id,
            "chapter_number": chapter_number,
            "evaluation_id": evaluation.id,
            "total_score": total_score,
            "weighted_score": evaluation.weighted_score,
            "rank": rank,
            "eval_type": evaluation.eval_type,
            "evaluator_type": evaluation.evaluator_type,
            "dims": dim_scores,
            "summary_feedback": evaluation.summary_feedback,
            "strengths": evaluation.strengths or [],
            "weaknesses": evaluation.weaknesses or [],
            "improvement_suggestions": evaluation.improvement_suggestions or [],
            "consistency_issues": evaluation.consistency_issues or [],
            "created_at": evaluation.created_at.isoformat() if evaluation.created_at else None,
        }


@router.post("/evaluation/chapter/{novel_id}/{chapter_number}/run", response_model=Dict[str, Any])
async def run_chapter_evaluation(
    novel_id: int,
    chapter_number: int,
    genre: str = "玄幻",
    num_blocks: int = 3,
    current_user = Depends(get_current_user)
):
    """
    对指定章节运行八维评分评测

    获取章节内容并执行采样评测
    """
    from app.models.chapter import Chapter
    from sqlalchemy import select
    from app.core.database import get_session

    async with get_session() as session:
        # 获取章节内容
        result = await session.execute(
            select(Chapter).where(
                Chapter.novel_id == novel_id,
                Chapter.chapter_number == chapter_number
            )
        )
        chapter = result.scalar_one_or_none()

        if not chapter or not chapter.content:
            return {
                "success": False,
                "error": "章节不存在或内容为空",
                "novel_id": novel_id,
                "chapter_number": chapter_number,
            }

        # 构建评测请求
        eval_request = SampledEvaluationRequest(
            text=chapter.content,
            num_blocks=num_blocks,
            max_bytes_per_block=8000,
            eval_type="llm",
            genre=genre,
            stream=False
        )

        # 执行评测（非流式）
        final_result = None
        async for line in _sampled_eval_generator(eval_request):
            data = json.loads(line)
            if data.get("type") == "result":
                final_result = data["data"]
            elif data.get("type") == "error":
                return {"success": False, "error": data.get("error")}

        if final_result:
            # 保存评测结果到数据库
            try:
                from app.models.rubric import RubricEvaluation, EvaluationType

                # 构建维度得分
                dim_scores = {}
                for dim in final_result.get("dims", []):
                    dim_scores[dim["id"]] = {
                        "name": dim["name"],
                        "weight": dim["weight"],
                        "score": dim["avg_score"],
                    }

                evaluation = RubricEvaluation(
                    novel_id=novel_id,
                    chapter_id=chapter.id if chapter else None,
                    chapter_number=chapter_number,
                    eval_type=EvaluationType.POST_TRAINING,
                    total_score=final_result.get("total_score", 0),
                    weighted_score=final_result.get("total_score", 0),
                    dimension_scores=dim_scores,
                    summary_feedback=f"章节八维评分完成，总分: {final_result.get('total_score', 0)}",
                )
                session.add(evaluation)
                await session.commit()
                final_result["evaluation_id"] = evaluation.id
            except Exception as e:
                logger.error(f"保存评测结果失败: {e}")

        return final_result or {"success": False, "error": "评测失败"}


# ============================================================
# 采样评测历史记录接口
# ============================================================

@router.get("/evaluation/history", response_model=Dict[str, Any])
async def get_evaluation_history(
    page: int = 1,
    page_size: int = 15,
    current_user = Depends(get_current_user)
):
    """
    获取采样评测历史记录列表（分页）

    - page: 页码，从1开始
    - page_size: 每页条数，默认15
    - 按创建时间倒序排列（最新的在前）
    """
    from sqlalchemy import select, func, desc
    from app.core.database import get_session
    from app.models.rubric import SampledEvaluationHistory

    async with get_session() as session:
        # 查询总数
        count_result = await session.execute(
            select(func.count()).select_from(SampledEvaluationHistory)
        )
        total = count_result.scalar() or 0

        # 查询当前页数据
        offset = (page - 1) * page_size
        result = await session.execute(
            select(SampledEvaluationHistory)
            .order_by(desc(SampledEvaluationHistory.created_at))
            .offset(offset)
            .limit(page_size)
        )
        records = result.scalars().all()

        return {
            "success": True,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "data": [record.to_summary_dict() for record in records],
        }


@router.get("/evaluation/history/{history_id}", response_model=Dict[str, Any])
async def get_evaluation_history_detail(
    history_id: int,
    current_user = Depends(get_current_user)
):
    """
    获取单条采样评测历史记录的详细信息
    """
    from sqlalchemy import select
    from app.core.database import get_session
    from app.models.rubric import SampledEvaluationHistory

    async with get_session() as session:
        result = await session.execute(
            select(SampledEvaluationHistory).where(SampledEvaluationHistory.id == history_id)
        )
        record = result.scalar_one_or_none()

        if not record:
            raise HTTPException(status_code=404, detail="评测记录不存在")

        return {
            "success": True,
            "data": record.to_detail_dict(),
        }
