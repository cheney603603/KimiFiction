# {{ title }} 分卷大纲

## 基本信息

- **卷号**: 第{{ volume_number }}卷
- **卷名**: {{ title }}
- **章节数**: {{ target_chapters | default('待定') }}
- **主题**: {{ theme | default('待定') }}

---

## 卷概述

{{ summary | default('待填写') }}

---

## 整体故事弧线

{{ overall_arc | default('待填写') }}

---

## 章节概要

### Act 1 (第{{ act_1.start }}-{{ act_1.end }}章)

**目标**: {{ act_1.purpose | default('待定') }}

| 章号 | 章节名 | 核心剧情 | 字数预估 |
|------|--------|----------|----------|
{% for chapter in act_1.chapters | default([]) %}
| 第{{ chapter.number }}章 | {{ chapter.title }} | {{ chapter.summary }} | {{ chapter.word_target | default('3000') }}字 |
{% endfor %}

### Act 2 (第{{ act_2.start }}-{{ act_2.end }}章)

**目标**: {{ act_2.purpose | default('待定') }}

| 章号 | 章节名 | 核心剧情 | 字数预估 |
|------|--------|----------|----------|
{% for chapter in act_2.chapters | default([]) %}
| 第{{ chapter.number }}章 | {{ chapter.title }} | {{ chapter.summary }} | {{ chapter.word_target | default('3000') }}字 |
{% endfor %}

### Act 3 (第{{ act_3.start }}-{{ act_3.end }}章)

**目标**: {{ act_3.purpose | default('待定') }}

| 章号 | 章节名 | 核心剧情 | 字数预估 |
|------|--------|----------|----------|
{% for chapter in act_3.chapters | default([]) %}
| 第{{ chapter.number }}章 | {{ chapter.title }} | {{ chapter.summary }} | {{ chapter.word_target | default('3000') }}字 |
{% endfor %}

---

## 剧情弧

{% for arc in arcs %}
### {{ arc.arc_id }}: {{ arc.title }}

**章节范围**: 第{{ arc.start_chapter }}-{{ arc.end_chapter }}章

**描述**: {{ arc.description }}

**冲突**: {{ arc.conflict }}

**解决**: {{ arc.resolution }}

{% if arc.key_events %}
**关键事件**:
{% for event in arc.key_events %}
- {{ event }}
{% endfor %}
{% endif %}

{% if arc.cliffhanger %}
**悬念设置**: {{ arc.cliffhanger }}
{% endif %}

---

{% endfor %}

---

## 卷高潮

{{ climax | default('待设计') }}

---

## 卷末悬念

{{ cliffhanger | default('待设置') }}

---

## 伏笔铺设

{% for fs in foreshadowing | default([]) %}
- **第{{ fs.chapter }}章**: {{ fs.title }} → 预计第{{ fs.resolution_chapter }}章回收
{% endfor %}

---

## 角色发展

{% for char_arc in character_arcs | default([]) %}
### {{ char_arc.character }}

**起始状态**: {{ char_arc.starting_state }}
**关键冲突**: {{ char_arc.key_conflicts | join(', ') }}
**转变点**: 第{{ char_arc.transformation_point }}章
**最终状态**: {{ char_arc.ending_state }}

{% endfor %}

---

## 节奏设计

- **开篇节奏**: {{ pacing.opening | default('待定') }}
- **中期节奏**: {{ pacing.development | default('待定') }}
- **高潮节奏**: {{ pacing.climax | default('待定') }}

---

## 创作笔记

> 此处记录创作过程中的修改、调整等。

---

**最后更新**: {{ last_modified }}
