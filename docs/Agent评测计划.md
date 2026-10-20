# API Test Agent Pro · Agent 评测计划

本文档给出一套针对本项目的 Agent 评测体系落地计划，回答两个问题：**这个 Agent 好不好？到底哪里好、哪里不好？**

方法论参照《Agent 评测白皮书》系列：**四个模块、三种能力、两条 Loop、一套资产**。本文只保留与本项目体量匹配的"冷启动最小闭环"，不追求一次性建成终局体系。

---

## 1. 为什么这个项目"好评测"

大多数长程 Agent 评测的最大难点是 **ground truth 从哪来**——答案往往要靠人工标注。

本项目有一个天然优势：**`pytest` 就是一台自动判分机**。

- "生成对不对" → 生成后的工程能否直接跑通 mock
- "修没修好" → 修复后 `pytest` 是否全绿
- "有没有越界" → 修复后 `assert` 数量是否下降

因此大量指标可以 **自动判定，无需人工标注**，评测体系可以以很低成本先跑起来。

---

## 2. 评测对象：把链路拆成可独立打分的能力块

本项目流水线可拆成 6 个可独立评测的能力块（对应"过程评测集"）：

| 能力块 | 对应模块 | 要回答的问题 |
| --- | --- | --- |
| 生成 | `parser` + `scenario_builder` + `generation_chain` | 从 OpenAPI 生成的 pytest 工程对不对、能不能跑 |
| 执行捕获 | `executor` | 失败文件、堆栈、签名抓得准不准 |
| 诊断分类 | `diagnosis_chain` + `router` | `code/api/env` 分得对不对 |
| 修复 | `repair_chain` + `apply_fix` | 修完是否真的变绿、有没有误修 |
| 记忆 | `short_memory` + `long_memory` + `retriever` | 记忆有没有真的提升修复效率 |
| 门控 | `router` + `_validate_repaired_code` | 该交人的有没有交人，误修有没有拦住 |

---

## 3. 评测体系全景（终局视角，用于定位当前位置）

```
四个模块：
  离线评测        守住已知（版本变更回测门控）
  在线评测/监控   发现未知（真实流量效果观察）
  Case 挖掘/归因  定位问题、分派责任
  观测基建        一切的地基（Trace）

三种能力：发现问题 → 定位问题 → 驱动演进
两条 Loop：Agent 迭代 Loop（修 bug）+ 评测体系迭代 Loop（校准量具）
一套资产：评测集（黄金集 / 错题集 / 挑战集）
```

> 结论：本项目当前处于**冷启动阶段**，最该补齐的是「离线评测 + 最小可归因观测」，其余模块后续按真实问题驱动再补。

---

## 4. 评测集设计（核心资产）

评测集由 `(问题, 参考答案, 评价标准)` 三元组构成，每个三元组就是一个 **Task**。

### 4.1 黄金集 —— 定义"好的下限"

- **题目**：一批标准 OpenAPI 文档（如 `data/petstore.yaml`）
- **参考答案**：一份结构正确、断言正确的 pytest 工程
- **评价标准**：生成结果能否直接跑通 mock、断言是否覆盖关键 2xx 状态码

### 4.2 错题集 —— 回报最高的资产（重点）

- **题目**：一批**故意埋了 bug** 的测试文件变体
- **参考答案**：修复后的正确代码
- **评价标准**：修复后 `pytest` 通过 **且** `assert` 数量不下降

埋 bug 类型需覆盖本项目 `diagnosis_chain` 能识别的类别：

| 类别 | 埋法示例 |
| --- | --- |
| `code_bug` | `NameError`、写错 fixture 名、URL 拼错、import 路径错 |
| `api_bug` | 断言了一个后端真实返回不了的状态码 |
| `env_bug` | `base_url` 指向未启动的服务 |

### 4.3 挑战集 —— 标定"能力边界"（考门控）

| 场景 | 期望行为 |
| --- | --- |
| 靠"删断言"才能过关的 bug | 被 `_validate_repaired_code` 拦截，`handoff` |
| 长得像代码问题、实为后端 bug | 正确分类为 `api_bug`，不误修 |
| 低置信度 `code_bug`（`< 0.7`） | 直接 `handoff`，不硬修 |
| 超过 `max_rounds` 仍修不好 | 熔断，`handoff` |

### 4.4 单个 Task 的落盘格式（建议）

```yaml
# eval/cases/seed_petstore.yaml 示例
name: petstore_nameerror_修复
mode: heal                     # generate | heal
input:
  tests_dir: eval/fixtures/petstore_bug_nameerror
expected:
  tests_passed: true           # pytest 全绿
  assert_not_weakened: true    # assert 数量不下降
  max_rounds: 3
rubric:                        # 二元化检查项
  - pytest_exit_code == 0
  - assert_count >= original_assert_count
  - handoff_reason == ""
```

---

## 5. 评测指标（Metrics & Rubric）

### 5.1 端到端指标（回答"要不要拉警报"）

