# 21天复刻学习计划：从空目录一比一吃透 API Test Agent

> 适用：想把这个项目写成校招简历核心项目、并扛住面试官三连问的人。  
> 核心原则：**每天只学 1.5~2 小时；每天都有 3 条能跑通的验收单测；当天必须能用 5 分钟口头回答 3 个自检问题；吃透一条才写一条简历 bullet。**

---

## 使用方法（重要，请先读这 7 条）

1. **新建一个干净目录**作为你的复刻仓库，例如 `api_test_agent_fork/`，不要直接在本仓库改；遇到写不下去再回本仓库看实现，看完删掉再手敲一遍。
2. **每天不要跳阶段**：S0→S1→S2→S3→S4 顺序不能反；前一天的 3 条单测跑不通，就不要进入下一天。
3. **每天结束做两件事**：① 独立跑「今天的 3 条验收单测」全部 pass；② 录一段 5 分钟语音，回答「当天 3 个口头自检问题」——答不出来就说明今天没吃透，花 15 分钟再看一遍代码和注释。
4. **简历 bullet 只加已吃透的**：每天结束判断自己是否"能口头讲 3 分钟 + 被追问 3 层不卡壳"，能做到才去简历里加对应 1 条 bullet，没做到先不加。
5. **不要主动说「AI 写了第一版」**：但面试如果问"你做项目踩过什么坑"，要能讲 1~2 个你复刻时亲踩的坑（例如"原子写在 Windows 同目录 replace 原子、跨目录不是原子；我加了目录检查"），这就是你的真实经历。
6. **数字不要乱写**：如"修复成功率 72%→89%"，必须等 S4 你真的拿 30~50 个失败样本跑一遍算出来，再写进简历；没算之前写定性描述"显著降低误修率与知识库污染率"。
7. **本仓库是"参考答案"，不是"抄的对象"**：你每天的目标是"我能在空目录里手写同样功能，并写出能证明它对的测试"，不是"我复制了一份能跑的"。

---

## 五个阶段总览（21 天总地图）

| 阶段                   | 天数    | 你会掌握什么                                                                                                   | 对应简历里能陆续新增几条 bullet              |
| ---------------------- | ------- | -------------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| **S0 准备**            | D1~D3   | 环境 + 四层架构脑图 + 输入输出总览；会看 RunReport/HandoffReport                                               | （暂不加，先打底）                           |
| **S1 工程底座**        | D4~D8   | config、signatures、utils（原子写+异常家族）、io/parser、io/executor、io/report                                | 2 条（底座 + 解析/执行/报告）                |
| **S2 链 & 记忆**       | D9~D15  | scenario_builder、generation/diagnosis/repair 三条链、双层 memory + retriever、llm factory + prompts、AST 门控 | 2 条（双层记忆 RAG + 三层防御 + LLM 兜底）   |
| **S3 LangGraph 编排**  | D16~D19 | state、nodes、router、runner、两张状态机图、异常兜底 handoff、置信度<0.7 handoff 门控                          | 2 条（状态机全链路 + 双层不误修）            |
| **S4 入口 & 面试可讲** | D20~D21 | CLI、Streamlit、Skill 文档；13 自测全绿；1 分钟/3 分钟话术；评测集（可选）；把「吃透的」正式写进简历           | 加剩余 bullet，补齐"评测维度/技能封装"等表述 |

---

# S0 · 准备（D1~D3）——先把"这项目在干啥"装进脑子里

## Day 1：项目全景 + 环境就绪

**学习目标**：能一句话讲清项目解决的痛点；能画出四层架构脑图；本地虚拟环境可用。

**你要做的事**：

1. 通读 README 的「背景 / 这个项目干了什么 / 功能特性 / 架构 / 快速开始」5 节。
2. 通读 [architecture.md](architecture.md) §1~§4。
3. 建立干净复刻目录，建虚拟环境并 `pip install -r requirements.txt`（从本仓库复制一份 requirements.txt 过去）。
4. 在本仓库里运行一次 3 条命令，先看一眼真实产物：
   - `python mock_api_server.py  `（另一个终端，跑在后台）
   - `python cli.py generate -i data/petstore.yaml -o D:/tmp/fork_demo_generated`
   - `python cli.py heal -t D:/tmp/fork_demo_generated` 后再 `python cli.py report` 看 RunReport

**当天必跑的 3 条验收命令（空断言/能 print 也算过）**：

1. `python -c "import yaml, requests, pytest; print('deps ok')"`
2. 能 print 出 README 里四段分层架构（把架构图 ASCII 写进一个 txt，py 里读出来打印，保证你至少看过一遍）
3. `python -m pytest tests -q`（在本仓库跑，先亲眼见过全绿 13 passed 是什么样）

