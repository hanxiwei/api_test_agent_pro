# 21天复写计划：按当前项目一比一复写 API Test Agent

适合对象：
- 你是小白或测开初学者
- 你希望不是“看懂一点点”，而是能从 0 复写出一个能跑的项目
- 你希望最后能把这个项目讲给面试官听，而不是只会运行命令

这份计划是基于**当前仓库已经落地的真实项目结构**写的，不是泛泛而谈的学习提纲。  
也就是说，你后面每天学到的内容，都能在这个仓库里找到对应文件。

---

## 一、你最后要复写出来的到底是什么

这个项目不是“生成几个 pytest 文件”这么简单。  
你要复写的是一套完整工具链：

1. 输入一份 OpenAPI 文档
2. 解析出接口信息
3. 组合成 CRUD 测试场景
4. 生成一套分层的 pytest 接口自动化工程
5. 运行 pytest
6. 如果失败，做失败分类
7. 如果属于代码级 bug，就走 LLM 自愈修复
8. 修完之后重新回归
9. 修复成功后把经验记下来，下一次优先复用
10. 同时支持命令行和 Streamlit 看板

最终目标不是“你抄出一堆文件”，而是：

- 你知道每个模块为什么存在
- 你知道它们的输入输出是什么
- 你能从空项目复写出来
- 你能自己排查跑不通的问题
- 你能在面试里讲清楚整条链路

---

## 二、当前项目真实结构总览

你现在仓库里的关键文件如下：

### 1. 核心源码
- `lang_agent/parser.py`
- `lang_agent/scenario_builder.py`
- `lang_agent/executor.py`
- `lang_agent/report.py`
- `lang_agent/config.py`

### 2. 生成、自愈、提示词相关
- `lang_agent/chains/generation_chain.py`
- `lang_agent/chains/diagnosis_chain.py`
- `lang_agent/chains/repair_chain.py`
- `lang_agent/chains/prompts.py`
- `lang_agent/chains/llm_factory.py`

### 3. 记忆系统
- `lang_agent/memory/short_memory.py`
- `lang_agent/memory/long_memory.py`
- `lang_agent/memory/retriever.py`

### 4. LangGraph 编排层
- `lang_agent/graph/nodes.py`
- `lang_agent/graph/router.py`
- `lang_agent/graph/runner.py`
- `lang_agent/graph/state.py`

### 5. 产品入口
- `cli.py`
- `app.py`

### 6. 演示数据与演示服务
- `data/petstore.yaml`
- `mock_api_server.py`

### 7. 自动生成产物目录
- `generated_tests/`

### 8. 项目自测
- `tests/`

你要始终分清楚两类东西：

- **生成器本体**：`lang_agent/`、`cli.py`、`app.py`
- **生成结果**：`generated_tests/`

前者是“机器”，后者是“机器打出来的产品”。

---

## 三、复写这类项目的正确顺序

很多人会犯一个错误：  
一上来就去写 LLM prompt、写 LangGraph、写自愈。

这会非常乱。

正确顺序一定是：

1. 先把“输入”和“执行环境”建好
2. 再把“生成链路”跑通
3. 再把“pytest 执行与错误收集”做好
4. 最后再做“失败闭环、自愈、记忆”
5. 最后再包装成 CLI / Streamlit

你可以把整个项目理解成三阶段：

### 阶段 A：先会生成
- 能解析 OpenAPI
- 能生成测试工程
- 能跑 pytest

### 阶段 B：再会修复
- 能拿到失败栈
- 能分类失败
- 能修复测试文件
- 能重新回归

### 阶段 C：最后变产品
- 能命令行运行
- 能看板运行
- 能展示报告
- 能给面试官讲清楚

这就是 21 天计划的底层安排逻辑。

---

## 四、21天完整学习与复写计划

下面是详细版。  
每一天我都给你写了：

- 今天目标
- 为什么今天做这个
- 你要读哪些文件
- 你要做哪些动作
- 你今天至少要产出什么
- 你怎么判断自己完成了
- 常见错误是什么

---

# 第1周：先把“生成链路”建立起来

这一周你先不要碰 LangGraph 和自愈。  
你先把“输入 OpenAPI -> 生成 pytest 工程 -> 跑通测试”做出来。

---

## Day 1：认识项目，搭好环境

### 今天目标
- 知道项目在解决什么问题
- 能说清项目里“机器”和“生成结果”的区别
- 本地开发环境可用

