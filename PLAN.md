# API Test Agent LangChain 版开发计划

## 1. 项目定位

本项目是当前 `api_test_agent` 的升级版/重构版，目标是在保留原有业务价值的前提下，引入 `LangChain` 和 `LangGraph`，从 0 开始实现一个更标准的 API 测试自愈 Agent。

核心目标不变：

- 基于 `OpenAPI/Swagger` 自动生成 `pytest` 用例
- 执行失败后，自动抓取错误上下文并调用大模型修复代码
- 通过双层记忆提升修复速度和成功率
- 提供 `CLI`、`Streamlit` 看板和 `Skill` 集成入口

与旧项目的主要区别：

- 使用 `LangChain` 统一封装模型、Prompt、输出解析、检索器和记忆接口
- 使用 `LangGraph` 重构主流程，实现更清晰的状态流转和修复循环
- 从架构上更接近一个标准的工作流式 Agent，而不是手写流程脚本

---

## 2. 一句话描述

基于 `LangChain + LangGraph + RAG` 的 API 测试自愈 Agent：输入 `OpenAPI/Swagger` 文档后，自动生成 `pytest` 用例；若执行失败，则结合短期记忆与 `ChromaDB` 长期记忆自动修复并重新验证，最终输出通过验证的测试代码与修复报告。

---

## 3. 业务目标

### 3.1 核心目标

- 自动解析 API 文档并生成测试代码
- 支持按资源构建多步骤 `CRUD` 场景测试
- 支持失败检测、错误上下文提取和自动修复
- 支持最多 3 轮修复循环
- 仅将 `pytest` 验证通过的修复结果写入长期记忆库

### 3.2 工程目标

- 用 `LangChain` 管理 LLM 调用和 Prompt
- 用 `LangGraph` 编排完整执行流
- 用 `ChromaDB` + `Retriever` 实现长期记忆
- 提供 `Click` 命令行
- 提供 `Streamlit` 前端
- 预留 `Claude Code Skill` 集成能力

### 3.3 非目标

- 不做多 Agent 协作系统
- 不做通用代码修复平台
- 不做复杂权限系统或在线部署平台
- 不优先处理非 HTTP API（如 gRPC、GraphQL）

---

## 4. 技术方案

### 4.1 技术栈

- 语言：`Python 3.10+`
- LLM：`langchain-openai`
- Agent/Workflow：`langgraph`
- Prompt/Chain：`langchain`
- 向量库：`ChromaDB`
- 文档解析：`prance`
- 测试执行：`pytest` + `pytest-json-report`
- 命令行：`click`
- Web UI：`streamlit`
- 配置：`python-dotenv` + `yaml`
- 稳定性：`tenacity`

### 4.2 新增依赖建议

```bash
pip install langchain langgraph langchain-openai langchain-community chromadb prance pytest pytest-json-report click streamlit tenacity python-dotenv pyyaml requests
```

---

## 5. 总体架构

```text
用户输入 OpenAPI 文档
        |
        v
LangGraph 主流程
        |
        +--> 文档解析节点
        +--> 场景构建节点
        +--> 代码生成节点
        +--> 测试执行节点
        +--> 失败分析节点
        +--> 短期记忆命中判断
        +--> 长期记忆检索
        +--> 修复代码生成节点
        +--> 回写测试文件节点
        +--> 重新执行节点
        +--> 成功写入长期记忆节点
        +--> 最终报告节点
```

可概括为：

`解析 -> 生成 -> 执行 -> 捕获失败 -> 短期记忆 -> 长期记忆 -> 修复 -> 重试 -> 记录`

---

## 6. LangChain / LangGraph 在本项目中的角色

### 6.1 LangChain 负责什么

- 封装模型客户端
- 管理 PromptTemplate
- 管理输出解析
- 封装向量检索器 Retriever
- 将长期记忆作为检索增强上下文注入修复链

### 6.2 LangGraph 负责什么

