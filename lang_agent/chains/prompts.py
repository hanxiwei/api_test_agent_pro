from __future__ import annotations

from ..parser import Endpoint
from ..scenario_builder import Scenario


def generation_prompt(base_url: str, scenario: Scenario) -> str:
    endpoints_desc = "\n".join(
        f"- {ep.method.upper()} {ep.path} operationId={ep.operation_id}"
        for ep in scenario.endpoints
    )
    return f"""你是一个资深 SDET。请基于下面的 API 场景生成一份可运行的 pytest 测试文件。

要求：
1) 只输出 Python 代码，不要输出解释文字
2) 使用 requests 访问 API，base_url = {base_url!r}
3) 每个步骤至少断言 status_code（成功时应 < 500）
4) 对 path 参数用合理的占位值（字符串/数字均可）
5) 代码中不要包含任何敏感信息

场景名：{scenario.name}
资源：{scenario.resource}
涉及接口：
{endpoints_desc}
"""


def diagnosis_prompt(error_log: str) -> str:
    return f"""你是一个测试自动化修复助手。请对以下 pytest 失败日志进行分类，并输出 JSON（不要用 markdown 包裹）。

字段：
- error_category: code_bug | api_bug | env_bug
- error_type: 简短的错误类型（例如 AssertionError / ConnectionError）
- error_signature: 稳定签名（用于缓存与检索，尽量去掉行号与随机值）
- error_summary: 1~2 句中文摘要

失败日志：
{error_log}
"""


def repair_prompt(
    original_code: str,
    error_log: str,
    error_type: str,
    error_summary: str,
    few_shot_examples: list[str],
) -> str:
    examples = "\n\n".join(few_shot_examples)
    return f"""你是一个资深 Python 测试工程师。下面有一份 pytest 测试代码在执行时失败了，请你修复代码。

修复规则：
1) 只修复测试代码，不要修改生产代码
2) 输出必须是“修复后的完整文件内容”，只输出 Python 代码
3) 不要省略任何原有的必要代码
4) 不要输出解释、不要输出 markdown

错误类型：{error_type}
错误摘要：{error_summary}

可参考的历史修复示例（可能为空）：
{examples}

失败日志：
{error_log}

原始代码：
{original_code}
"""