**口头自检 3 问（录 5 分钟语音）**：
Q1：这个项目解决的两个核心痛点是什么？（答：接口用例写得慢 + 业务迭代后脚本维护贵）
Q2：四层架构分别是什么？各自职责一句话。（答：入口层 / Harness 层 / 横切 io+llm+core 层 / 产物层）
Q3："机器"和"生成结果"分别指哪些目录？（答：机器=lang_agent+cli+app；生成=generated_tests+output+reports）

**锚点文件**： [README.md](../README.md) §背景§特性§架构、[architecture.md](architecture.md) §1~§4。

---

## Day 2：认识核心数据对象（Endpoint / Settings / TestFailure / RunReport）

**学习目标**：能不看文档说出 4 类核心对象的字段含义；能手动构造 1 个 Settings。

**你要做的事（在 fork 目录里开始写代码）**：

1. 新建 fork 里的 `lang_agent/core/__init__.py`，只写空文件；
2. 复刻 `core/config.py`：先只写 4 个 `@dataclass`（ModelSettings/HealSettings/MemorySettings/Settings），`load_settings` 暂时不写，今天只要字段齐。
3. 复刻 `io/parser.py` 里 `HttpMethod / Endpoint` dataclass（先不写 parse_openapi）。
4. 复刻 `io/executor.py` 里 `TestFailure / PytestRunResult` dataclass。
5. 复刻 `io/report.py` 里 3 个 dataclass（RepairHistoryEntry/RunReport/HealReport）和 save/load 函数（今天先写空函数 + docstring，明天补）。

**当天必跑的 3 条验收单测（fork 目录里新建 `tests/day2_test.py`，用最小 unittest）**：

1. `test_settings_fields`：实例化一个 Settings，能 assert output_dir / model.name / heal.max_rounds 三个字段存在。
2. `test_endpoint_fields`：实例化一个 Endpoint（method='get', path='/pets', operation_id='getPets'），assert endpoint.method + path。
3. `test_report_dataclass_to_dict`：构造一个最简 RepairHistoryEntry（round=1, file='a.py', error_category='code_bug', error_type='AssertionError', error_signature='sig', short_memory_hit=False, long_memory_used=False, outcome='passed'），调用 `.to_dict()` 断言得到 dict。

**口头自检 3 问**：
Q1：为什么 Settings 要按 model/heal/memory 拆？（答：分层合并、CLI overrides 只改需要部分、多环境 yaml 好维护）
Q2：PytestRunResult 为什么把 failures 单独列成 list，不只存 raw report？（答：后面 classify/build_signature 节点直接用，解耦报告格式升级）
Q3：RunReport 为什么要 handoff_report / repair_history 两个字段？（答：handoff 给人看，repair_history 给记忆和复盘用）