- 管理全局 State
- 控制节点间状态流转
- 处理“测试通过 / 测试失败”分支
- 处理“短期记忆命中 / 未命中”分支
- 处理“修复成功 / 修复失败 / 达到最大轮次”分支
- 显式表达最多 3 轮修复循环

---

## 7. 记忆系统设计

本项目仍采用双层记忆，但会结合 `LangChain` 的抽象能力来实现。

### 7.1 短期记忆

短期记忆建议使用两层方案：

- `LangGraph State`：保存当前运行过程中的关键上下文，例如当前轮次、当前失败文件、最近一次修复结果
- `session_cache` 字典：以 `test_file_name::error_signature` 为 key，保存本次会话内已经验证成功的修复代码

说明：

- `LangChain` 确实有短期记忆相关概念，但更适合对话历史
- 这个项目的“短期记忆”更像“会话级错误修复缓存”
- 因此最稳妥的做法是：**状态流用 LangGraph，错误缓存用本地字典**
- 缓存 key 需要包含文件名，避免不同测试文件出现相同 `error_signature` 时发生错误复用

建议 key 形式：

```python
cache_key = f"{test_file_name}::{error_signature}"
```

### 7.2 长期记忆

长期记忆使用：

- `ChromaDB` 存历史成功修复案例
- `LangChain VectorStore / Retriever` 负责检索

说明：

- 本项目**不使用 `LangGraph Store` 作为长期记忆方案**
- `Store` 更适合键值级精确查找，不适合“根据错误日志做语义相似度检索”
- 因此长期记忆统一采用 `ChromaDB + LangChain Retriever`

长期记忆中每条记录建议包括：

- `error_log`
- `error_signature`
- `error_type`
- `original_code_summary`
- `fixed_code`
- `test_file_name`
- `repair_round`
- `validated=true`

其中：

- `error_type` 用于检索前的元数据预过滤，例如 `KeyError`、`AssertionError`、`ConnectionError`
- `error_log` 用于在同类错误内部继续做语义相似度排序
- `fixed_code` 仅保存最终通过 `pytest` 验证的版本

检索策略建议：

1. 先按 `error_type` 做元数据过滤
2. 再在过滤后的候选集内做向量相似度检索
3. 最终只返回 `top_k=2~3` 条作为 Few-shot 示例

### 7.3 为什么这样设计

- 短期记忆强调“快”和“精确命中”
- 长期记忆强调“相似检索”和“跨会话复用”
- 只有通过 `pytest` 验证的修复结果才允许写入长期记忆
- 先按 `error_type` 过滤再做语义检索，可以显著降低 Few-shot 污染风险

---

## 8. 主流程设计

### 8.1 generate 模式

只做代码生成，不做修复：

```text
输入 OpenAPI -> 解析 -> 分组构建 CRUD 场景 -> 调用 LLM 生成 pytest -> 保存到 generated_tests/
```

### 8.2 heal 模式

完整自愈流程：

```text
输入 OpenAPI
  -> 解析
  -> 生成 pytest
  -> 执行 pytest
  -> 是否失败？
      -> 否：输出成功报告
      -> 是：根因分类
          -> api_bug：停止自动修复，生成 Bug 报告并转人工
          -> env_bug：停止自动修复，生成环境异常报告并转人工
          -> code_bug：选择当前失败文件 -> 提取错误签名 + error_type
              -> 查询短期记忆
                  -> 命中：直接复用修复代码
                  -> 未命中：查询长期记忆
                      -> 先按 error_type 过滤
                      -> 再检索相似修复案例
                      -> 组装 Few-shot Prompt
              -> 调用 LLM 生成修复代码
              -> 仅回写 current_file
              -> 全量重新执行 pytest
              -> 是否通过？
                  -> 是：写入短期记忆 + 长期记忆
                  -> 否：进入下一轮，最多 3 轮
                      -> 第 3 轮仍失败：输出人工介入报告
```

修复范围约束：