### 为什么先做这个
如果你连项目结构都没认清，后面每个文件都会看得很痛苦。

### 今天重点理解
这个项目一句话描述：

> 根据 OpenAPI 自动生成接口测试工程，运行失败后再用 LLM 自愈修复。

### 今天要读的文件
- `README.md`
- `requirements.txt`
- `app.py`
- `cli.py`

### 今天要做的动作
1. 看一遍仓库顶层目录
2. 安装依赖
3. 验证关键库能导入

### 参考命令
```bash
python --version
pip install -r requirements.txt
python -c "import pytest, yaml, requests; print('ok')"
python -c "import click, streamlit; print('ok')"
```

### 今天最小产出
- 一张你自己的笔记：
  - `lang_agent/` 是什么
  - `generated_tests/` 是什么
  - `mock_api_server.py` 是什么

### 完成标准
- 依赖安装成功
- 你能口头说清楚项目主线

### 常见错误
- 虚拟环境没激活
- pip 装错 Python 版本

---

## Day 2：理解整个链路，不写代码也要讲明白

### 今天目标
你能把整条链路用自己的话讲出来。

### 为什么今天单独讲链路
这是后面所有模块的地图。

### 今天要读的文件
- `app.py`
- `cli.py`
- `lang_agent/graph/runner.py`

### 今天要做的动作
把链路抄下来并理解：

1. OpenAPI 输入
2. parser 解析
3. scenario_builder 场景构建
4. generation_chain 生成测试工程
5. executor 跑 pytest
6. diagnosis 分类
7. repair 修复
8. memory 记忆
9. report 报告
10. app/cli 展示

### 今天最小产出
自己写 10 句话，每句只解释一个模块干什么。

### 完成标准
你能在不看文档的情况下，大致说出项目流程。

---

## Day 3：写 mock API，先让测试有地方打

### 今天目标
- 知道为什么一定要有 mock 服务
- 能写出最小 CRUD 服务

### 为什么先写它
因为没有后端服务，生成出来的测试根本没法验收。

### 今天要读的文件
- `mock_api_server.py`
- `data/petstore.yaml`

### 今天要理解的概念
- `GET /pets`
- `POST /pets`
- `GET /pets/{petId}`
- `PUT /pets/{petId}`
- `DELETE /pets/{petId}`

### 今天要做的动作
1. 阅读 `mock_api_server.py`
2. 看看它用什么方式存储“宠物数据”
3. 理解每个接口的返回状态码
4. 亲自启动它

### 参考命令
```bash
python mock_api_server.py
```

新开一个终端测试：

```bash
python -c "import requests; print(requests.get('http://127.0.0.1:8000/pets').status_code)"
```

### 今天最小产出
一张表：

| 方法 | 路径 | 含义 | 成功状态码 |
|---|---|---|---|
| GET | /pets | 查询列表 | 200 |
| POST | /pets | 创建宠物 | 201 |
| GET | /pets/{petId} | 查单个 | 200/404 |
| PUT | /pets/{petId} | 更新 | 200 |
| DELETE | /pets/{petId} | 删除 | 204 |

### 完成标准
- mock 服务能启动
- 你能成功访问一个接口

### 常见错误
- 8000 端口被占用
- 服务没开就去跑测试

---

## Day 4：理解 OpenAPI 文档是怎么被程序“读懂”的

### 今天目标
- 明白 OpenAPI 不是“给人看的文档”，也是“给程序吃的输入”
- 知道 parser 最终要抽取哪些字段

### 今天要读的文件
- `data/petstore.yaml`
- `lang_agent/parser.py`
- `tests/test_parser.py`

### 你今天要重点理解的字段
- `paths`
- `method`
- `operationId`
- `parameters`
- `requestBody`
- `responses`

### 今天要做的动作
1. 读 `petstore.yaml`
2. 手动写出一个接口的结构
3. 再去看 `parser.py`，看看代码是不是在抽这些信息

### 今天最小产出
你自己写一个“Endpoint 长什么样”的伪结构，例如：

```python
Endpoint(
    method="get",
    path="/pets/{petId}",
    operation_id="getPet",
    parameters=[...],
    request_schema={...},
    responses={...},
)
```

### 完成标准
你能说清 `parser.py` 的输入和输出。

---

## Day 5：自己复写 Endpoint 和 parse_openapi

