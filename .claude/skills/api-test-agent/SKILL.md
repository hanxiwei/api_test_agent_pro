---
name: api-test-agent
description: |
  API 测试自愈 Agent — 从 OpenAPI/Swagger 文档自动生成分层 pytest 接口自动化工程，
  执行失败后进入自动自愈闭环（最多 3 轮、仅对 code_bug 修复）。
  支持短期记忆（同错复用、0 LLM 调用）与可选的长期记忆（ChromaDB，validated-only）。

  Triggers: API test, OpenAPI, Swagger, pytest generation, test auto-heal, 接口测试, 自动化测试生成, 测试自愈
---

# API Test Agent

基于 LangChain + LangGraph + RAG 的 API 测试自愈 Agent。

## 能力概览

- **生成测试工程**：从 OpenAPI/Swagger YAML/JSON 自动生成分层 pytest 工程
- **执行并自愈**：运行 pytest，对失败用例自动分类、检索记忆、LLM 修复、回归验证
- **报告查看**：查看最近一次运行报告
- **Streamlit 看板**：可视化一键流水线操作

## 前置条件

在执行任何命令前，确认以下环境就绪：

### 1) 依赖安装

```bash
python -m pip install -r requirements.txt
```

### 2) 环境变量（.env）

检查 `.env` 是否配置了 `OPENAI_API_KEY`（项目使用 DeepSeek API，走 OpenAI 兼容协议）：

```env
OPENAI_API_KEY=your_deepseek_api_key
OPENAI_BASE_URL=https://api.deepseek.com
```

### 3) 本地 Mock 服务（验收用）

如果用户没有自己的后端服务，先启动 mock：

```bash
python mock_api_server.py
```

验证 mock 正常：

```bash
python -c "import requests; print(requests.get('http://127.0.0.1:8000/pets').status_code)"
```

## 命令参考

### 生成测试工程

从 OpenAPI 文档生成分层 pytest 工程：

```bash
python cli.py generate -i <openapi_path> -o <output_dir>
```

参数说明：
- `-i / --input`：（必填）OpenAPI/Swagger 文档路径（YAML 或 JSON）
- `-o / --output`：输出目录，默认 `generated_tests`
- `--base-url`：API 服务地址，覆盖 config.yaml 中的配置
- `--model-name`：模型名称，覆盖 config.yaml 中的配置

生成产物结构：

```text
generated_tests/
├── api/          # API 封装层
├── config/       # 配置文件
├── data/         # 测试数据
├── reports/      # 运行报告
├── testcases/    # 测试用例
├── utils/        # 工具函数
├── conftest.py   # pytest 配置
└── pytest.ini    # pytest 设置
```

### 执行并自愈

运行 pytest 并在失败时自动修复（最多 3 轮）：

```bash
python cli.py heal -t <tests_dir>
```

参数说明：
- `-i / --input`：OpenAPI 文档路径（可选，如果提供则先生成再 heal）
- `-t / --tests`：测试工程目录路径
- `-o / --output`：输出目录，默认 `generated_tests`
- `-r / --rounds`：最大修复轮数，覆盖 config.yaml
- `--base-url`：API 服务地址
- `--model-name`：模型名称
- `--enable-long-memory / --disable-long-memory`：启用/禁用 ChromaDB 长期记忆

### 查看最近报告

```bash
python cli.py report
```

### 启动 Streamlit 看板

```bash
python -m streamlit run app.py
```

## 工作流指引

当用户请求以下任务时，按对应流程执行：

### 场景 A：用户要求生成 API 测试

1. 确认 OpenAPI 文档路径（默认 `data/petstore.yaml`）
2. 确认输出目录（默认 `generated_tests`）
3. 确认是否需要先启动 mock 服务
4. 执行 `python cli.py generate -i <openapi_path> -o <output_dir>`
5. 告知用户生成结果和目录结构

### 场景 B：用户要求运行测试并修复

1. 确认测试目录路径
2. 确认 mock 服务或真实后端是否在运行
3. 执行 `python cli.py heal -t <tests_dir>`
4. 解读修复报告，告知用户修复了哪些失败用例

### 场景 C：用户要求查看报告

1. 执行 `python cli.py report`
2. 以易读的方式呈现报告内容

### 场景 D：用户要求启动看板

1. 执行 `python -m streamlit run app.py`
2. 告知用户访问地址（默认 `http://localhost:8501`）

## 注意事项

- 生成的 `generated_tests/` 目录随时可删后重生成，不建议提交 Git
- 短期记忆缓存位于 `.cache/`，可安全删除
- 长期记忆（ChromaDB）默认关闭，需通过 `--enable-long-memory` 或修改 `config.yaml` 启用
- 默认模型为 `deepseek-v4-pro`，可在 `config.yaml` 或命令行覆盖
- 默认 `base_url` 为 `http://localhost:8000`，在 `config.yaml` 中修改或通过命令行覆盖