- 每一轮修复只处理一个失败文件，即 `current_file`
- 修复后不是只跑单文件，而是**全量重新执行所有测试文件**
- 这样既能验证当前修复是否生效，也能检查是否引入了对其他测试文件的回归影响

---

## 9. 模块划分

建议新项目目录结构如下：

```text
api_test_agent_langchain/
├── PLAN.md
├── requirements.txt
├── .env.example
├── config.yaml
├── app.py
├── cli.py
├── skill/
│   └── SKILL.md
├── data/
│   └── petstore.yaml
├── lang_agent/
│   ├── __init__.py
│   ├── config.py
│   ├── parser.py
│   ├── scenario_builder.py
│   ├── executor.py
│   ├── signatures.py
│   ├── report.py
│   ├── memory/
│   │   ├── short_memory.py
│   │   ├── long_memory.py
│   │   └── retriever.py
│   ├── chains/
│   │   ├── llm_factory.py
│   │   ├── prompts.py
│   │   ├── generation_chain.py
│   │   ├── diagnosis_chain.py
│   │   └── repair_chain.py
│   └── graph/
│       ├── state.py
│       ├── nodes.py
│       ├── router.py
│       └── runner.py
└── generated_tests/
```

---

## 10. 关键模块职责

### `parser.py`

- 解析 `OpenAPI/Swagger`
- 输出统一的 endpoint 结构

### `scenario_builder.py`

- 按资源分组
- 推断 `CRUD` 链
- 构造测试场景描述

### `chains/generation_chain.py`

- 调用 `LangChain` LLM 生成 `pytest` 测试代码

### `executor.py`

- 执行 `pytest`
- 解析 `json report`
- 抽取失败文件与错误日志
- 修复后执行全量回归，验证是否引入新的失败文件

### `signatures.py`

- 从错误日志生成错误签名
- 提取 `error_type`
- 生成用于短期记忆匹配的签名摘要

### `memory/short_memory.py`

- 管理会话级缓存
- 对同类错误直接复用修复结果
- 缓存 key 使用 `test_file_name::error_signature`

### `memory/long_memory.py`

- 用 `ChromaDB` 存储历史成功修复
- 提供新增与查询接口
- 查询时先按 `error_type` 做元数据过滤，再做向量相似度排序

### `chains/diagnosis_chain.py`

- 只负责失败根因分类
- 输出结构化结果：`error_category`、`error_signature`、`error_type`、`error_summary`
- `error_category` 支持 `code_bug`、`api_bug`、`env_bug`

### `chains/repair_chain.py`

- 只负责修复，不负责分类
- 拼接错误日志、原始代码、错误类型、Few-shot 历史修复案例
- 生成修复后的完整测试代码

### `graph/runner.py`

- 负责构建和执行 `LangGraph`

---

## 11. LangGraph 状态设计

建议主状态字段如下：

```python
{
    "mode": "generate" | "heal",
    "openapi_path": str,
    "endpoints": list,
    "generated_files": list,
    "failed_tests": dict,
    "current_file": str,
    "current_error_log": str,
    "error_category": "code_bug" | "api_bug" | "env_bug" | None,
    "error_signature": str,
    "error_type": str,
    "error_summary": str,
    "repair_round": int,
    "max_rounds": int,
    "short_memory_hit": bool,
    "retrieved_examples": list,
    "proposed_fix_code": str,
    "api_bug_report": dict | None,
    "repair_history": list,
    "final_result": dict,
}
```

---

## 12. LangGraph 节点规划

建议节点如下：

1. `parse_openapi_node`
2. `build_scenarios_node`
3. `generate_tests_node`
4. `run_tests_node`
5. `collect_failures_node`
6. `pick_failure_node`
7. `classify_failure_node`
8. `build_signature_node`
9. `lookup_short_memory_node`
10. `retrieve_long_memory_node`
11. `repair_code_node`
12. `apply_fix_node`
13. `retest_node`
14. `persist_memory_node`
15. `build_handoff_report_node`
16. `final_report_node`

