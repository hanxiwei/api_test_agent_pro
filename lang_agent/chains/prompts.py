from __future__ import annotations

from ..scenario_builder import Scenario


def generation_prompt(
    base_url: str,
    scenario: Scenario,
    resource_key: str,
    api_module: str,
    api_functions: list[str],
    data_file: str,
) -> str:
    endpoints_desc = "\n".join(
        f"- {ep.method.upper()} {ep.path} operationId={ep.operation_id}"
        for ep in scenario.endpoints
    )
    imports = "\n".join(f"from {api_module} import {name}" for name in api_functions)
    return f"""你是一名资深 SDET。请基于下面的 API 场景生成一份可直接运行的 pytest 测试文件。
要求：
1. 只输出 Python 代码，不要输出解释文字。
2. 这是一个分层的 pytest + requests 接口自动化项目，测试文件位于 `testcases/`。
3. 测试文件里不要直接写 requests 请求，请复用 `api/` 层函数。
4. 可以直接使用 fixture：`base_url`、`request_session`。
5. 可直接使用这些导入：
{imports}
from utils.assertions import assert_response_ok, response_json
from utils.data_loader import load_resource_data
6. 测试数据位于 `{data_file}`，通过 `load_resource_data("{resource_key}")` 读取。
7. 每个步骤至少断言 status_code，且不要包含敏感信息。
8. 输出必须是完整测试文件内容，不要输出 markdown。

场景名：{scenario.name}
资源：{scenario.resource}
base_url 参考值：{base_url!r}
涉及接口：
{endpoints_desc}
"""


def diagnosis_prompt(error_log: str) -> str:
    return f"""你是一个测试自动化修复助手。请对下面的 pytest 失败日志进行分类，并输出 JSON，不要使用 markdown 包裹。
字段：
- error_category: code_bug | api_bug | env_bug
- error_type: 简短错误类型，例如 AssertionError / ConnectionError
- error_signature: 稳定签名，用于缓存与检索，尽量去掉行号与随机值
- error_summary: 1 到 2 句中文摘要
- confidence: 0 到 1 之间的浮点数，表示分类置信度
- reasons: 字符串数组，列出 2~4 条分类依据或关键观察
- actionable_hint: 一句话可操作提示（例如“请先启动本地 mock_api_server.py”或“请检查测试中的断言”）

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
    return f"""你是一名资深 Python 测试工程师。下面有一份 pytest 测试代码执行失败了，请修复这份测试代码。
修复规则：
1. 只修复测试代码，不要修改生产代码。
2. 输出必须是修复后的完整文件内容，只输出 Python 代码。
3. 不要省略原文件中必要的导入和辅助函数。
4. 不要输出解释文字，不要输出 markdown。

错误类型：{error_type}
错误摘要：{error_summary}

可参考的历史修复示例（可能为空）：
{examples}

失败日志：
{error_log}

原始代码：
{original_code}
"""