### 今天目标
- 自己动手写一个简化版 OpenAPI 解析器

### 今天要读的文件
- `lang_agent/parser.py`
- `tests/test_parser.py`

### 今天要做的动作
1. 先自己写，不看原文件
2. 定义 `Endpoint`
3. 写一个简版 `parse_openapi`
4. 再和项目现有实现对照

### 你今天最少要写出来的能力
- 读 yaml
- 遍历 `paths`
- 提取 method/path/operationId/responses

### 验收命令
```bash
pytest tests/test_parser.py -q
```

### 完成标准
- 单测通过
- 你知道为什么 parser 要做 fallback（例如 prance 依赖问题时还能读 yaml）

### 常见错误
- 忘记处理 `requestBody`
- 忘记处理 `parameters`
- 把 `responses` 读丢了

---

## Day 6：场景构建器，理解为什么不能只按单接口生成测试

### 今天目标
- 理解 Scenario 的作用
- 自己能写一个简化版 `build_scenarios`

### 今天要读的文件
- `lang_agent/scenario_builder.py`

### 为什么这一步重要
因为接口自动化不是只测一个 GET，而是测试“先创建、再查询、再更新、再删除”的链路。

### 今天要做的动作
1. 看 `Scenario` 数据结构
2. 理解 resource 是怎么来的
3. 理解同一资源下多个接口为什么要组合成 CRUD 场景

### 今天最小产出
你要能解释这三个概念：
- Endpoint：单个接口
- Scenario：一组接口组成的测试场景
- Resource：这些接口属于哪个资源

### 完成标准
你能回答：

> 为什么不能只根据 operationId 一股脑生成 test 文件？

标准答案方向：
- 因为很多接口有依赖
- 没有前置数据会 404
- 场景化更接近真实业务链路

---

## Day 7：生成分层测试工程骨架

### 今天目标
- 理解“分层 pytest 工程”到底指什么
- 自己写出 scaffold 逻辑

### 今天要读的文件
- `lang_agent/chains/generation_chain.py`
- `generated_tests/` 当前目录结构

### 今天重点理解的目录
```text
generated_tests/
├── api/
├── config/
├── data/
├── reports/
├── testcases/
├── utils/
├── conftest.py
└── pytest.ini
```

### 为什么这样分层
- `api/`：接口动作封装
- `testcases/`：测试逻辑
- `utils/`：公共工具
- `data/`：测试数据
- `config/`：生成工程自己的配置
- `conftest.py`：fixture
- `pytest.ini`：pytest 规则

### 今天要做的动作
1. 看 `_scaffold_files`
2. 看它写了哪些公共文件
3. 自己手写一个最小 scaffold

### 完成标准
你能自己回答：

> 为什么用例里不应该直接写 requests，而要经过 api 层？

---

# 第2周：把“生成结果能真正跑起来”

这一周重点是：  
不只是生成目录，而是生成出来的东西要能执行。

---

## Day 8：理解 `api/` 层是怎么生成的

### 今天目标
- 明白接口封装层的价值
- 理解 `pets_api.py` 这种文件是怎么来的

### 今天要读的文件
- `generated_tests/api/pets_api.py`
- `lang_agent/chains/generation_chain.py`

### 今天重点理解
为什么要生成：
- `create_pet(...)`
- `get_pet(...)`
- `update_pet(...)`
- `delete_pet(...)`
- `list_pets(...)`

### 今天完成标准
你能讲清楚：

> `api/` 层的作用不是“多写一层代码”，而是为了让 testcases 更干净、后续更好维护。

---

## Day 9：理解 `utils/` 层和 `conftest.py`

### 今天目标
- 知道 fixture 是怎么给测试注入公共能力的
- 知道 utils 为什么要拆出来

### 今天要读的文件
- `generated_tests/utils/http_client.py`
- `generated_tests/utils/assertions.py`
- `generated_tests/utils/data_loader.py`
- `generated_tests/conftest.py`

### 今天要理解
- `base_url`
- `request_session`
- `load_resource_data`
- `assert_response_ok`

### 完成标准
你能说出：
- `conftest.py` 负责什么
- `utils/` 负责什么
- 为什么不能把这些逻辑全塞进测试文件

---

## Day 10：理解测试用例模板是怎么生成的

### 今天目标
- 明白生成出来的 `test_pets_crud.py` 为什么能跑

