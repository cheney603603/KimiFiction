# 第{{ chapter_number }}章 {{ title }}

## 基本信息

- **卷号**: 第{{ volume }}卷
- **章节号**: 第{{ chapter_number }}章
- **字数目标**: {{ word_target | default('3000') }}字
- **章节类型**: {{ chapter_type | default('待定') }}
- **创作时间**: {{ created_at }}

---

## 章节摘要

{{ summary | default('待填写') }}

---

## 核心任务

{{ core_task | default('待填写') }}

---

## 情节点

{% for scene in scenes %}
### 场景 {{ loop.index }}: {{ scene.name }}

**地点**: {{ scene.location }}
**时间**: {{ scene.time | default('待定') }}
**出场人物**: {{ scene.characters | join(', ') }}

**内容**:
{{ scene.content | default('待填写') }}

{% if scene.dialogue %}
**关键对话**:
{{ scene.dialogue }}
{% endif %}

{% endfor %}

---

## 章节亮点

{% for highlight in highlights | default([]) %}
- {{ highlight }}
{% endfor %}

---

## 伏笔/钩子

{% if foreshadowing %}
{% for fs in foreshadowing %}
- **{{ fs.id }}**: {{ fs.content }} → 第{{ fs.resolution_chapter }}章
{% endfor %}
{% else %}
暂无伏笔铺设。
{% endif %}

---

## 章节钩子

{{ chapter_hook | default('待设置') }}

---

## 与前后章节的衔接

**承接**: 第{{ prev_chapter }}章 {{ prev_title | default('待定') }}

**引出**: 第{{ next_chapter }}章 {{ next_title | default('待定') }}

---

## 写作注意事项

{% for note in writing_notes | default([]) %}
- {{ note }}
{% endfor %}

---

## 修订记录

| 日期 | 版本 | 修改内容 | 修改原因 |
|------|------|----------|----------|
| {{ created_at }} | v1.0 | 初始版本 | - |
{% for revision in revisions | default([]) %}
| {{ revision.date }} | {{ revision.version }} | {{ revision.content }} | {{ revision.reason }} |
{% endfor %}

---

## 正文草稿

> 以下为AI生成或手工撰写的内容

---

*（正文开始）*