节点职责约束：

- `classify_failure_node`：只做根因分类，不生成代码
- `pick_failure_node`：从失败列表中选出当前轮次要修复的 `current_file`
- `build_signature_node`：只提取 `error_signature`、`error_type` 和错误摘要
- `repair_code_node`：只根据输入上下文生成新代码，不承担分类职责
- `build_handoff_report_node`：在第 3 轮仍失败或识别为 `api_bug` / `env_bug` 时，产出人工介入报告

---

## 13. Prompt 设计

至少准备 4 类 Prompt：

### 13.1 测试生成 Prompt

- 输入：接口信息、资源名、方法链、请求体字段、响应字段
- 输出：完整 `pytest` 测试代码

### 13.2 异步轮询 Prompt

- 输入：异步提交接口、轮询接口、超时、状态字段
- 输出：轮询型 `pytest` 用例

### 13.3 失败诊断 Prompt

- 输入：原始代码 + 错误日志
- 输出：结构化 JSON
- 字段：
  - `error_category`: `code_bug` | `api_bug` | `env_bug`
  - `error_signature`: 短期记忆使用的精确匹配键
  - `error_type`: 例如 `KeyError`、`AssertionError`、`ConnectionError`
  - `error_summary`: 精简版错误描述

建议使用 `with_structured_output` 强制模型返回结构化结果。

### 13.4 修复 Prompt

- 输入：
  - 原始代码
  - 当前错误日志
  - `error_type`
  - `error_summary`
  - Few-shot 历史修复案例
- 输出：修复后的完整 Python 代码

修复节点标准入参建议为：

```python
(original_code, error_log, error_type, error_summary, few_shot_examples)
```

---

## 14. 从 0 开始的开发阶段

### 阶段 1：项目初始化

目标：

- 创建独立目录
- 初始化依赖、配置、环境变量样例
- 准备示例 `OpenAPI` 文档

产出：

- `requirements.txt`
- `.env.example`
- `config.yaml`
- 基础目录结构

### 阶段 2：OpenAPI 解析与测试生成

目标：

- 解析 `OpenAPI`
- 按资源构建 `CRUD` 链
- 通过 `LangChain` 生成基础 `pytest` 用例

产出：

- `parser.py`
- `scenario_builder.py`
- `generation_chain.py`

### 阶段 3：pytest 执行与失败捕获

目标：

- 封装执行器
- 抓取错误堆栈、失败片段和报告

产出：

- `executor.py`
- `report.py`

### 阶段 4：修复链（不带记忆）

目标：

- 在不接记忆的前提下，先打通“失败分类 -> LLM 修复 -> 回写 -> 回归验证”
- 验证修复 Prompt 和代码回写逻辑本身有效
- 完成 `code_bug` / `api_bug` / `env_bug` 分类分流

产出：

- `diagnosis_chain.py`
- `repair_chain.py`

### 阶段 5：双层记忆

目标：

- 实现短期记忆缓存
- 实现 `ChromaDB` 长期记忆
- 接入 `Retriever`
- 将 Few-shot 检索结果接入修复链

产出：

- `short_memory.py`
- `long_memory.py`
- `retriever.py`

### 阶段 6：LangGraph 主流程

目标：

- 将 `generate` 和 `heal` 两种模式接入 `LangGraph`
- 实现最多 3 轮修复循环

产出：

- `state.py`
- `nodes.py`
- `router.py`
- `runner.py`

### 阶段 7：入口层

目标：

- 提供 `Click` 命令行
- 提供 `Streamlit` 页面
- 提供 `Skill` 定义

产出：

- `cli.py`
- `app.py`
- `skill/SKILL.md`

### 阶段 8：回归测试与指标验证

目标：

- 验证生成成功率
- 验证修复成功率
- 验证记忆命中效果

建议指标：

- 首次生成可执行率
- 首次执行通过率
- 3 轮内修复成功率
- 短期记忆命中率
- 长期记忆检索有效率
- `api_bug` 识别准确率
- `env_bug` 识别准确率
- 人工介入报告可用率