### 今天要读的文件
- `generated_tests/testcases/test_pets_crud.py`
- `generated_tests/testcases/test_pets_get_pet.py`
- `lang_agent/chains/generation_chain.py`

### 今天重点理解
- 为什么 GET/PUT/DELETE 之前有时需要 bootstrap create
- 为什么要自动造唯一 name/title
- 为什么 path_params 要动态更新

### 完成标准
你能自己解释：

> 为什么单独测 get_pet 时，不能假设 petId=1 一定存在？

---

## Day 11：让生成出来的测试真正跑一次

### 今天目标
- 自己完成一次“启动 mock -> 跑 generated_tests”

### 今天要做的动作
1. 启动 mock
2. 运行 pytest
3. 看测试通过

### 参考命令
```bash
python mock_api_server.py
python -m pytest generated_tests -q
```

### 完成标准
- 你知道“生成”和“执行”是两件不同的事
- 你知道为什么 mock 没开时会报 localhost:8000 连接失败

---

## Day 12：写 pytest 执行器

### 今天目标
- 让程序自己跑 pytest，而不是靠人手动观察终端

### 今天要读的文件
- `lang_agent/executor.py`

### 今天要理解
- 为什么用 `--json-report`
- 为什么要提取 `nodeid/file/call_longrepr`

### 完成标准
你能说清 executor 的输入输出：
- 输入：test_path、pytest_args、report_path
- 输出：exit_code、stdout、stderr、failures

---

## Day 13：统一报告结构

### 今天目标
- 知道为什么 app 和 cli 都读同一份报告

### 今天要读的文件
- `lang_agent/report.py`
- `.cache/latest_run_report.json`

### 今天要理解
报告至少要包含：
- 是否通过
- 修复轮次
- 停止原因
- 当前失败文件
- 修复历史

### 完成标准
你能解释为什么“没有统一报告结构，UI 和 CLI 会各写各的，非常乱”。

---

## Day 14：把 Generate 流程完整串起来

### 今天目标
- 知道 `run_generate` 到底干了什么

### 今天要读的文件
- `lang_agent/graph/runner.py`
- `lang_agent/graph/nodes.py`

### 今天要理解
Generate 图大致就是：
- parse_openapi
- build_scenarios
- generate_tests
- final_report

### 完成标准
你能用一句话讲清：

> run_generate 不是“直接写文件”，而是通过图把解析、场景构建、生成和报告串起来。

---

# 第3周：进入“失败闭环、自愈、产品化”

这一周是项目最有亮点的部分。

---

## Day 15：理解失败分类为什么是自愈前提

### 今天目标
- 知道为什么不是所有失败都该让 LLM 修

### 今天要读的文件
- `lang_agent/chains/diagnosis_chain.py`
- `lang_agent/chains/prompts.py`

### 今天重点理解三类错误
- `code_bug`
- `api_bug`
- `env_bug`

### 今天完成标准
你能解释：

> 为什么“服务没启动”不应该交给 LLM 去修测试代码？

---

## Day 16：理解修复链怎么工作

### 今天目标
- 知道 repair chain 输入什么、输出什么

### 今天要读的文件
- `lang_agent/chains/repair_chain.py`
- `lang_agent/chains/prompts.py`

### 今天重点理解
修复输入：
- 原始失败文件
- 错误日志
- 错误类型
- 错误摘要
- few-shot 历史修复示例

修复输出：
- 修复后的完整文件内容

### 完成标准
你能回答：

> 为什么修复链输出的是完整文件，而不是 patch 片段？

---

## Day 17：理解短期记忆

### 今天目标
- 知道短期记忆为什么能省钱、省时间

### 今天要读的文件
- `lang_agent/memory/short_memory.py`

### 今天要理解
key 设计：
- `current_file::error_signature`

### 完成标准
你能解释：

> 为什么同一个文件、同一个错误签名，第二次没必要再问大模型？

---

## Day 18：理解长期记忆和 ChromaDB

### 今天目标
- 明白长期记忆为什么只保存“验证通过”的修复

### 今天要读的文件
- `lang_agent/memory/long_memory.py`
- `lang_agent/memory/retriever.py`
- `tests/test_long_memory.py`

### 今天要重点理解
- 为什么要 `validated=True`
- 为什么 retrieval 需要 `error_type` 和 `error_signature`
- 为什么 DeepSeek-only 场景下要允许 embedding 降级

### 完成标准
你能解释：