**锚点文件**：
[core/config.py](../lang_agent/core/config.py)、
[io/parser.py](../lang_agent/io/parser.py#L18-L29)、
[io/executor.py](../lang_agent/io/executor.py#L21-L31)、
[io/report.py](../lang_agent/io/report.py#L18-L53)。

---

## Day 3：把数据链路串起来（空实现版）

**学习目标**：在 fork 目录里写出"最小可跑骨架"——即：解析 Endpoints → 生成假的 Output → 保存 RunReport。

**你要做的事**：

1. 写一个最小的 `io/parser.py`：`load_openapi_spec` 只用 `yaml.safe_load` 读 `data/petstore.yaml`，返回顶层 dict；`parse_openapi` 写 5 行硬编码返回一个写死的 list[Endpoint]（2~3 个 endpoint 就行，今天先不求真解析）。
2. 写一个最小的 `generation_chain.py`：`generate_pytest_project` 不接 LLM，只 mkdir + `touch api/__init__.py / testcases/__init__.py / conftest.py / pytest.ini` 6 个空文件。
3. 写一个最小的 `report.py save_run_report`：把 dict 写进 json，再 `load_run_report` 读回来。
4. 写一个"0 状态机" `runner.py`：写 `run_generate_minimal()` 串起来：parse→generate→save_report，并跑一次。

**当天 3 条验收单测（fork 目录 tests/day3）**：

1. `test_parse_openapi_returns_list`：断言写死的 parse 能得到 len>=2 的 list[Endpoint]。
2. `test_generate_creates_conftest_and_pytest_ini`：generate 后 Path('conftest.py').exists() + Path('pytest.ini').exists()。
3. `test_save_and_load_run_report`：save 再 load，断言 RunReport.mode 字段能 roundtrip。

**口头自检 3 问**：
Q1：为什么今天可以用"写死的 Endpoints"照样跑最小链路？（答：调试分层的关键是先让上下游耦合变小，parser/generator/report 各自独立可测）
Q2：为什么 generate 先只 mkdir + touch 6 个空文件？（答：分层骨架先对，内容后补）
Q3：RunReport 为什么用 `json.dumps` + `indent=2 + ensure_ascii=False`？（答：中文可读，面试现场 cat 就能看）

**锚点文件**：
[chains/generation_chain.py](../lang_agent/chains/generation_chain.py#L29-L59)、
[io/report.py save_run_report](../lang_agent/io/report.py#L78-L82)。

---

# S1 · 工程底座（D4~D8）——先把「不会被追工程化扣分」的地基打牢

## Day 4：config.py 完整实现（yaml+env+CLI overrides 合并）

**目标**：能写 `load_settings`，做到：默认 yaml + dotenv + CLI overrides 三层合并，且 CLI 优先级最高。

**你要做**：

1. 复刻 `_deep_merge(base, override)`；
2. 复刻 `load_dotenv(override=False)`；
3. 复刻 `load_settings(config_path, overrides)`；加兼容 `os.getenv('OPENAI_MODEL')`；

**3 条验收单测**：

1. `test_default_yaml_loads`：加载 `config.yaml`，assert base_url 为 'http://localhost:8000'。
2. `test_overrides_merge`：overrides={'heal':{'max_rounds':7}}，得到 Settings.heal.max_rounds==7。
3. `test_pytest_args_str_convert`：raw yaml 里 pytest_args 是 [1, '2']，load_settings 后元素全是 str（[1, '2'] → ['1','2']）。

**口头自检 3 问**：
Q1：为什么 override 要 deep_merge，不是直接 dict.update？（答：model/heal/memory 是嵌套，浅 merge 会整层覆盖）
Q2：为什么 load_dotenv(override=False)？（答：用户自己在 shell 里 export 的变量优先，不会被 .env 覆盖）
Q3：为什么 OPENAI_API_KEY 不传进 Settings？（答：密钥不要进 dataclass，永远只从 env 读，避免序列化泄露）

**锚点文件**：[core/config.py load_settings](../lang_agent/core/config.py#L46-L79)。

---

## Day 5：signatures.py + utils.py 异常家族

**目标**：能从真实失败日志抽出 error_type + 稳定错误签名；能自定义 5 类业务异常。

**你要做**：

1. 复刻 `core/signatures.py` 两个函数；
2. 复刻 `core/utils.py` `BaseSelfHealingError + 5 个子类`；
3. 先不急着写 atomic_write_text（明天做）。

**3 条验收单测（给日志写死在 tests/fixtures 目录里一个 fake_traceback.txt）**：

1. `test_extract_assertion_error`：给一段 `AssertionError: Expected 200 but got 500`，断言 error_type 为 'AssertionError'。
2. `test_error_signature_dedup_line_numbers_and_ptrs`：给两段"行号不同、错误相同"的日志，断言签名相同。
3. `test_parser_error_to_dict`：构造 OpenAPIParserError(message, user_hint='hint', details={'path':'x'}), `.to_dict()` 包含三个字段。

**口头自检 3 问**：
Q1：signatures 为什么只取尾部 20 行？（答：错误根因通常在最后）
Q2：为什么把数字和 0x 指针替换成占位符？（答：去掉不稳定信息，命中短期记忆概率才高）
Q3：BaseSelfHealingError 的 user_hint 和 details 有什么区别？（答：hint 给最终用户看一句话怎么做；details 是结构化字段用于 handoff_report）

**锚点文件**：[core/signatures.py](../lang_agent/core/signatures.py)、[core/utils.py 异常家族](../lang_agent/core/utils.py#L9-L40)。

---

## Day 6：原子写 atomic_write_text（今天你面试里的"文件崩溃怎么恢复"就靠它）

**目标**：能实现并测出原子写的 3 种场景——正常写、写失败保留旧文件、父目录不存在。

**你要做**：完整复刻 atomic_write_text（mkstemp→write→fsync→os.replace→异常清 tmp）。

**3 条验收单测（今天的核心，必须全过）**：

1. `test_atomic_write_normal`：写入新内容后，读回与写入一致。
2. `test_atomic_write_failure_keeps_old`：先写 old，再 monkeypatch `builtins.open` 在写 tmp 时抛 OSError，断言文件内容仍是 old，tmp 不存在。
3. `test_atomic_write_creates_parent_dir`：写入 `a/b/c/new.txt`，父目录自动创建且文件存在。

**口头自检 3 问**：
Q1：为什么 fsync 之后再 os.replace？（答：确保磁盘真的写了再替换，不是 OS 缓存）
Q2：为什么 os.replace 而不是先删再 rename？（答：Windows/Posix 同目录下 replace 对已有文件直接替换；先删再 rename 中间态会丢旧文件）
Q3：什么时候 atomic_write_text 不是原子？（答：跨卷 replace 不是原子；所以我默认写同目录）

**锚点文件**：[core/utils.py atomic_write_text](../lang_agent/core/utils.py#L43-L73)。
**对照本仓库 tests**：[test_utils_robustness.py](../tests/test_utils_robustness.py#L19-L81)。

---

## Day 7：io/parser.py 真实解析 + 兼容 Prance 缺失

**目标**：petstore.yaml → 真实 list[Endpoint]（而不是昨天的硬编码）。

**你要做**：完整复刻 parse_openapi；try import prance；prance 不可用则走 yaml fallback。

**3 条验收单测**：

1. `test_petstore_yields_more_than_10_endpoints`：len(parse('data/petstore.yaml')) >= 10。
2. `test_endpoints_have_operation_ids`：所有 endpoint.operation_id 非空。
3. `test_missing_file_raises_parser_error`：parse('does_not_exist.yaml') 抛 OpenAPIParserError 且 details 里含 path。

**口头自检 3 问**：
Q1：为什么 prance 失败就 fallback 纯 yaml？（答：无网络/缺第三方库依旧能跑 MVP，符合 ADR-05 兜底）
Q2：operation_id 缺失时为什么自己拼？（答：后面生成 api 层函数名必须稳定）
Q3：为什么 parameters 合并 path-level 和 operation-level 两份？（答：OpenAPI 规范允许，漏合并则生成的 path parameter 缺失）

**锚点文件**：[io/parser.py parse_openapi](../lang_agent/io/parser.py#L53-L132)。

---

## Day 8：io/executor.py + io/report.py 真实 save/load

**目标**：不跑 LLM，也能：写一个故意失败的 test\_\*.py → subprocess 跑 pytest → 拿到 failures 列表 → 落盘 RunReport 能读回。

**你要做**：

1. 完整复刻 run_pytest（subprocess + json-report + failures 解析 + 非 0/1 抛 TestRunnerError）；
2. 完整复刻 save_run_report / load_run_report。

**3 条验收单测**：

1. `test_run_pytest_exit_0_collects_0_failures`：写一个 `pass` testcase，run 后 exit_code=0，failures 为空。
2. `test_run_pytest_exit_1_collects_assertion_failure`：写一个 `assert 1==2`，failures 里含 AssertionError。
3. `test_test_runner_error_on_invalid_exit_code`：伪造 exit_code=2（pytest 正常是 0/1），要触发抛 TestRunnerError。

**口头自检 3 问**：
Q1：为什么用 `sys.executable -m pytest` 而不是 `pytest`？（答：保证子进程用的就是当前 venv 的解释器，不会用错全局 pytest 缺依赖）
Q2：为什么 exit_code 不在 {0,1} 且 report 为空才抛？（答：pytest 内部崩溃、收集错误可能 exit_code=2/4/5，这时不能当"失败"要当"执行环境问题"）
Q3：为什么 failures 自己拼 nodeid/file/call_longrepr 三个字段？（答：后面 classify 节点只依赖这三个，格式升级 json-report 也不影响）

**锚点文件**：[io/executor.py run_pytest](../lang_agent/io/executor.py#L33-L102)、[io/report.py save/load](../lang_agent/io/report.py#L78-L91)。

---

# S2 · Chains & Memory（D9~D15）——把「AI 怎么想 + 记住什么」写出来

## Day 9：scenario_builder.py（Endpoint 按资源分组 + CRUD 链 + 单接口场景）

**目标**：Endpoints 入，Scenarios 出；每个资源至少 1 条 CRUD + N 条单接口。

**你要做**：完整复刻 build_scenarios + Scenario dataclass。

**3 条验收单测**：

1. `test_petstore_generates_pet_crud_scenario`：scenarios 里出现 'pet_crud'（按 tag 聚合的资源）。
2. `test_each_endpoint_has_single_scenario`：每个 endpoint operation_id 至少对应一个 scenario。
3. `test_crud_contains_at_least_post_and_get`：pet_crud scenario.endpoints 里 method 同时有 post/get。

**口头自检 3 问**：
Q1：为什么要同时有 CRUD 场景 + 单接口场景？（答：CRUD 才体现业务链路一致性；单接口覆盖边界 case）
Q2：为什么资源 key 默认 endpoint.tags[0]？（答：真实 OpenAPI 通常已分组，比我自己拼 path 稳）
Q3：CRUD 链里固定顺序 post→get→put→delete 为什么？（答：最贴近"创建-查询-修改-删除"的真实使用顺序，便于传依赖 ID）

**锚点文件**：[chains/scenario_builder.py](../lang_agent/chains/scenario_builder.py)。

---

## Day 10：llm factory + 三条 prompts

**目标**：在缺 OPENAI_API_KEY 时 `build_chat_llm` 返回 None（不崩）；三条 prompt 都能拼出字符串。

**你要做**：复刻 llm/factory.py（build_chat_llm + build_embeddings）+ llm/prompts.py（generation/diagnosis/repair）。

**3 条验收单测（今天的重点是"不崩"）**：

1. `test_build_llm_returns_none_without_api_key`：临时 unset OPENAI_API_KEY，断言 `build_chat_llm(ModelSettings(...)) is None`。
2. `test_diagnosis_prompt_contains_json_fields`：生成 prompt 字符串，包含 error_category / confidence / actionable_hint 三个词。
3. `test_repair_prompt_contains_few_shot`：传入 2 条 example，断言 prompt 里 example 原文至少各出现 1 次。

**口头自检 3 问**：
Q1：为什么 build_embeddings 遇到 DeepSeek base_url 且没单独配 EMBEDDING_BASE_URL 时返回 None？（答：当前 DeepSeek 没有稳定 embedding；不自动降级就会在 long_memory 构造时崩，违背 ADR-05）
Q2：为什么 diagnosis prompt 明确要求 JSON？（答：router/nodes 要按字段取，结构化才能接门控）
Q3：为什么 generation_prompt 明确要求"只输出 Python 代码不要 markdown"？（答：防 LLM 包 `python` 导致我写盘后是带 markdown 的坏 py）

**锚点文件**：[llm/factory.py](../lang_agent/llm/factory.py)、[llm/prompts.py](../lang_agent/llm/prompts.py)。

---

## Day 11：generation_chain 真实可跑（模板版 + LLM 可选）

**目标**：无 LLM 时，调用生成链也能产出一个最小可运行的分层工程，`pytest generated` 能收集到用例（不要求 passed，能收集到 test function 存在即可）。

**你要做**：完整复刻 generate_pytest_project（scaffold_api_module/scaffold_utils / write_data_file / \_template_testcase_code / \_llm_testcase_code）。

**3 条验收单测（今天的核心）**：

1. `test_generates_at_least_one_py_in_testcases`：generate 后 `output/testcases/` 目录至少有 1 个 `test_*.py`。
2. `test_pytest_collection_passes`：生成后 `run_pytest(output, ['--collect-only', '-q'], report)` 收集到的 tests 数 > 0。
3. `test_conftest_exposes_base_url_fixture`：打开生成的 `output/conftest.py`，字符串 `def base_url` 存在。

**口头自检 3 问**：
Q1：为什么生成 api 层独立模块，不在 test*\*.py 直接写 requests？（答：接口升级只要改 api 层，测试层复用）
Q2：为什么 test*\*.py 要固定用 utils.assertions / data_loader？（答：断言风格、加载种子数据的方式统一）
Q3：为什么所有文件写入都走 atomic_write_text？（答：生成中途 Ctrl+C 不把半写 py 文件留在磁盘）

**锚点文件**：[chains/generation_chain.py](../lang_agent/chains/generation_chain.py#L60-L211)。

---

## Day 12：diagnosis_chain 三类诊断 + 置信度 + heuristic 兜底

**目标**：给一段失败日志，无论 LLM 是否可用，都能得到 7 字段 Diagnosis JSON。

**你要做**：完整复刻 diagnosis_chain.py（Diagnosis dataclass + diagnose + \_heuristic_category + \_parse_diagnosis_json）。

**3 条验收单测**：

1. `test_heuristic_connection_error_becomes_env_bug`：给一段 "ConnectionRefused localhost:8000" 的日志，不接 LLM，返回 diagnosis.category='env_bug'、confidence≈0.55。
2. `test_heuristic_assertion_becomes_code_bug`：给一段 AssertionError 日志，返回 code_bug，confidence=0.55。
3. `test_parse_diagnosis_ignores_extra_fields`：构造一个带多余字段 xxx 的 JSON 字符串，parse 后仍合法（字段只取我们需要的 7 个）。

**口头自检 3 问**：
Q1：为什么 heuristic confidence 固定 0.55？（答：既不会被 0.7 门控误伤，也明确告诉上层"我是猜的"）
Q2：为什么 action_hint 必须是一句人话？（答：handoff 时直接给用户看，不需要再解包）
Q3：为什么 reasons 是数组而不是一句话？（答：给面试官、SDET 自己看能知道分类依据）

**锚点文件**：[chains/diagnosis_chain.py](../lang_agent/chains/diagnosis_chain.py#L23-L163)。

---

## Day 13：repair_chain AST 门控三件套（今天的面试"AI 乱修怎么办"标准答案）

**目标**：能在不接 LLM 时，写出 `_validate_repaired_code` 检测 3 类坏修复，并测试通过。

**你要做**：完整复刻 \_validate_repaired_code / \_count_asserts / \_contains_def_test / \_compile_without_syntax_error / repair_prompt（今天不写 repair_test_file 的 LLM 调，只写 AST 门控 + apply_repair_to_file 原子写）。

**3 条验收单测（今天必须全过）**：

1. `test_validate_blocks_assertion_weakening`：原 3 个 assert 修后 1 个 assert → 抛 RepairGateBlockedError。
2. `test_validate_blocks_missing_def_test`：修后文件里没有 `def test_` → 抛 RepairGateBlockedError。
3. `test_validate_blocks_syntax_error`：修后文件有语法错（写一个 `return if:` 之类）→ 抛 SyntaxError。

**口头自检 3 问**：
Q1：为什么断言削弱是红线？（答：LLM 最容易走的捷径就是把 assert 删掉或改得永远 True，表面"修复"，实则丢了质量）
Q2：为什么只拦"3 件事"不拦更多？（答：低误杀原则；门控过严会把本来能修的也拦掉，handoff 太多就显得 Agent 没用）
Q3：为什么 apply_repair_to_file 要先 validate 再 atomic_write？（答：先保证修好才允许替换旧文件，磁盘上永远是上一次好的或这次好的）

**锚点文件**：[chains/repair_chain.py \_validate_repaired_code](../lang_agent/chains/repair_chain.py#L38-L104)。

---

## Day 14：双层记忆 short_memory + long_memory（validated-only）

**目标**：short 写了下次能 0 LLM 命中；long 只有 validated=True 才写。

**你要做**：

1. 复刻 short_memory.py（ShortMemory：KV save/lookup + file::signature 键）；
2. 复刻 long_memory.py（LongMemory：构造函数 build_embeddings 为 None 时 no-op；`add_validated_fix` / `search`）；

**3 条验收单测**：

1. `test_short_memory_roundtrip`：`save(same file::sig, code)` 再 `lookup`，返回与写入一致。
2. `test_long_memory_disabled_when_embeddings_none`：没 EMBEDDING_API_KEY 时，LongMemory().add_validated_fix(...) 不抛异常（no-op）。
3. `test_long_memory_filters_validated_true_in_metadata`：如果你本地装了 chroma + 有 embedding key，search 只返回 validated=True 的。

**口头自检 3 问**：
Q1：为什么 short 记忆键是 `current_file::error_signature`？（答：同一个文件的同一个错误才敢直接复用，跨文件风险高）
Q2：为什么长期记忆只有 retest passed + 非 short hit 才写？（答：ADR-03 validated-only，防止"删断言过的修复"污染知识库）
Q3：为什么 long_memory.search 要"先 embedding 再 signature 重排"？（答：embedding 抓语义近的；signature 再推字面上完全同类的到最前）

**锚点文件**：[memory/short_memory.py](../lang_agent/memory/short_memory.py)、[memory/long_memory.py](../lang_agent/memory/long_memory.py)。

---

## Day 15：retriever.py + 把 diagnose/short/long/repair 链的组合在一个脚本里跑通（不用状态机）

**目标**：给一段 failure，先查 short（命中就直接用，跳过 LLM），未命中查 long（few-shot），调用 repair（门控），原子写回文件。

**你要做**：

1. 复刻 retriever.py（`retrieve_few_shot_examples` 统调 short + long 记忆）；
2. 在 fork 里写一个 `notebooks/day15_e2e_heal_mini.py` 串：
   → 生成一个故意失败的 `assert 1==2` 小文件
   → diagnose
   → retrieve 0 条
   → 用模板化的 repair 代码（assert 1==1）修回来
   → validate + atomic_write
   → retest passed

**3 条验收单测**：

1. `test_retriever_short_hit_skips_llm`：short 提前 save 后，retrieve 返回命中，函数能区分"short_hit=True"。
2. `test_e2e_mini_passes_retest`：上面脚本跑完后 exit_code==0。
3. `test_e2e_mini_does_not_write_if_gate_blocks`：模板化修后故意只有 0 个 assert，门控拦截且磁盘文件仍是旧的 assert 1==2。

**口头自检 3 问**：
Q1：为什么"short 命中"要和 long_memory_used 区分开记到 RepairHistoryEntry？（答：RunReport 统计"0-LLM 命中率"是非常亮眼的指标）
Q2：为什么 few-shot 最多 2~3 条？（答：再多上下文就太长，LLM 费用高且慢）
Q3：今天串 heal 小闭环和明天 LangGraph 编排的区别是什么？（答：今天是手写 if/while；明天是把每一步变成独立节点，方便 trace + 画图 + 加熔断边）

**锚点文件**：[memory/retriever.py](../lang_agent/memory/retriever.py)、[graph/nodes.py 修复相关节点](../lang_agent/graph/nodes.py#L143-L283)。

---

# S3 · LangGraph 编排（D16~D19）——把"流程"变"可追溯状态机"

## Day 16：state.py + router.py（4 个路由函数 + 置信度<0.7 handoff 门控）

**目标**：能手写 AgentState（TypedDict）所有字段；能单元测 4 个路由判断分支。

**你要做**：

1. 复刻 state.py AgentState TypedDict；
2. 复刻 router.py（route_after_test_run / route_after_classification / route_after_short_lookup / route_after_retest）。

**3 条验收单测（对照本仓库 tests/test_router.py）**：

1. `test_route_classification_confidence_gate`：code_bug + confidence=0.69 → 'handoff'；0.9 → 'build_signature'。
2. `test_route_after_retest_passed`：retest exit=0 → 'persist_memory'。
3. `test_route_after_test_run_errored`：pytest exit=4 或 5 → 'handoff'。

**口头自检 3 问**：
Q1：为什么用 TypedDict 不 dataclass？（答：LangGraph 每个节点会 mutate dict 里字段，TD 天然兼容；dataclass 要 to_dict/from_dict 麻烦）
Q2：为什么缺省 confidence 也要放行 code_bug？（答：兼容历史 state 可能没 confidence 字段；别让用户升级后跑不动）
Q3：为什么 max_rounds 熔断放在 router 里？（答：熔断是"路由决策"——决定下一步去哪，而不是"节点动作"）

**锚点文件**：[graph/state.py](../lang_agent/graph/state.py)、[graph/router.py](../lang_agent/graph/router.py)、[tests/test_router.py](../tests/test_router.py#L33-L46)。

---

## Day 17：nodes.py 先写 Generate 图 4 节点 + final_report_node

**目标**：不接 LangGraph，你也能手动按顺序 `parse_openapi_node→build_scenarios_node→generate_project_node→final_report_node` 调用，得到一个合法 RunReport。

**你要做**：复刻 nodes.py 中 parse / build_scenarios / generate_project / final_report_node 四个节点实现（注意 import 路径要对 fork 目录）。

**3 条验收单测**：

1. `test_parse_node_populates_endpoints`：state 在 parse 后 'endpoints' 非空。
2. `test_generate_project_node_populates_generated_files`：state['generated_files'] len>0。
3. `test_final_report_node_returns_report`：state 包含 'run_report_path'，且 load_run_report 能读回 dict。

**口头自检 3 问**：
Q1：为什么每个节点返回一个 dict（增量字段）而不是直接改 state？（答：LangGraph 会自动把返回 dict merge 到 state；风格统一，方便单测每个节点输出）
Q2：为什么 final_report_node 同时写 report_path 和 state 里的字段？（答：路径给 CLI/UI 读；state 给图后续边用——虽然 Generate 后面没边了，但保持一致）
Q3：为什么在生成链任何异常会被 runner 捕获 handoff？今天你手工测一下节点抛错，手写 catch 后写 handoff。（答：用户不会看到堆栈，只会看到结构化提示 + actionable_hint）

**锚点文件**：[graph/nodes.py](../lang_agent/graph/nodes.py#L38-L140)。

---

## Day 18：nodes.py 写 Heal 图 12 节点 + runner.\_build_handoff_from_exception

**目标**：Heal 图的每个节点单测跑通（输入 state 子集，输出正确字段）。重点：build_signature_node、lookup_short_node、retrieve_long_node、repair_code_node、apply_fix_node、retest_node、persist_memory_node、build_handoff_report_node。

**你要做**：完整复刻 heal 图所有节点 + 手写 runner.\_build_handoff_from_exception（接受任意 BaseSelfHealingError，写 RunReport 含 handoff_report dict）。

**3 条验收单测**：

1. `test_build_signature_node_writes_signature`：给一段 call_longrepr，state 填好 current_file + failures[0]，build_signature 后 state.error_signature 非空。
2. `test_persist_memory_skipped_if_short_hit`：short_memory_hit=True 时，persist_memory_node 不调 long_memory.add_validated_fix（你 mock long_memory 观察没调用）。
3. `test_handoff_from_exception_writes_report`：抛一个 OpenAPIParserError，\_build_handoff_from_exception 后 load_run_report 读到 handoff_report.type == 'OpenAPIParserError'。

**口头自检 3 问**：
Q1：为什么 retest 节点失败后回到 run_tests 而不是 classify？（答：每轮 retest 后可能还有其它文件失败，必须重新全量收集 + 重新 pick_failure）
Q2：为什么 repair_code_node 要同时接 LLM 和 short_memory code？（答：short 命中就别调用 LLM，省钱省时间）
Q3：为什么 build_handoff_report 节点要把 actionable_hint 放在最显眼的字段？（答：handoff 的目的是让人上手修，不是给机器读）

**锚点文件**：[graph/nodes.py Heal 节点](../lang_agent/graph/nodes.py#L143-L285)、[graph/runner.py \_build_handoff_from_exception](../lang_agent/graph/runner.py#L136-L194)。

---

## Day 19：runner.py 两张 StateGraph 编译 + 实际 invoke 跑通 Generate 和 Heal

**目标**：在 fork 目录里真的 import langgraph，`StateGraph().add_node/add_edge/compile()` 两张图，然后：

- run_generate(settings) 成功写 RunReport；
- run_heal(settings, tests_path) ① 先跑 pass 的工程 → ok=True ② 故意改 test 失败 → heal rounds 走至少一轮。

**你要做**：完整复刻 runner.py `_compile_generate_graph / _compile_heal_graph / run_generate / run_heal`。

**3 条验收单测（今天里程碑）**：

1. `test_run_generate_generates_report`：调用 run_generate，run_report_path 指向的 json 文件存在且 ok=True。
2. `test_run_heal_on_pass_is_noop`：给一个 100% passed 的工程，run_heal rounds=0，ok=True，no repair。
3. `test_run_heal_on_code_bug_reaches_round_1`：给一个故意 `assert 1==2` 的工程 + low-confidence 兜底（confidence=0.55），断言最终 stopped_reason='handoff_classification_confidence'。

**口头自检 3 问**：
Q1：为什么图里 START / END 节点要显式加？（答：LangGraph 规范，不加没法确定入口；多个入口容易造成调试混乱）
Q2：为什么 compile() 调用后才允许 invoke？（答：编译后做了一些拓扑检查，能提前发现缺边缺节点）
Q3：为什么 healgraph 里加专门的 handoff 边而不是"节点里 return END"？（答：handoff 是"路径终点"，以后加 LangSmith trace 会单独标出来，统计 handoff 率才准确）

**锚点文件**：[graph/runner.py](../lang_agent/graph/runner.py)。

---

# S4 · 入口 + 简历可讲（D20~D21）——交付给"非你本人"也能使用，然后正式写简历 bullet

## Day 20：CLI 三条命令 + Streamlit 最小版 + Skill 说明文档

**目标**：别人 clone 下你 fork 仓库，看 README 就能跑通 `generate / heal / report` 三条命令。

**你要做**：

1. 复刻 cli.py（generate / heal / report 三个 click 子命令；--config / -i / -o / -t 参数）；
2. 复刻 app.py（Streamlit：上传 yaml + 按钮 generate + 按钮 heal + 显示 RunReport JSON）；
3. 写 `.claude/skills/api-test-agent/SKILL.md` 一份（哪怕只有 20 行，说明 Skill 的触发词/输入输出）。

**3 条验收单测**：

1. `python cli.py report --report-path .cache/latest_run_report.json` 命令运行后退出码 0（只要存在报告就能打印）；
2. Streamlit `streamlit run app.py` 能启动（你可以开浏览器看一眼首页加载不出错就行）；
3. `.claude/skills/api-test-agent/SKILL.md` 文件存在且描述了输入输出。

**口头自检 3 问**：
Q1：为什么 report 命令单独拎出来？（答：面试/debug 时只看报告，不想重跑 generate+heal）
Q2：CLI 的默认输出路径为什么放在 config.yaml 里而不是写死？（答：让 CI 切换到 output/generated 更容易，用户本地也能自己改）
Q3：Skill 文档的 MCP 理念怎么体现在实际代码里？（答：Agent 通过 SKILL.md 协议就能调用 generate/heal，不必改代码对接；这就是"可被编排"的能力）

**锚点文件**：[cli.py](../cli.py)、[app.py](../app.py)。

---

## Day 21：自测 13 passed 全绿 + 1分钟/3分钟 话术 + 正式写简历

**今天的任务清单（不要跳）**：

1. 在 fork 目录里跑：`python -m pytest tests -q`。**今天的目标是让你自己的 fork 仓库能达到至少 10+ passed**（不要急，缺哪个就补哪个；允许今天 + 明天一起调）。
2. 录 1 分钟语音："项目定位 + 三层亮点（门控/记忆/工程化）+ 结果"。
3. 录 3 分钟语音：STAR 版讲解（S 痛点 / T 约束 / A 四个技术动作 / R 13 passed + 7 ADR + 三入口）。
4. 把你**真的能讲 3 分钟 + 被追问 3 层不卡壳**的 bullet 正式写进简历（按之前给你的"强化版 6 条"选 4~6 条）。

**3 条最终验收（今天不要求全部做到，但本周内必须做到）**：

1. `pytest tests -q` 输出 13 passed（对照本仓库 tests 逐个补齐）。
2. 让一个同学/朋友当面试官，随机从 ADR-01~ADR-07 抽 3 条提问，你能不看资料答出。
3. 现场 demo：`generate + heal + report` 三段命令不翻资料 5 分钟内跑完。

**口头终极自检（面试前反复背）**：
Q1：这个项目和"网上一个调 OpenAI 修脚本的 demo"有什么本质不同？（答：我有结构化诊断+置信度门控、双层记忆validated-only、AST 门控防删断言、原子写防半写、异常家族+handoff 可观测、三入口交付——是"工程化 Agent Harness"，不是"单次调用 prompt"）
Q2：你在这个项目里最骄傲的 1 件事是什么？（答：把"AI 容易乱修"这个最大风险，拆成 4 层防御——低置信不接/门控拦删断言/记忆只写验证过/异常都写报告，让系统"修不好就停并解释原因"，而不是"硬修把系统修坏"）
Q3：这个项目下一步你会升级什么？（答：接 DockerExecutor 沙箱执行修复后的 pytest、output 三目录统一、GitHub Actions 让 Build 徽章变真、加 50 条评测集得出真实修复成功率）

**锚点文件**：
[design_decisions.md](design_decisions.md) 七条 ADR；
[README.md](../README.md) §测试基线 13 passed。

---

## 附：复刻完成标准（只有 3 条，满足就可以写简历）

1. **你自己的 fork 仓库里 `pytest tests -q` 能跑出 >=10 passed**；
2. **你能不翻资料口头讲出 S1~S3 的 7 条口头自检**；
3. **你写在简历上的每条 bullet，都能指到 fork 里的具体代码位置**。

只要做到这 3 条，这个项目就是你的，面试时面对三连问完全不虚。祝顺利！
