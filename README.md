# API Test Agent Pro

一个面向测开 / SDET 的工具：从 OpenAPI/Swagger 文档自动生成分层 pytest 接口自动化工程，执行失败后进入自动自愈闭环（最多 3 轮、仅对 code_bug 修复）。支持短期记忆（同错复用、0 LLM 调用）与可选的长期记忆（ChromaDB，validated-only）。

## 能力概览

- OpenAPI/Swagger 解析：从 YAML/JSON 提取接口信息，构建 Endpoint 列表
- 场景构建：按资源聚合接口，生成 CRUD 场景（Scenario）
- 分层工程生成：输出 `api/ testcases/ utils/ data/ config/ reports/ + conftest.py + pytest.ini`
- pytest 执行与失败收集：封装执行器并解析 `pytest-json-report`
- 自愈闭环：失败分类 → 短期/长期记忆检索 → LLM 重写失败测试文件 → 回归验证
- 入口与展示：Click CLI + Streamlit 看板（一键流水线）
- 可复现实验环境：内置 `mock_api_server.py` + `data/petstore.yaml`

## 快速开始

### 0) 准备环境

- Python：3.10+（推荐）
- Windows / macOS / Linux 均可

### 1) 安装依赖

```bash
python -m pip install -r requirements.txt
```

### 2) 启动本地 mock 服务（推荐先做）

本项目默认用 `data/petstore.yaml` 演示，测试请求的 `base_url` 期望为 `http://localhost:8000`。先把 mock 启动起来，后面所有命令都能稳定验收：

```bash
python mock_api_server.py
```

验证 mock 正常：

```bash
python -c "import requests; print(requests.get('http://127.0.0.1:8000/pets').status_code)"
```

### 3) 配置环境变量（可选但推荐）

复制 `.env.example` 为 `.env`。

如果你使用 `DeepSeek API`（OpenAI 兼容协议），推荐直接这样配置：

```env
OPENAI_API_KEY=your_deepseek_api_key
OPENAI_BASE_URL=https://api.deepseek.com
```

默认模型已配置为 `deepseek-v4-pro`。

说明（和当前实现保持一致）：

- 本项目的聊天模型通过 `langchain_openai.ChatOpenAI` 走 OpenAI 兼容协议接入 `DeepSeek`
- 如果你只配置 `DeepSeek`，长期记忆中的向量检索会自动降级为 no-op，不影响生成和修复主流程（仍可写入/按元数据兜底检索）
- 如果你还想启用长期记忆检索，可额外配置一个支持 embedding 的服务：`EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL`、`EMBEDDING_MODEL`

### 4) 生成分层测试工程

```bash
python cli.py generate -i data/petstore.yaml -o generated_tests
```

生成完成后，你会得到类似结构（示意）：

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

### 5) 执行 pytest（只执行，不修复）

```bash
python -m pytest generated_tests -q
```

### 6) 执行并自动修复（最多 3 轮）

当且仅当 pytest 失败且被识别为 `code_bug` 时，才会进入修复循环：

```bash
python cli.py heal -t generated_tests
```

## 项目结构

### 核心源码

- `lang_agent/`：核心逻辑（解析、场景、生成链、自愈链、执行器、记忆、LangGraph 编排）
- `cli.py`：Click 命令行入口（generate/heal/report）
- `app.py`：Streamlit 看板入口（一键流水线 / 仅生成 / 仅自愈 / 最近报告）
- `mock_api_server.py`：本地可复现 mock 后端（用于验收闭环）
- `data/`：示例 OpenAPI 文档（默认 `petstore.yaml`）
- `tests/`：本项目自身的单元测试（不是生成的接口测试）

### 自动生成产物

- `generated_tests/`：自动生成的分层 pytest 工程（建议不提交 Git，随时可删后重生成）
- `.cache/`：运行报告与短期记忆缓存（可删）
- `.chroma_acceptance/`：长期记忆验收用 Chroma 数据（可删）

## CLI 用法

### 生成

```bash
python cli.py generate -i data/petstore.yaml -o generated_tests
```

### 自愈

```bash
python cli.py heal -t generated_tests
```

### 查看最近一次报告

```bash
python cli.py report
```

## Streamlit 看板

```bash
python -m streamlit run app.py
```

打开页面后建议用：

- 一键流水线：OpenAPI → Generate → pytest →（失败则 heal）→ 报告

## 常见问题（Troubleshooting）

### 1) 无法连接到 localhost:8000 / 目标计算机拒绝连接

原因：mock 服务或你的真实后端没有启动。  
处理：

- 先运行 `python mock_api_server.py`
- 或把 `config.yaml` / Streamlit 侧边栏的 `base_url` 改成你的真实服务地址

### 2) invalid_api_key / 401

原因：`OPENAI_API_KEY` 未配置或不正确。  
处理：检查 `.env` 中的 `OPENAI_API_KEY` 与 `OPENAI_BASE_URL`，并确认模型名称配置正确。

### 3) 生成物里出现老的平铺 test_xxx.py

原因：你本地残留了旧的 `generated_tests/` 产物。  
处理：删除整个 `generated_tests/` 后重新 generate。

## 开发者验证

运行项目自测：

```bash
pytest tests -q
```
