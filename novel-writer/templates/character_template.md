# 角色设定卡

## 角色总览

| 序号 | 姓名 | 角色定位 | 性格关键词 | 状态 |
|------|------|----------|------------|------|
{% for char in characters %}
| {{ loop.index }} | {{ char.name }} | {{ char.role_type }} | {{ char.profile.personality[:20] if char.profile.personality else '-' }} | {{ char.status or '待出场' }} |
{% endfor %}

---

{% for char in characters %}
# {{ char.name }}

{% if char.profile %}
## 基本信息

- **性别**: {{ char.profile.gender | default('未知') }}
- **年龄**: {{ char.profile.age | default('未知') }}
- **外貌**: {{ char.profile.appearance | default('未描述') }}

## 性格特点

- **MBTI**: {{ char.profile.mbti | default('未知') }}
- **性格描述**: {{ char.profile.personality | default('未描述') }}
{% if char.profile.fears %}
- **内心恐惧**: {{ char.profile.fears | join(', ') }}
{% endif %}

## 背景故事

{{ char.profile.background | default('未填写') }}

## 目标与动机

{% if char.profile.goals %}
**目标**:
{% for goal in char.profile.goals %}
- {{ goal }}
{% endfor %}
{% endif %}

## 能力设定

{% if char.profile.skills %}
**技能/特长**:
{% for skill in char.profile.skills %}
- {{ skill }}
{% endfor %}
{% endif %}

{% if char.arc_description %}
## 成长弧线

{{ char.arc_description }}
{% endif %}

{% if char.profile.relationships %}
## 人际关系

{% for other, relation in char.profile.relationships.items() %}
- **{{ other }}**: {{ relation }}
{% endfor %}
{% endif %}

---

{% if char.current_status %}
## 当前状态

{{ char.current_status }}
{% endif %}

{% if char.arc_progress %}
## 成长进度

{{ char.arc_progress }}
{% endif %}

{% else %}
## 基本信息

- **角色定位**: {{ char.role_type }}
- **状态**: {{ char.status or '待出场' }}
{% endif %}

{% endfor %}

---

## 角色关系图

```
{{ relationship_summary | default('待生成') }}
```

---

## 创作笔记

> 此处记录创作过程中的灵感、修改记录等。