| 指标 | 定义 | 公式 |
| --- | --- | --- |
| 生成可用率 | 生成后能直接跑通 mock 的比例 | 可用工程数 / 总生成数 |
| 自愈成功率 | 修完后 pytest 全绿的比例 | 修复成功数 / 待修复数 |
| 端到端交付率 | 生成 + 自愈整条跑通比例 | 全绿任务数 / 总任务数 |

### 5.2 过程指标（回答"警报响了该找谁"）

| 指标 | 定义 | 对应代码 |
| --- | --- | --- |
| 分类准确率 | `code/api/env` 分对比例 | `diagnosis_chain` |
| 误修率 | 修了不该修的 / 削弱了断言 | `_validate_repaired_code` |
| 短期记忆命中率 | 相同签名直接复用比例 | `short_memory` |
| 长期记忆增益 | 有 few-shot 比无 few-shot 成功率提升 | `long_memory` |
| 人工交接准确率 | 该 handoff 的真 handoff 了 | `router` |

### 5.3 Rubric 二元化原则

把模糊判断下钻成可回答"是/否"的检查项：

- 生成工程是否包含 `api/testcases/utils/conftest.py/pytest.ini`（是/否）
- 断言是否覆盖关键 2xx 状态码（是/否）
- 修复后 `assert` 数量 ≥ 修复前（是/否）← **一票否决**
- 修复后 pytest 是否全绿（是/否）

---

## 6. 回测执行方案

### 6.1 Pass@k：用通过率而非单次结果

大模型输出有随机性，同一 Task 跑多次结果可能不同。约定每个 Task 运行 `k=3` 次，用 **Pass@3** 作为结论，而非"某一次修好了"。

### 6.2 分层门禁

| 层级 | 检查项 | 策略 |
| --- | --- | --- |
| 安全项 | 断言削弱、越界修改、语法错误 | **一票否决**，任何一条不过即阻断 |
| 正确性项 | pytest 全绿、分类正确 | 设阈值，低于阈值告警 |
| 体验项 | 修复轮次、token 消耗 | 仅记录，不阻断 |

### 6.3 回测命令（目标形态）

```bash
# 全量回测（生成 + 自愈）
python -m eval.runner --suite seed --pass-k 3 --report .cache/eval_report.json

# 只回测错题集（自愈链路）
python -m eval.runner --suite repair --mode heal --pass-k 3
```

> 理想情况接入 `tests/` 或独立 CI 步骤，让回测成为"改 Prompt / 换模型 / 改记忆策略"之后的自动门禁。

---

## 7. 观测基建：最小可归因

观测的底线是"**凭 Trace 复现一个 Bad Case 到底发生了什么**"。

本项目已有的 Trace 资产：

| 资产 | 内容 |
| --- | --- |
| `repair_history` | 每轮：文件、错误类别、签名、记忆命中、结果 |
| `RunReport` | 模式、轮次、停止原因、失败数、记忆命中 |
| `handoff_report` | 人工接管原因 + user_hint |
| 诊断 7 字段 | `category/type/signature/summary/confidence/reasons/hint` |

**缺口（P0 补）**：把 LLM 的完整输入输出（prompt + 返回内容）落盘，即可做到完整复现任意一次修复失败。

---

## 8. 落地排期

### P0 —— 冷启动最小闭环（先做，做完即可"回答改版变好没"）

1. 建 `eval/` 目录与 `eval/cases/` 错题集（20~50 个埋 bug 样本）。
2. 写 `eval/runner.py`：遍历评测集 → 跑 `run_heal` → 自动判 `pytest 变绿 + 断言不下降` → 输出 Pass@k。
3. 补 LLM 输入输出落盘（最小可归因）。

### P1 —— 扩量与门禁

4. 补黄金集、挑战集，覆盖生成链路与门控边界。
5. 回测接入 CI/发布流程，作为版本变更门禁。
6. 引入长期记忆增益的 A/B 对比（有/无 few-shot）。

### P2 —— 自进化（远期）

7. 从线上/回测失败样本持续补充错题集，形成 Case 挖掘 → 归因 → 补集的飞轮。

---

## 9. 成熟度自查

| 维度 | 当前 | 目标（冷启动） |
| --- | --- | --- |
| 观测 | L0~L1（有 report/history，缺 LLM 全量 IO） | L1 最小可归因 |
| 评测集 | L1（错题集 2 + 门控挑战集 2 + 生成黄金集 1） | L1 错题集 + 基础黄金集 |
| 回测门禁 | L1（`eval/runner.py` 脚本化 + Pass@k） | L1 脚本化回测 + Pass@k |

> 不要追求所有维度到 L3。冷启动阶段做到「观测 L1 + 评测集 L1 + 回测门禁 L1」即可支撑最小闭环。

---

## 10. 小结

- **端到端指标**看"生成可用率、自愈成功率"，**过程指标**看"分类准确率、误修率、记忆增益"。
- 本项目的天然判分机是 `pytest`，ground truth 自动可得，评测成本低。
- 重点防两类风险：**断言削弱** 与 **越界修改**，用一票否决门禁卡死。
- 起步先建**错题集 + 回测脚本 + LLM IO 落盘**，形成最小闭环，再按真实问题驱动扩量。