---

## 15. 命令行设计

### `generate`

```bash
python cli.py generate -i data/petstore.yaml
```

仅生成测试代码。

### `heal`

```bash
python cli.py heal -i data/petstore.yaml -r 3
```

生成 + 执行 + 修复。

### `report`

```bash
python cli.py report
```

展示最近一次执行结果、修复轮次和记忆命中情况。

---

## 16. 前端页面设计

`Streamlit` 页面建议包含：

- OpenAPI 文件上传
- 最大修复轮次设置
- 模型名称选择
- 是否启用长期记忆开关
- 实时日志区域
- 最终测试结果区域
- 修复记录展示区域

---

## 17. Skill 集成设计

建议提供两个 Skill：

- `/api-test-generate`
- `/api-test-heal`

本质上分别映射到：

- `python cli.py generate -i <openapi_file>`
- `python cli.py heal -i <openapi_file> -r 3`

---

## 18. 风险与注意事项

### 风险 1：LangChain 抽象过重

应对：

- 保持业务逻辑独立
- 不要把所有简单逻辑都强塞进 Chain

### 风险 2：短期记忆误用 LangChain 会话记忆

应对：

- 明确区分“对话历史记忆”和“错误修复缓存”
- 本项目短期记忆以错误签名缓存为主

### 风险 3：长期记忆污染

应对：

- 严格执行“未通过 pytest 不写入长期记忆”
- 检索前先按 `error_type` 过滤，避免无关案例污染 Few-shot

### 风险 4：Graph 过早复杂化

应对：

- 第一版只做单 Agent、单主流程
- 不做多 Agent 协作

### 风险 5：把 API Bug 错修成代码 Bug，造成虚假通过

应对：

- 在修复链前强制增加 `classify_failure_node`
- 仅 `code_bug` 允许进入修复链
- `api_bug` 直接输出缺陷报告并转人工

### 风险 6：环境问题被误送入修复链，浪费修复轮次

应对：

- 将 `error_category` 扩展为 `code_bug` / `api_bug` / `env_bug`
- `env_bug` 与 `api_bug` 一样，禁止进入自动修复链

---

## 19. 验收标准

项目第一阶段完成后，至少应满足：

- 能解析标准 `OpenAPI/Swagger`
- 能生成至少 3 个完整 `CRUD` 测试文件
- 能自动执行 `pytest`
- 失败后能抓取错误日志并触发修复链
- 能实现短期记忆命中直接复用
- 能实现长期记忆检索增强修复
- 最多修复 3 轮
- 能区分 `code_bug`、`api_bug` 和 `env_bug`
- `api_bug` 与 `env_bug` 不允许进入自动修复链
- 只有验证通过的修复结果写入长期记忆
- 第 3 轮失败后能自动输出人工介入报告
- 每轮只修一个失败文件，但修复后会触发全量回归验证
- CLI、前端、Skill 三种入口可用

---

## 20. 最终目标

最终交付的不是简单的“AI 写测试代码脚本”，而是一个：

- 基于 `LangChain` 的 LLM/RAG 能力层
- 基于 `LangGraph` 的流程控制层
- 基于 `pytest` 的执行验证层
- 基于 `ChromaDB` 的长期经验沉淀层
- 面向 API 自动化测试场景的自愈 Agent 工具

---

## 21. 下一步建议

按以下顺序启动新项目最稳妥：

1. 建目录和依赖
2. 先做 `generate`，打通解析 -> 生成 -> 保存
3. 再做 `heal`，先打通执行 -> 失败分类 -> 人工报告
4. 再补不带记忆的 `code_bug` 修复链
5. 再接双层记忆
6. 最后接 `LangGraph` 和前端入口

这样可以避免一上来把 `LangChain`、`LangGraph`、`RAG`、前端、CLI 一次性全部压到一起，导致调试困难。
