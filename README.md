# API Test Agent（LangChain 版）

这个项目从 OpenAPI/Swagger 文档自动生成 pytest 测试，并在失败时进行三轮以内的自动修复（仅限 code_bug），支持短期记忆与可选的长期记忆（ChromaDB）。

## 快速开始

1. 安装依赖

```bash
python -m pip install -r requirements.txt
```

2. 配置环境变量

复制 `.env.example` 为 `.env`。

如果你使用 `DeepSeek API`，推荐直接这样配置：

```env
OPENAI_API_KEY=your_deepseek_api_key
OPENAI_BASE_URL=https://api.deepseek.com
```

默认模型已配置为 `deepseek-chat`。

说明：

- 本项目的聊天模型通过 `langchain_openai.ChatOpenAI` 走 OpenAI 兼容协议接入 `DeepSeek`
- 如果你只配置 `DeepSeek`，长期记忆中的向量检索会自动降级为 no-op，不影响生成和修复主流程
- 如果你还想启用长期记忆检索，可额外配置一个支持 embedding 的服务：`EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL`、`EMBEDDING_MODEL`

3. 生成测试

```bash
python cli.py generate -i data/petstore.yaml -o generated_tests
```

4. 执行并自动修复（最多 3 轮）

```bash
python cli.py heal -t generated_tests
```

## 项目结构

- lang_agent/：核心逻辑（解析、场景、链、执行器、记忆、流程编排）
- generated_tests/：自动生成的 pytest 用例输出目录
- data/：示例 OpenAPI 文档
