"""
模仿学习系统

从参考小说(reference文件夹)中提取写作模式和风格，
生成用于RL微调的训练数据。

主要功能：
1. 解析参考小说，提取章节结构
2. 分析写作风格和模式
3. 生成模仿学习训练样本
4. 评估模仿效果
"""
import json
import re
import os
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
from loguru import logger


@dataclass
class ChapterStructure:
    """章节结构"""
    chapter_number: int
    title: Optional[str]
    content: str
    word_count: int
    paragraphs: List[str]
    dialogue_count: int
    description_ratio: float


@dataclass
class WritingStyle:
    """写作风格特征"""
    avg_sentence_length: float
    avg_paragraph_length: float
    dialogue_ratio: float
    description_ratio: float
    punctuation_style: Dict[str, float]
    common_phrases: List[str]
    sentence_openings: List[str]


@dataclass
class ImitationSample:
    """模仿学习样本"""
    context: str                           # 上下文/大纲
    style_prompt: str                      # 风格提示
    output: str                            # 参考输出
    metadata: Dict[str, Any] = field(default_factory=dict)


class NovelParser:
    """小说解析器"""
    
    # 章节标题匹配模式
    CHAPTER_PATTERNS = [
        r'第[一二三四五六七八九十百千零\d]+章[\s：:]*([^\n]*)',  # 第X章：标题
        r'Chapter\s*\d+[\s:]*([^\n]*)',  # Chapter X: Title
        r'\d+[\.、\s]+([^\n]{0,30})',  # 1. 标题
    ]
    
    def parse_file(self, file_path: str) -> List[ChapterStructure]:
        """
        解析小说文件，提取章节
        
        Args:
            file_path: 小说文件路径
            
        Returns:
            章节结构列表
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            return self.parse_content(content)
            
        except Exception as e:
            logger.error(f"[NovelParser] 解析文件失败 {file_path}: {e}")
            return []
    
    def parse_content(self, content: str) -> List[ChapterStructure]:
        """解析小说内容"""
        chapters = []
        
        # 尝试匹配章节
        chapter_positions = []
        
        for pattern in self.CHAPTER_PATTERNS:
            matches = list(re.finditer(pattern, content, re.IGNORECASE))
            if len(matches) > 3:  # 至少匹配到3个章节才使用
                chapter_positions = [(m.start(), m.end(), m.group()) for m in matches]
                break
        
        if not chapter_positions:
            # 无法识别章节结构，作为单章处理
            chapters.append(self._create_chapter(1, None, content))
            return chapters
        
        # 提取各章节内容
        for i, (start, end, header) in enumerate(chapter_positions):
            # 章节标题
            title = self._extract_title(header)
            
            # 章节内容范围
            content_start = end
            content_end = chapter_positions[i + 1][0] if i + 1 < len(chapter_positions) else len(content)
            chapter_content = content[content_start:content_end].strip()
            
            if chapter_content:
                chapters.append(self._create_chapter(i + 1, title, chapter_content))
        
        return chapters
    
    def _extract_title(self, header: str) -> Optional[str]:
        """从章节标题中提取标题文本"""
        # 去除"第X章"等前缀
        for pattern in [r'第[一二三四五六七八九十百千零\d]+章[\s：:]*', r'Chapter\s*\d+[\s:]*']:
            header = re.sub(pattern, '', header, flags=re.IGNORECASE)
        return header.strip() or None
    
    def _create_chapter(self, number: int, title: Optional[str], content: str) -> ChapterStructure:
        """创建章节结构对象"""
        # 分割段落
        paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
        
        # 计算字数（中文字符）
        word_count = len(re.findall(r'[\u4e00-\u9fff]', content))
        
        # 计算对话数量（引号内的内容）
        dialogue_pattern = r'["""]([^"""]{10,200})["""]'
        dialogues = re.findall(dialogue_pattern, content)
        dialogue_count = len(dialogues)
        
        # 描述比例（非对话内容占比）
        description_ratio = 1.0 - (dialogue_count * 100 / max(word_count, 1))
        
        return ChapterStructure(
            chapter_number=number,
            title=title,
            content=content,
            word_count=word_count,
            paragraphs=paragraphs,
            dialogue_count=dialogue_count,
            description_ratio=max(0.0, min(1.0, description_ratio))
        )


class StyleAnalyzer:
    """写作风格分析器"""
    
    def analyze(self, chapters: List[ChapterStructure]) -> WritingStyle:
        """
        分析写作风格
        
        Args:
            chapters: 章节列表
            
        Returns:
            写作风格特征
        """
        if not chapters:
            return WritingStyle(
                avg_sentence_length=0,
                avg_paragraph_length=0,
                dialogue_ratio=0,
                description_ratio=0,
                punctuation_style={},
                common_phrases=[],
                sentence_openings=[]
            )
        
        # 合并所有内容
        all_content = '\n'.join(ch.content for ch in chapters)
        
        # 分析句子长度
        sentences = re.split(r'[。！？]', all_content)
        sentences = [s.strip() for s in sentences if s.strip()]
        avg_sentence_length = sum(len(s) for s in sentences) / max(len(sentences), 1)
        
        # 分析段落长度
        all_paragraphs = []
        for ch in chapters:
            all_paragraphs.extend(ch.paragraphs)
        avg_paragraph_length = sum(len(p) for p in all_paragraphs) / max(len(all_paragraphs), 1)
        
        # 对话比例
        total_dialogues = sum(ch.dialogue_count for ch in chapters)
        total_words = sum(ch.word_count for ch in chapters)
        dialogue_ratio = total_dialogues * 100 / max(total_words, 1)
        
        # 描述比例
        description_ratio = sum(ch.description_ratio for ch in chapters) / len(chapters)
        
        # 标点符号风格
        punctuation_style = self._analyze_punctuation(all_content)
        
        # 常用短语
        common_phrases = self._extract_common_phrases(all_content)
        
        # 句子开头模式
        sentence_openings = self._extract_sentence_openings(sentences)
        
        return WritingStyle(
            avg_sentence_length=avg_sentence_length,
            avg_paragraph_length=avg_paragraph_length,
            dialogue_ratio=dialogue_ratio,
            description_ratio=description_ratio,
            punctuation_style=punctuation_style,
            common_phrases=common_phrases,
            sentence_openings=sentence_openings
        )
    
    def _analyze_punctuation(self, content: str) -> Dict[str, float]:
        """分析标点符号使用风格"""
        punctuation_counts = defaultdict(int)
        total = 0
        
        for char in content:
            if char in '，。！？；：""""''（）、':
                punctuation_counts[char] += 1
                total += 1
        
        # 归一化
        if total > 0:
            return {k: v / total for k, v in punctuation_counts.items()}
        return {}
    
    def _extract_common_phrases(self, content: str, top_k: int = 20) -> List[str]:
        """提取常用短语"""
        # 提取4字短语
        phrases = defaultdict(int)
        
        for i in range(len(content) - 3):
            phrase = content[i:i+4]
            if re.match(r'^[\u4e00-\u9fff]{4}$', phrase):
                phrases[phrase] += 1
        
        # 返回最常见的
        sorted_phrases = sorted(phrases.items(), key=lambda x: x[1], reverse=True)
        return [p[0] for p in sorted_phrases[:top_k]]
    
    def _extract_sentence_openings(self, sentences: List[str], top_k: int = 10) -> List[str]:
        """提取句子开头模式"""
        openings = defaultdict(int)
        
        for sent in sentences:
            # 取前3个字符
            opening = sent[:3].strip()
            if opening:
                openings[opening] += 1
        
        sorted_openings = sorted(openings.items(), key=lambda x: x[1], reverse=True)
        return [o[0] for o in sorted_openings[:top_k]]


class ImitationLearning:
    """
    模仿学习系统
    
    从参考小说学习写作风格，生成训练数据
    """
    
    def __init__(self, reference_dir: str = "reference"):
        self.reference_dir = Path(reference_dir)
        self.parser = NovelParser()
        self.analyzer = StyleAnalyzer()
        
        # 已加载的参考数据
        self.reference_novels: Dict[str, List[ChapterStructure]] = {}
        self.styles: Dict[str, WritingStyle] = {}
        self.training_samples: List[ImitationSample] = []
        
        logger.info(f"[ImitationLearning] 初始化: reference_dir={reference_dir}")
    
    def load_references(self) -> Dict[str, List[ChapterStructure]]:
        """
        加载所有参考小说
        
        Returns:
            {文件名: 章节列表}
        """
        if not self.reference_dir.exists():
            logger.warning(f"[ImitationLearning] 参考目录不存在: {self.reference_dir}")
            return {}
        
        # 查找所有txt文件
        txt_files = list(self.reference_dir.glob("*.txt"))
        
        logger.info(f"[ImitationLearning] 找到{len(txt_files)}本参考小说")
        
        for file_path in txt_files:
            try:
                chapters = self.parser.parse_file(str(file_path))
                if chapters:
                    self.reference_novels[file_path.name] = chapters
                    logger.info(f"[ImitationLearning] 加载: {file_path.name} - {len(chapters)}章")
            except Exception as e:
                logger.error(f"[ImitationLearning] 加载失败 {file_path.name}: {e}")
        
        return self.reference_novels
    
    def analyze_styles(self) -> Dict[str, WritingStyle]:
        """
        分析所有参考小说的写作风格
        
        Returns:
            {文件名: 写作风格}
        """
        if not self.reference_novels:
            self.load_references()
        
        for filename, chapters in self.reference_novels.items():
            style = self.analyzer.analyze(chapters)
            self.styles[filename] = style
            logger.info(f"[ImitationLearning] 风格分析: {filename}")
        
        return self.styles
    
    def generate_training_samples(
        self,
        num_samples: int = 100,
        context_length: int = 200,
        output_length: int = 1000
    ) -> List[ImitationSample]:
        """
        生成模仿学习训练样本
        
        Args:
            num_samples: 样本数量
            context_length: 上下文长度（字符）
            output_length: 输出长度（字符）
            
        Returns:
            训练样本列表
        """
        if not self.reference_novels:
            self.load_references()
        
        samples = []
        
        for filename, chapters in self.reference_novels.items():
            style = self.styles.get(filename)
            
            for chapter in chapters:
                if len(chapter.content) < context_length + output_length:
                    continue
                
                # 随机位置采样
                max_start = len(chapter.content) - context_length - output_length
                if max_start <= 0:
                    continue
                    
                start_pos = 0  # 可以从0开始或随机
                
                # 提取上下文（前文概要）
                context = chapter.content[:start_pos + context_length].strip()
                if not context:
                    context = f"第{chapter.chapter_number}章"
                
                # 提取输出（正文）
                output = chapter.content[
                    start_pos + context_length:
                    start_pos + context_length + output_length
                ].strip()
                
                # 构建风格提示
                style_prompt = self._build_style_prompt(style)
                
                sample = ImitationSample(
                    context=context,
                    style_prompt=style_prompt,
                    output=output,
                    metadata={
                        "source": filename,
                        "chapter": chapter.chapter_number,
                        "word_count": chapter.word_count,
                    }
                )
                samples.append(sample)
                
                if len(samples) >= num_samples:
                    break
            
            if len(samples) >= num_samples:
                break
        
        self.training_samples = samples
        logger.info(f"[ImitationLearning] 生成{len(samples)}个训练样本")
        
        return samples
    
    def _build_style_prompt(self, style: Optional[WritingStyle]) -> str:
        """构建风格提示词"""
        if style is None:
            return "保持叙事流畅，情节紧凑。"
        
        prompts = []
        
        # 句式风格
        if style.avg_sentence_length > 30:
            prompts.append("使用较长句式，文风细腻")
        elif style.avg_sentence_length < 15:
            prompts.append("使用短句，节奏明快")
        else:
            prompts.append("句式长短结合")
        
        # 对话比例
        if style.dialogue_ratio > 0.4:
            prompts.append("对话较多")
        elif style.dialogue_ratio < 0.2:
            prompts.append("描写为主")
        
        # 段落长度
        if style.avg_paragraph_length > 200:
            prompts.append("段落较长")
        else:
            prompts.append("段落简洁")
        
        # 常用开头
        if style.sentence_openings:
            prompts.append(f"常用开头：{', '.join(style.sentence_openings[:3])}")
        
        return "；".join(prompts)
    
    def export_to_json(self, output_path: str):
        """
        导出训练样本为JSON格式
        
        格式适合用于GRPO/LoRA训练
        """
        if not self.training_samples:
            self.generate_training_samples()
        
        data = []
        for sample in self.training_samples:
            # 构建训练样本格式
            prompt = f"""根据以下上下文和风格要求，续写小说内容：

【上下文】
{sample.context}

【风格要求】
{sample.style_prompt}

请续写："""
            
            data.append({
                "prompt": prompt,
                "completion": sample.output,
                "metadata": sample.metadata
            })
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"[ImitationLearning] 训练数据已导出: {output_path}")
        return output_path
    
    def export_to_jsonl(self, output_path: str):
        """
        导出为JSONL格式（适合llama.cpp训练）
        """
        if not self.training_samples:
            self.generate_training_samples()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for sample in self.training_samples:
                data = {
                    "prompt": f"【上下文】\n{sample.context}\n\n【风格】\n{sample.style_prompt}\n\n续写：",
                    "completion": sample.output
                }
                f.write(json.dumps(data, ensure_ascii=False) + '\n')
        
        logger.info(f"[ImitationLearning] JSONL训练数据已导出: {output_path}")
        return output_path
    
    def get_style_summary(self) -> Dict[str, Any]:
        """获取风格汇总报告"""
        if not self.styles:
            self.analyze_styles()
        
        summary = {
            "total_novels": len(self.styles),
            "total_chapters": sum(len(chs) for chs in self.reference_novels.values()),
            "avg_word_count": 0,
            "styles": {}
        }
        
        total_words = 0
        for filename, style in self.styles.items():
            chapters = self.reference_novels.get(filename, [])
            word_count = sum(ch.word_count for ch in chapters)
            total_words += word_count
            
            summary["styles"][filename] = {
                "chapters": len(chapters),
                "word_count": word_count,
                "avg_sentence_length": round(style.avg_sentence_length, 2),
                "dialogue_ratio": round(style.dialogue_ratio, 3),
                "common_phrases": style.common_phrases[:10],
            }
        
        summary["avg_word_count"] = total_words // max(len(self.styles), 1)
        
        return summary
    
    def get_writing_guidelines(self) -> str:
        """
        生成写作指南
        
        基于参考小说的风格特征，生成写作建议
        """
        if not self.styles:
            self.analyze_styles()
        
        # 计算平均特征
        avg_sentence_length = sum(s.avg_sentence_length for s in self.styles.values()) / max(len(self.styles), 1)
        avg_dialogue_ratio = sum(s.dialogue_ratio for s in self.styles.values()) / max(len(self.styles), 1)
        avg_description_ratio = sum(s.description_ratio for s in self.styles.values()) / max(len(self.styles), 1)
        
        # 收集常用短语
        all_phrases = []
        for style in self.styles.values():
            all_phrases.extend(style.common_phrases)
        phrase_freq = defaultdict(int)
        for p in all_phrases:
            phrase_freq[p] += 1
        common_phrases = [p for p, c in sorted(phrase_freq.items(), key=lambda x: x[1], reverse=True)[:20]]
        
        guidelines = f"""# 模仿学习写作指南

基于{len(self.styles)}本参考小说分析得出：

## 风格特征
- 平均句长: {avg_sentence_length:.1f}字
- 对话比例: {avg_dialogue_ratio:.1%}
- 描写比例: {avg_description_ratio:.1%}

## 写作建议
1. 句式控制：{'使用长句营造细腻氛围' if avg_sentence_length > 25 else '使用短句保持节奏'}
2. 对话平衡：{'增加对话推动情节' if avg_dialogue_ratio > 0.3 else '适当减少对话，增加描写'}
3. 描写风格：保持{'详细描写' if avg_description_ratio > 0.6 else '简洁描写'}

## 常用表达
{chr(10).join(f'- {p}' for p in common_phrases[:10])}

## 参考来源
{chr(10).join(f'- {name}' for name in self.styles.keys())}
"""
        
        return guidelines


def main():
    """测试模仿学习系统"""
    # 初始化
    il = ImitationLearning("reference")
    
    # 加载参考小说
    novels = il.load_references()
    print(f"加载了{len(novels)}本参考小说")
    
    # 分析风格
    styles = il.analyze_styles()
    print(f"分析了{len(styles)}种写作风格")
    
    # 生成训练样本
    samples = il.generate_training_samples(num_samples=50)
    print(f"生成了{len(samples)}个训练样本")
    
    # 导出
    il.export_to_json("training_data/imitation_samples.json")
    il.export_to_jsonl("training_data/imitation_samples.jsonl")
    
    # 打印风格汇总
    summary = il.get_style_summary()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    
    # 打印写作指南
    guidelines = il.get_writing_guidelines()
    print(guidelines)


if __name__ == "__main__":
    main()