> 如果把错误修复也写进长期记忆，会发生什么问题？

---

## Day 19：理解 Heal 图如何串起整个闭环

### 今天目标
- 明白自愈并不是一个函数，而是一张状态图

### 今天要读的文件
- `lang_agent/graph/nodes.py`
- `lang_agent/graph/router.py`
- `lang_agent/graph/state.py`

### 今天要理解的节点顺序
- run_tests
- collect_failures
- pick_failure
- classify_failure
- lookup_short_memory
- retrieve_long_memory
- repair_code
- apply_fix
- retest
- persist_memory
- final_report

### 完成标准
你能画出一张简单流程图。

---

## Day 20：CLI 和 Streamlit 为什么都要做

### 今天目标
- 理解“工程能力”和“产品展示能力”的区别

### 今天要读的文件
- `cli.py`
- `app.py`

### 今天要理解
- CLI 适合自动化、批处理、面试演示命令
- Streamlit 适合演示产品体验和闭环状态

### 今天完成标准
你能解释：

> 为什么一个作品集项目只有脚本还不够，还需要 CLI 或看板？

---

## Day 21：最终复写验收 + 面试讲法整理

### 今天目标
- 你不只是“做过”，还要“讲得清楚”

### 最终你要能完成的 5 件事

#### 1. 启动 mock 服务
```bash
python mock_api_server.py
```

#### 2. 生成测试工程
```bash
python cli.py generate -i data/petstore.yaml -o generated_tests
```

#### 3. 跑 pytest
```bash
python -m pytest generated_tests -q
```

#### 4. 运行 heal
```bash
python cli.py heal -t generated_tests
```

#### 5. 启动 Streamlit
```bash
python -m streamlit run app.py
```

### 面试时你至少要会讲这 4 点
- 我解决了什么问题
- 为什么先做生成链路，再做自愈链路
- 为什么要短期记忆 + 长期记忆
- 为什么要做 CLI + Streamlit 两种入口

### Day 21 完成标准
你能独立回答这句话：

> 如果让你从空项目重新做一遍，你会按什么顺序做，为什么？

---

## 五、你每天学习时固定使用的 6 步方法

以后你每天都按这个节奏学，会非常稳：

### 第1步：先看“今天学什么”
- 不要一上来就敲代码
- 先知道今天的目标

### 第2步：先读真实文件
- 不是看教程，而是看仓库里的真实实现

### 第3步：自己先讲一遍
- 用自己的话解释输入、输出、作用

### 第4步：再写一个简化版
- 不要求一模一样，但要自己动手写

### 第5步：一定要运行
- pytest
- cli
- streamlit
- mock

### 第6步：写复盘
每天写这 3 句话：
- 今天这个模块输入是什么
- 输出是什么
- 如果失败，一般会卡在哪

---

## 六、你复写过程中最容易踩的坑

### 1. mock 没开
现象：
- localhost:8000 连接失败

本质：
- 不是测试生成错了，是服务没启动

### 2. 把生成结果当成项目源码
现象：
- 盯着 `generated_tests/` 看半天，以为那是项目核心

本质：
- 那只是生成结果，不是生成器本体

### 3. 一上来就做自愈
现象：
- prompt、LLM、记忆、图编排全部缠在一起

本质：
- 应该先做 generate，再做 heal

### 4. 不区分 code_bug 和 env_bug
现象：
- 服务没开也让 LLM 修测试代码

本质：
- 方向错了

### 5. 长期记忆乱写
现象：
- 只要有修复结果就往记忆库里塞

本质：
- 错误修复会污染后续 few-shot

---

## 七、如果你要我“每天带你学”，我们怎么配合最好

你后面每天只需要这样发我：

```text
今天学 Day X
我已经看了：
1.
2.
3.

我不懂的点是：
1.
2.

我跑命令的结果是：
...
```

我会按下面的方式带你：
- 先用人话解释
- 再告诉你今天真正该看哪几行
- 再告诉你今天最值得自己敲哪一小段
- 最后给你一个当天的“验收题”

---

## 八、你现在最适合怎么开始

不要一下看完 21 天再开始。  
你现在最适合这样做：

1. 先做 Day 1
2. 把结果发我
3. 我继续带你做 Day 2

如果你愿意，我下一条就直接开始正式带你学：

**Day 1 第一课：这个项目到底在解决什么问题，项目里每个目录分别是什么。**

