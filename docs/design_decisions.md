# Design Decisions · 关键设计决策记录（ADR）

本文件采用轻量 **Architecture Decision Record (ADR)** 格式：每条记录包含 5 个字段——
`Context / Decision / Consequences / Rejected Alternatives / Notes`。
用于面试时直接展示"为什么这么选"，以及后续重构时不遗忘前提。

---

## ADR-01. 业务编排用 LangGraph 状态机，不手写 if-else

- **Context**：自愈流程至少有"执行 → 收集失败 → 分类 → 查记忆 → 修复 → 回写 → 再执行 → 写记忆 → 人工交接 → 报告" 9+ 步，纯 if-else 很难追踪状态、也难画图说明。
- **Decision**：用 LangGraph 的 `StateGraph` 编译两条独立的图——`_compile_generate_graph`（4 节点）与 `_compile_heal_graph`（12 节点 + 4 条条件边）。
- **Consequences**：
  - 业务流程可序列化（后续可加 LangSmith / LangFuse trace）
  - 节点实现纯函数化，单独 mock state 即可测试
  - 图结构直接对得上 README 的 Mermaid
- **Rejected Alternatives**：
  - 手写 if-else + while round<max_rounds：短期开发快，但调试难、可视化难、难以向面试官讲"状态迁移"
  - Task 队列 + Worker：复杂度过高，不适合本项目作为"作品集项目"的体量
- **Notes**：LangGraph 不可用时，runner 抛 `RuntimeError("langgraph 未安装")`，避免静默降级。

---

## ADR-02. 诊断分类必须输出 confidence/reasons/actionable_hint，低置信 code_bug 不自动修

- **Context**：早期 MVP 只输出 `error_category`，但代码类分类错一次就可能"误删断言 + 长期记忆污染"。面试官通常会追问"AI 说错了怎么办"。
- **Decision**：
  - diagnosis 结果强制 7 字段 schema（见 architecture.md §5.1）
  - `route_after_classification` 增加规则：`code_bug + confidence < 0.7 → handoff`
  - 缺省 confidence 时保持兼容（仍走 code_bug 修复链），避免老数据被拦
- **Consequences**：
  - 低置信度的"误修风险"被大幅压低，面试官追问安全时直接指这条
  - handoff_report 结构能复用到"env_bug / api_bug / 轮次熔断 / 诊断置信不满足"四种停机原因
- **Rejected Alternatives**：
  - 阈值 0.8：会 handoff 太多，显得 Agent 没用
  - 阈值 0.5：误修风险高，长期记忆会被污染
- **Notes**：启发式兜底（没 LLM）confidence 固定 **0.55**——既不会被 0.7 门控误伤，也能被面试官看到"我是故意给出猜测信号"。

---

## ADR-03. 长期记忆只写 validated-only（retest 通过 + 非 short hit）

- **Context**：LLM 修复一次"看起来对"但其实是靠断言削弱过关的情况非常常见，一旦写进长期记忆，后面所有类似错误都会学到坏修复。
- **Decision**：
  - `persist_memory_node` 只有在 `retest exit_code==0 + 无失败 + short_memory_hit==False` 才调 `long_memory.add_validated_fix`
  - ChromaDB 元数据 `validated=True`，检索时强制 `$and validated=True`
- **Consequences**：
  - 长期记忆脏数据风险极低，几个月之后依旧可用
  - 记忆召回时质量更高（few-shot 例子都是"真修好了"的）
- **Rejected Alternatives**：
  - 只要 propose 就写记忆：脏数据快，3 轮迭代后知识库就废了
  - 由人工 review 才写入：作品集项目不可能有人工 review 环节
- **Notes**：面试时这句话直接背：**"validated-only + chroma where 子句"是我防止记忆污染的策略。**

---

## ADR-04. 文件写入统一走原子写（tempfile + fsync + os.replace），半写态不允许

- **Context**：生成/修复过程中，如果磁盘写满或进程中途被杀，旧文件会被截断成半写态，后续恢复非常麻烦；面试常问"崩溃后怎么恢复"。
- **Decision**：
  - 新文件统一用 `core/utils.atomic_write_text`：`mkstemp → write → fsync → os.replace → 异常清 tmp`
  - 禁止 `path.write_text` 直接覆盖（新代码走 atomic_write，旧代码全部替换完成）
