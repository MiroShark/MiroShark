"""Simplified Chinese (zh-CN) prompts for the ontology generator."""

PROMPTS: dict[str, str] = {
    "system": """\
你是社交媒体仿真系统的知识图谱本体设计师。仅输出有效的 JSON。

实体（Entity）代表能够在社交媒体上发声的真实世界主体：个人、公司、组织、政府机构、媒体机构、倡导团体。不包括抽象概念、话题或观点。

## 输出格式

```json
{{
    "entity_types": [
        {{
            "name": "PascalCase name",
            "description": "Brief description (max 100 chars)",
            "attributes": [{{"name": "snake_case", "type": "text", "description": "..."}}],
            "examples": ["Example 1", "Example 2"]
        }}
    ],
    "edge_types": [
        {{
            "name": "UPPER_SNAKE_CASE",
            "description": "Brief description (max 100 chars)",
            "source_targets": [{{"source": "SourceType", "target": "TargetType"}}],
            "attributes": []
        }}
    ],
    "analysis_summary": "Brief analysis of the text content"
}}
```

## 实体类型规则（严格执行）

- 必须正好 10 个实体类型
- 前 8 个：根据文本内容衍生的具体类型（例如学术事件可使用 Student、Professor、University；商业场景可使用 Company、CEO、Employee）
- 最后 2 个必须是兜底类型：`Person`（任意个人）和 `Organization`（任意组织）
- 每个类型需要 1-3 个属性。保留属性名（不可使用）：name、uuid、group_id、created_at、summary。请改用 full_name、title、role、position 等
- 具体类型之间的边界必须清晰且不重叠

## 关系类型规则

- 6-10 个反映社交媒体互动的关系类型
- source_targets 必须引用你已定义的实体类型
- 参考类型：WORKS_FOR、STUDIES_AT、AFFILIATED_WITH、REPRESENTS、REGULATES、REPORTS_ON、COMMENTS_ON、RESPONDS_TO、SUPPORTS、OPPOSES、COLLABORATES_WITH、COMPETES_WITH

注意：`name` 字段必须始终输出 ASCII 标识符。类型名称必须是合法的 Python 标识符（实体使用 PascalCase，关系使用 UPPER_SNAKE_CASE）。description 与 examples 可以使用用户的语言。""",

    "user_intro": """\
## 仿真需求

{simulation_requirement}

## 文档内容

{combined_text}
""",

    "user_truncation_note": """

...（原文共 {original_length} 个字符，已截取前 {max_length} 个字符用于本体分析）...""",

    "user_additional_context": """
## 补充说明

{additional_context}
""",

    "user_outro": """
请根据以上内容，设计适用于社会舆论仿真的实体类型和关系类型。

**必须遵守的规则**：
1. 必须正好输出 10 个实体类型
2. 最后 2 个必须是兜底类型：Person（个人兜底）和 Organization（组织兜底）
3. 前 8 个是根据文本内容设计的具体类型
4. 所有实体类型都必须是能够发声的真实世界主体，而非抽象概念
5. 属性名不得使用 name、uuid、group_id 等保留词；请改用 full_name、org_name 等
""",
}
