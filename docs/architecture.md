# API Test Agent Pro · 架构说明

本文档给出 API Test Agent Pro 的分层架构、核心数据流、自愈状态机与关键熔断策略，便于面试口头讲"为什么这么拆"以及二次开发时快速定位模块。

## 1. 分层架构（自顶向下）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 入口层 Entrypoints                                                            │
│   cli.py              Click CLI (generate / heal / report)                   │
│   app.py              Streamlit 控制台（一键流水线 / 仅生成 / 仅自愈）         │
│   .claude/skills/     Claude Code Skill（自然语言驱动）                       │
├─────────────────────────────────────────────────────────────────────────────┤
│ Agent Harness（业务内核，LangGraph 状态机）                                    │
│   lang_agent/graph/   runner / nodes / router / state                        │
│   lang_agent/chains/  generation_chain / diagnosis_chain / repair_chain      │
│   lang_agent/chains/  scenario_builder（Endpoint → 业务场景）                │
│   lang_agent/memory/  short_memory / long_memory / retriever                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ 横切能力层 Capabilities（与业务解耦，可替换）                                   │
│   lang_agent/io/      parser / executor / report                             │
│   lang_agent/io/sandbox/  docker_runner / policy（后续升级安全执行层）        │
│   lang_agent/llm/     factory / prompts（ChatLLM / Embeddings 实例化 + Prompt）│
│   lang_agent/core/    config / signatures / utils（原子写 + 异常家族）        │
├─────────────────────────────────────────────────────────────────────────────┤
│ 产物 / 配置 / 数据 Artifacts（与代码分离，可 gitignore）                        │
│   configs/            default.yaml / long_memory.yaml                        │
│   data/               petstore.yaml / todo_demo.yaml                         │
│   output/generated/   分层 pytest 工程（api/testcases/utils/data/config/...） │
│   output/reports/     RunReport / handoff_report / json-report               │
│   output/diffs/       每轮修复 old/new patch（可追溯）                         │
│   .cache/             short_memory.json / pytest_*.json                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

- **为什么这么拆**：入口、业务内核、横切能力、产物彼此独立，新增"换执行器为 Docker 沙箱""换报告为 CTRF"、"换模型供应商"都只碰一层。
- **面试话术**：业务内核（graph/chains/memory）稳定；横切能力（io/llm/core）可替换；Artifacts 永不进仓库。

---

## 2. 关键模块职责速查

| 模块 | 文件 | 职责一句话 |
| --- | --- | --- |
| 状态机驱动 | [runner.py](../lang_agent/graph/runner.py) | 编译 Generate / Heal 两个 StateGraph；业务异常下统一写 handoff_report |
| 节点实现 | [nodes.py](../lang_agent/graph/nodes.py) | 解析、场景、生成、执行、分类、记忆、修复、回写、汇报等 16 个节点 |
| 路由决策 | [router.py](../lang_agent/graph/router.py) | 四类路由；`code_bug` 置信度 `< 0.7 → handoff` |
| 状态字段 | [state.py](../lang_agent/graph/state.py) | AgentState TypedDict：含 diagnosis_* 三字段 |
| 生成链 | [generation_chain.py](../lang_agent/chains/generation_chain.py) | scenarios → 分层 pytest 工程；LLM 不可用时落回模板 |
| 诊断链 | [diagnosis_chain.py](../lang_agent/chains/diagnosis_chain.py) | 三类分类 + confidence/reasons/actionable_hint + 启发式兜底 |
| 修复链 | [repair_chain.py](../lang_agent/chains/repair_chain.py) | 修复 + AST 门控（断言削弱、缺 test_、语法错） |
| 场景构建 | [scenario_builder.py](../lang_agent/chains/scenario_builder.py) | Endpoints 按资源分组 → CRUD 链 + 单接口场景 |
| 短期记忆 | [short_memory.py](../lang_agent/memory/short_memory.py) | `current_file::error_signature → fix_code` KV |
| 长期记忆 | [long_memory.py](../lang_agent/memory/long_memory.py) | ChromaDB validated-only 写入 + signature 重排 |
| 检索封装 | [retriever.py](../lang_agent/memory/retriever.py) | few-shot 统一入口 |
| 解析 | [parser.py](../lang_agent/io/parser.py) | OpenAPI → list[Endpoint]，兼容无 Prance 的纯 YAML |
| 执行 | [executor.py](../lang_agent/io/executor.py) | 宿主机子进程 pytest + 结构化失败；非 0/1 退出抛 TestRunnerError |
| 报告 | [report.py](../lang_agent/io/report.py) | RunReport / HealReport / RepairHistoryEntry 的 load/save |
| 模型工厂 | [factory.py](../lang_agent/llm/factory.py) | ChatLLM / Embeddings 构建，DeepSeek Embedding 自动降级 |
| 提示词 | [prompts.py](../lang_agent/llm/prompts.py) | generation / diagnosis / repair 三条 Prompt |
| 配置加载 | [config.py](../lang_agent/core/config.py) | yaml + env + CLI overrides 合并 → Settings |
| 错误签名 | [signatures.py](../lang_agent/core/signatures.py) | 行号、地址归一化；尾部 300 字做签名 |
| 通用工具 | [utils.py](../lang_agent/core/utils.py) | 原子写 + BaseSelfHealingError 五种子类 |

