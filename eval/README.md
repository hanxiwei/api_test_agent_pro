# eval · Agent 评测回测脚本

本目录是 [Agent评测计划.md](../docs/Agent评测计划.md) 的可执行落地，用于回答"改 Prompt / 换模型 / 改记忆策略之后，Agent 有没有变好"。

## 结构

```
eval/
  cases.yaml                      评测集定义（错题集 + 门控挑战集 + 生成黄金集 + 记忆能力）
  runner.py                       回测脚本（CLI 入口）
  fixtures/bugs/<name>/           埋 bug 的坏文件，会覆盖到基准工程 testcases/
  runs/                           每次回测的临时工程与汇总（可删，gitignore）
```

## 前置条件

1. 存在一份基准工程 `generated_tests/`（正确的 petstore pytest 工程）：

   ```bash
   python cli.py generate -i data/petstore.yaml -o generated_tests
   ```

2. 自愈类 case（`nameerror` / `typeerror`）依赖 LLM，需在 `.env` 配置 `OPENAI_API_KEY`（及 `OPENAI_BASE_URL`）。未配置时 runner 会提示，且这类 case 会被启发式门控拦下（预期 handoff）。

3. mock 服务默认由 runner 自动启动，无需手动开。

## 使用

```bash
# 先看加载了哪些 case（不真正执行）
python eval/runner.py --dry-run

# 全量回测（自动启动 mock）
python eval/runner.py

# 只跑自愈错题集 / 门控挑战集 / 生成黄金集 / 记忆能力
python eval/runner.py --suite repair
python eval/runner.py --suite gate
python eval/runner.py --suite generation
python eval/runner.py --suite memory

# 调高重复次数（Pass@k）
python eval/runner.py --pass-k 3
```

结果会打印到控制台，并写入 `eval/runs/summary.json`。

## 内置 case 说明

| case                 | 埋的 bug / 输入                                     | 期望行为                        | 依赖 LLM | 依赖 mock |
| -------------------- | --------------------------------------------------- | ------------------------------- | -------- | --------- |
| `nameerror_selfheal` | `create_pet` 写成 `create_pett`（运行时 NameError） | 自愈修复，pytest 变绿           | 是       | 是        |
| `typeerror_selfheal` | `create_pet` 少传 `payload`（运行时 TypeError）     | 自愈修复，pytest 变绿           | 是       | 是        |
| `syntax_gate`        | 文件末尾未闭合 `def`（collect 阶段语法错误）        | 被 errored 拦截，不盲目修       | 否       | 否        |
| `apibug_gate`        | 后端返回 201，断言错写成 200（AssertionError）      | 分类 api_bug 交人，不误修       | 是       | 是        |
| `petstore_generate`  | 输入 `data/petstore.yaml`                           | 生成结构完整、可 collect 的工程 | 是       | 否        |
| `short_memory_reuse` | `create_pet` 写成 `create_pett`，同一 bug 修两次    | 第二次命中短期记忆、零 LLM 复用 | 是       | 是        |
| `no_pollution`       | 后端返回 201，断言错写成 200（api_bug）             | handoff 且未写入记忆            | 是       | 是        |

## 判分逻辑

- 自愈类（`expect_pass: true`）：`pytest 变绿` **且** `assert 数量不下降` 才算通过。
- 门控类（`expect_pass: false`）：`pytest 未变绿` 即算通过（证明没有被错误修复）；若配置了 `expect_category`，还会校验 handoff 分类一致（如 `api_bug`）。
- 生成类（`mode: generate`）：`结构完整`（关键文件齐全 + 存在 testcases/test\_\*.py）**且** `pytest --collect-only 成功` 才算通过。
- 记忆类：
  - `short_memory_reuse`：第一次 `修好且未命中` + 第二次 `修好且命中短期记忆` 才算通过（证明零 LLM 复用）。
  - `no_pollution`：`未通过 pytest` **且** `短期记忆为空` **且** handoff 分类正确，才算通过（证明错误修复不污染记忆）。
- 每个 case 跑 `pass_k` 次，用 `Pass@k` 通过率，避免单次大模型随机性误判。

## 扩展

- 新增自愈 case：在 `fixtures/bugs/<name>/` 放一个埋 bug 的 `test_*.py`，并在 `cases.yaml` 增加一条。
- 新增门控 case：同上，`expect_pass: false`。
- 接入 CI：把 `python eval/runner.py --suite repair` 作为发布前门禁步骤。