- **Consequences**：
  - 任何异常下旧文件保持原状，具备可回滚性
  - `test_utils_robustness.py` 用 monkeypatch 模拟 `os.fdopen` 失败就能测
- **Rejected Alternatives**：
  - 写 `.bak` 再 rename：语义等价，但要多一个文件、清 tmp 逻辑更杂
- **Notes**：Windows NTFS 下 `os.replace` 仍是原子跨卷不一定原子；项目里同目录写，所以没问题。

---

## ADR-05. 诊断链 / 修复链统一提供 heuristic 兜底，不依赖 LLM 必达

- **Context**：面试 demo 当天，网络抖动或 API 配额用完是常事。"没有 LLM 就废了"会被打分为纯 prompt 项目。
- **Decision**：
  - `diagnose()`：LLM 不可用 / 抛错 → 走 `_heuristic_category` + confidence 0.55
  - `generate_pytest_project()`：LLM 不可用 → 走 `_template_testcase_code`（模板 + CRUD 场景）
  - `repair_test_file()`：LLM 完全没 key → 抛 `LLMUnavailableError`，runner 写 handoff_report；调用超时走 tenacity 2 次
- **Consequences**：
  - 无 LLM 仍能：读 OpenAPI → 生成工程 → 跑 pytest → 分类失败 → 给出 handoff 报告
  - 面试官现场断网也能演示（作品集项目最怕"当场 demo 不 work"）
- **Rejected Alternatives**：
  - 只依赖 LLM、没 key 直接 Exception：风险太大，demo 失败是作品集项目致命伤
- **Notes**：生成链 / 诊断链 / 修复链的 tenacity 全部独立降级 `try / except`，保证 import 时即便缺 tenacity 也不崩。

---

## ADR-06. 目录按"入口层 / 业务内核层 / 横切能力层 / 产物层"拆，不按文件类型平铺

- **Context**：MVP 阶段 parser/executor/config/signatures/utils 全部平铺在 `lang_agent/`，看起来像"一堆脚本"；面试官一打开目录容易觉得工程感弱。
- **Decision（本次落地的重组）**：
  - 业务内核（**零外部副作用依赖**）：`chains/` `graph/` `memory/`
  - 横切能力（**副作用集中层**）：`io/`（parser/executor/report + 预留 sandbox）、`llm/`（factory/prompts）、`core/`（config/signatures/utils）
  - scenario_builder 不再挂 lang_agent 根，落到 `chains/scenario_builder.py`
- **Consequences**：
  - 新增沙箱执行器只改 `io/sandbox/` + runner 里切 executor 开关
  - 新增报告格式（CTRF/Allure）只改 `io/report.py`
  - 新增模型供应商（Claude/Ollama）只改 `llm/factory.py`
  - 所有 tests 只需调 import 路径即可，逻辑零改动
- **Rejected Alternatives**：
  - 按"功能包"全部平铺：短期 OK，但加 sandbox 之后会越来越乱
  - 按 DDD 拆 domain/application/infrastructure：作品集项目过重，面试难讲清
- **Notes**：`scenario_builder.py` 本回合放进 `chains/`（因为它是"parser 之后 → generation 之前"的能力链一环）；如果后续加了 domain 层再挪。

---

## ADR-07（P1，下一步）. 执行器分 HostExecutor + DockerExecutor，CI 默认沙箱

（本条为已决策但未实现的记录，面试时可以直接讲路线图，不会被追"现在直接宿主机跑不安全"。）

- **Context**：`io/executor.py` 直接 subprocess 跑 pytest，有环境变量泄漏、路径写穿、`rm -rf /tmp` 等风险。
- **Decision（P1 计划）**：
  - `io/sandbox/docker_runner.py` 做 bind mount：代码目录只读、output/reports 可写、network 默认断网或只允许 `host-gateway:8000`
  - `io/sandbox/policy.yaml` 存策略：超时、CPU 核数、内存、允许的域名白名单、允许写的目录
  - Settings 新增 `executor: host | docker`，本地默认 host，CI 默认 docker
- **Consequences**：安全扣分点直接被化解为路线图亮点。
- **Rejected Alternatives**：Python-level RestrictedPython / AST 黑白名单：做不净（标准库就能绕过），也难解释给面试官。
- **Notes**：目录已预留 `io/sandbox/__init__.py`，后续只写俩文件即可。