---

## 3. 数据流（Generate 流水线）

```
OpenAPI 输入 YAML
    │
    ▼
io.parser.parse_openapi → list[Endpoint]
    │
    ▼
chains.scenario_builder.build_scenarios → list[Scenario]
    │
    ▼
chains.generation_chain.generate_pytest_project
    │   1) scaffold 分层目录
    │   2) 写 api/ 层函数与 utils/ 辅助
    │   3) 写 data/ 种子 YAML
    │   4) LLM 生成 test_*.py；失败回退模板
    ▼
output/generated/ 分层 pytest 工程
    │
    ▼
graph.nodes.final_report_node → io.report.save_run_report → output/reports/*
```

- **关键不变量**：Generate 流程不跑 pytest，只保证"工程结构合法 + 可执行"，真正执行留到 Heal。
- **失败通道**：parser/generation 任一步抛 `BaseSelfHealingError` → runner._build_handoff_from_exception → handoff_report 落盘。

---

## 4. 数据流（Heal 状态机 + 熔断）

```
[START]
   │
   ▼
run_tests_node ──io.executor.run_pytest──▶ pytest json-report
   │
   ├─route_after_test_run── passed  ─────────────────────▶ final_report_node ──▶ [END]
   │                       errored ─────────────────────▶ final_report_node ──▶ [END]
   │
   ▼ failed
collect_failures_node → pick_failure_node → classify_failure_node
                                                │
                                                │ diagnosis = code_bug/api_bug/env_bug + confidence
                                                │
       ┌──────────────────────route_after_classification──────────────────────┐
       │ api_bug/env_bug/unknown        │ code_bug + conf<0.7        │ code_bug conf>=0.7
       ▼                                  ▼                             ▼
  build_handoff_report_node          build_handoff_report_node    build_signature_node
       │                                  │                             │
       └────────────────────────────────┴┘                            ▼
                                          │                   lookup_short_memory_node
                                          │                        │
                                          │                   hit ─┴─ miss
                                          │                    ▼        ▼
                                          │              apply_fix  retrieve_long_memory_node
                                          │                    │        │
                                          │                    │   repair_code_node
                                          │                    │        │
                                          │                    └──┬─────┘
                                          │                       ▼
                                          │                apply_fix_node ──core.utils.atomic_write_text──
                                          │                       ▼
                                          │                retest_node ──io.executor.run_pytest──
                                          │                       │
                                          └──────────────────┐    │
                                                             │    ├─route_after_retest── passed ─▶ persist_memory_node ▶ final_report_node ─▶ [END]
                                                             │    │                      retry  ─▶ run_tests_node（循环直到 max_rounds）
                                                             │    │                      handoff▶ build_handoff_report_node ▶ final_report_node ─▶ [END]
                                                             └────┘
```

### 4.1 关键熔断 / 门控

