# {{world_name}} 世界设定

## 基本信息

- **世界名称**: {{world_name}}
- **类型**: {{genre_type}}
- **创建时间**: {{created_at}}
- **版本**: {{version}}

## 世界概述

{{overview}}

---

## 力量体系

{% for system in power_systems %}
### {{ system.name }}

{{ system.description }}

**等级划分**: {{ system.levels | join(" → ") }}

{% if system.cultivation_method %}
**修炼方式**: {{ system.cultivation_method }}
{% endif %}

{% if system.rules %}
**核心规则**:
{% for rule in system.rules %}
- {{ rule }}
{% endfor %}
{% endif %}

{% if system.limits %}
**限制条件**:
{% for limit in system.limits %}
- {{ limit }}
{% endfor %}
{% endif %}

{% endfor %}

---

## 社会结构

### 主要势力

{% for faction in social_structure.main_factions %}
#### {{ faction.name }}
- **立场**: {{ faction.align }}
- **描述**: {{ faction.description }}
{% if faction.resources %}
- **掌控资源**: {{ faction.resources | join(", ") }}
{% endif %}

{% endfor %}

### 社会阶层

{{ social_structure.power_distribution }}

---

## 地理环境

{{ geography.map_description }}

{% for region in geography.regions %}
### {{ region.name }}

- **气候**: {{ region.climate }}
- **控制势力**: {{ region.controlled_by }}
- **描述**: {{ region.description }}
{% if region.resources %}
- **特产资源**: {{ region.resources | join(", ") }}
{% endif %}

{% endfor %}

---

## 历史背景

### 世界起源

{{ history.origin }}

### 重大事件

{% for event in history.major_events %}
#### {{ event.event }}
- **时间**: {{ event.time }}
- **描述**: {{ event.description }}
- **影响**: {{ event.impact }}

{% endfor %}

---

## 文化设定

{% if culture.beliefs %}
### 信仰
{% for belief in culture.beliefs %}
- {{ belief }}
{% endfor %}
{% endif %}

{% if culture.customs %}
### 习俗
{% for custom in culture.customs %}
- {{ custom }}
{% endfor %}
{% endif %}

{% if culture.taboos %}
### 禁忌
{% for taboo in culture.taboos %}
- {{ taboo }}
{% endfor %}
{% endif %}

---

## 关键规则

{% for rule in key_rules %}
### {{ rule.rule }}

{{ rule.description }}

**戏剧潜力**: {{ rule.dramatic_potential }}

{% endfor %}

---

## 核心冲突

{% for conflict in conflicts %}
### {{ conflict.type }}: {{ conflict.parties | join(" vs ") }}

**核心问题**: {{ conflict.core_issue }}
**当前状态**: {{ conflict.current_status }}

{% endfor %}

---

## 独特设定

{% for feature in unique_features %}
- {{ feature }}
{% endfor %}

---

## 避免的俗套

{% for cliche in avoid_clichés %}
- {{ cliche }}
{% endfor %}

---

## 更新日志

| 日期 | 版本 | 修改内容 |
|------|------|----------|
| {{created_at}} | v1.0 | 初始版本 |