- **置信度门控（分类后）**：`code_bug + confidence < 0.7 → handoff`，避免 LLM 低置信下误修（见 [router.py:29-31](../lang_agent/graph/router.py#L29-L31)）。
- **AST 门控（修复后）**：断言数下降 / 缺 `def test_` / SyntaxError → 抛 RepairGateBlockedError 并拒绝写入（见 [repair_chain.py:38-64](../lang_agent/chains/repair_chain.py#L38-L64)）。
- **轮次熔断（重测后）**：`repair_round >= heal.max_rounds（默认 3）→ handoff`（见 [router.py:44-47](../lang_agent/graph/router.py#L44-L47)）。
- **长期记忆门控（写回时）**：仅在 `retest passed + 非短期记忆命中` 时写 ChromaDB（validated-only 原则）。

---

## 5. 诊断与记忆策略

### 5.1 三层诊断输出（diagnosis_chain 必出 7 字段）

```jsonc
{
  "error_category": "code_bug | api_bug | env_bug",
  "error_type": "AssertionError / ConnectionError / ...",
  "error_signature": "<行号归一化后的稳定签名>",
  "error_summary": "1~2 句中文摘要",
  "confidence": 0.0 ~ 1.0,
  "reasons": ["2~4 条依据"],
  "actionable_hint": "一句话可操作提示"
}
```

- LLM 不可用时，走 heuristic 兜底：confidence 固定 **0.55**，保证不会被 0.7 门控误伤，又保留"我是猜的"信号。

### 5.2 记忆分层

| 记忆层 | 命中键 | 写入条件 | 命中收益 |
| --- | --- | --- | --- |
| 短期（KV 文件） | `current_file::error_signature` | 任何 apply_fix_node 成功即写 | 0 LLM 延迟、可离线命中 |
| 长期（ChromaDB） | `error_type + $and{validated=True}` + embedding 或 signature 重排 | retest passed + 非 short hit | few-shot 质量提升、跨项目迁移 |

---

## 6. 产物目录约定（建议统一）

```
output/
├── generated/      # 由 generate 输出，等价旧 generated_tests/，可删可重生
│   ├── api/
│   ├── testcases/
│   ├── utils/
│   ├── data/
│   ├── config/
│   ├── reports/
│   ├── conftest.py
│   └── pytest.ini
├── reports/        # RunReport / handoff_report / pytest json-report
└── diffs/          # 每轮修复前后 patch，格式 diff_<run_id>_r<round>_<file>.patch
```

> 本项目当前仍保留兼容旧默认值：`output_dir=generated_tests`、`report_path=.cache/...`。**下一阶段（P1）统一改到 output/ 三目录，保持 CLI 与 README 一致。**

---

## 7. 安全执行层（P1 升级：`io/sandbox/`）

当前 executor 在宿主机直接执行，已在目录中预留 `io/sandbox/` 位置，升级策略：
- **双执行器**：`HostExecutor`（当前默认，保留本地体验）+ `DockerExecutor`（CI 默认，沙箱隔离）
- **策略文件**：`io/sandbox/policy.yaml`（内存/CPU/超时/网络白名单/可写目录白名单）
- **CI 默认**：`configs/default.yaml` 中 `executor: docker`；本地默认 `executor: host`；不破坏"面试机器没 Docker 也能跑"

---

## 8. 异常家族（BaseSelfHealingError）

5 种业务异常统一集中在 [core/utils.py](../lang_agent/core/utils.py)：

```
BaseSelfHealingError
├── OpenAPIParserError        io/parser 抛，env_bug 类
├── TestRunnerError           io/executor 抛，env_bug 类
├── LLMUnavailableError       llm/factory / repair_chain 抛，code_bug 类
├── DiagnosisBlockedError     chains/diagnosis_chain 抛，code_bug 类
└── RepairGateBlockedError    chains/repair_chain 抛，code_bug 类（断言削弱/语法错）
```

任何上述异常在 generate/heal 入口被 [runner.py](../lang_agent/graph/runner.py) 捕获：`_build_handoff_from_exception → save_run_report`，保证"即便全流程崩了，也有结构化报告可读"。

---

## 9. 可观测清单（用于面试官追问"怎么看线上表现"）

1. **RunReport**：每次运行模式、停止原因、修复轮次、失败数、短/长记忆命中、完整 repair_history。
2. **HandoffReport**：分类停止、置信度不满足、轮次耗尽、业务异常时必落盘，含 error_log 与 actionable_hint。
3. **RepairHistoryEntry × N**：每轮 outcome/error_category/diagnosis 三字段，直接支持"修复链路"复盘。
4. **pytest json-report**：保留原始 failure 详情（`.cache/pytest_report*.json`）。
