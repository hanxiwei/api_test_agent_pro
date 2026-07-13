from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import streamlit as st

from lang_agent.config import load_settings
from lang_agent.graph.runner import run_generate, run_heal
from lang_agent.report import load_run_report


st.set_page_config(page_title="API Test Agent", layout="wide")


def _inject_style() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(153, 196, 255, 0.18), transparent 28%),
                radial-gradient(circle at top right, rgba(255, 189, 214, 0.22), transparent 24%),
                linear-gradient(180deg, #f7f8fc 0%, #f3f0ff 100%);
        }
        .hero-card, .panel-card {
            background: rgba(255, 255, 255, 0.78);
            border: 1px solid rgba(126, 87, 194, 0.14);
            border-radius: 20px;
            box-shadow: 0 14px 40px rgba(48, 43, 99, 0.08);
            padding: 1.2rem 1.35rem;
            backdrop-filter: blur(10px);
        }
        .hero-title {
            font-size: 2rem;
            font-weight: 700;
            color: #251a46;
            margin-bottom: 0.35rem;
        }
        .hero-subtitle {
            color: #5b5573;
            line-height: 1.7;
            font-size: 0.98rem;
        }
        .badge-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin-top: 0.9rem;
        }
        .badge {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.28rem 0.72rem;
            background: rgba(108, 99, 255, 0.08);
            color: #4c3fb0;
            font-size: 0.82rem;
            font-weight: 600;
        }
        .section-title {
            font-size: 1.08rem;
            font-weight: 700;
            color: #2f2652;
            margin-bottom: 0.7rem;
        }
        .mini-note {
            color: #6a6485;
            font-size: 0.9rem;
            line-height: 1.65;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _build_overrides(base_url: str, enable_long_memory: bool, model_name: str, max_rounds: int) -> dict[str, Any]:
    overrides: dict[str, Any] = {
        "heal": {"max_rounds": int(max_rounds)},
        "memory": {"enable_long_memory": enable_long_memory},
    }
    if base_url.strip():
        overrides["base_url"] = base_url.strip()
    if model_name.strip():
        overrides.setdefault("model", {})["name"] = model_name.strip()
    return overrides


def _resolve_openapi_path(source_mode: str, uploaded: Any, local_path: str) -> str | None:
    if source_mode == "上传文件":
        if uploaded is None:
            return None
        suffix = Path(uploaded.name).suffix or ".yaml"
        with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded.getvalue())
            return tmp.name

    value = local_path.strip()
    if not value:
        return None
    path = Path(value)
    if not path.exists():
        st.error(f"OpenAPI 文件不存在：{path}")
        return None
    return str(path)


def _render_report(report: dict[str, Any], title: str) -> None:
    st.markdown(f"### {title}")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("运行模式", str(report.get("mode", "-")))
    col2.metric("是否通过", "是" if report.get("ok") else "否")
    col3.metric("修复轮次", int(report.get("rounds", 0)))
    col4.metric("失败数量", int(report.get("failures_count", 0)))

    col5, col6, col7 = st.columns(3)
    col5.metric("停止原因", str(report.get("stopped_reason", "-")))
    col6.metric("短期记忆命中", "是" if report.get("short_memory_hit") else "否")
    col7.metric("长期记忆使用", "是" if report.get("long_memory_used") else "否")

    current_file = report.get("current_file")
    if current_file:
        st.caption(f"当前处理文件：`{current_file}`")

    generated_files = report.get("generated_files") or []
    if generated_files:
        with st.expander("生成的测试文件", expanded=False):
            st.code("\n".join(str(x) for x in generated_files), language="text")

    repair_history = report.get("repair_history") or []
    if repair_history:
        st.markdown("#### 修复历史")
        st.dataframe(repair_history, use_container_width=True, hide_index=True)

    handoff_report = report.get("handoff_report")
    if handoff_report:
        st.markdown("#### 人工介入报告")
        st.json(handoff_report)

    final_result = report.get("final_result") or {}
    if final_result:
        with st.expander("运行尾部日志", expanded=False):
            stdout_tail = str(final_result.get("stdout_tail") or "").strip()
            stderr_tail = str(final_result.get("stderr_tail") or "").strip()
            if stdout_tail:
                st.markdown("**stdout**")
                st.code(stdout_tail, language="text")
            if stderr_tail:
                st.markdown("**stderr**")
                st.code(stderr_tail, language="text")
            if not stdout_tail and not stderr_tail:
                st.info("本次没有可展示的尾部日志。")


def _render_latest_summary(report: dict[str, Any] | None) -> None:
    if not report:
        st.info("还没有最近一次运行报告，可以先执行“一键流水线”或“仅生成/仅修复”。")
        return

    _render_report(report, "最近一次运行概览")


_inject_style()

st.markdown(
    """
    <div class="hero-card">
        <div class="hero-title">API Test Agent 控制台</div>
        <div class="hero-subtitle">
            这里把 OpenAPI 生成、pytest 回归、自愈修复和运行报告放到同一块面板里。
            你可以一键跑完整流水线，也可以按需拆分成“仅生成 / 仅修复”两步。
        </div>
        <div class="badge-row">
            <span class="badge">OpenAPI / Swagger</span>
            <span class="badge">LangChain + LangGraph</span>
            <span class="badge">Pytest 执行与自愈</span>
            <span class="badge">短期记忆 / ChromaDB</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")

if "last_action_report" not in st.session_state:
    st.session_state.last_action_report = None
if "last_generated_files" not in st.session_state:
    st.session_state.last_generated_files = []

with st.sidebar:
    st.markdown("## 运行配置")
    config_path = st.text_input("config 路径", value="config.yaml")
    base_url = st.text_input("base_url（覆盖 config.yaml）", value="")
    model_name = st.text_input("模型名称（覆盖 config.yaml）", value="")
    enable_long_memory = st.checkbox("启用长期记忆（ChromaDB）", value=False)
    max_rounds = st.slider("最大修复轮次", min_value=1, max_value=10, value=3)
    st.markdown("---")
    st.markdown(
        """
        <div class="panel-card">
            <div class="section-title">当前建议</div>
            <div class="mini-note">
                真实修复验收时，先启动本地 mock API，再让 heal 处理生成测试目录。
                如果使用 DeepSeek，只要 .env 中已经配置好兼容的 OpenAI 变量即可。
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

source_col, path_col = st.columns([1.15, 1.85])
with source_col:
    source_mode = st.radio("OpenAPI 输入方式", ["上传文件", "本地路径"], horizontal=True)
with path_col:
    local_openapi_path = st.text_input(
        "本地 OpenAPI 路径",
        value="data/petstore.yaml",
        disabled=source_mode != "本地路径",
    )

uploaded = st.file_uploader("上传 OpenAPI 文件（yaml / yml / json）", type=["yaml", "yml", "json"])

row1, row2 = st.columns(2)
with row1:
    output_dir = st.text_input("测试输出目录", value="generated_tests")
with row2:
    tests_dir = st.text_input("待执行 tests 目录", value="generated_tests")

tab_run, tab_report, tab_about = st.tabs(["运行面板", "最近报告", "项目说明"])

with tab_run:
    st.markdown(
        """
        <div class="panel-card">
            <div class="section-title">流水线操作</div>
            <div class="mini-note">
                一键流水线：OpenAPI → Generate pytest → 执行 pytest → 失败则自动自愈（最多 3 轮）→ 输出报告。<br/>
                你也可以按需只生成测试，或只对已有 tests 目录执行自愈。
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")

    btn_col1, btn_col2, btn_col3 = st.columns(3)

    with btn_col1:
        if st.button("一键流水线", use_container_width=True):
            openapi_path = _resolve_openapi_path(source_mode, uploaded, local_openapi_path)
            if openapi_path is None:
                st.warning("请先上传 OpenAPI 文件，或填写一个存在的本地路径。")
            else:
                with st.spinner("正在执行流水线：生成测试 → 执行 pytest → 自愈修复..."):
                    settings = load_settings(
                        config_path,
                        overrides=_build_overrides(base_url, enable_long_memory, model_name, max_rounds),
                    )
                    files = run_generate(settings=settings, openapi_path=openapi_path, output_dir=output_dir)
                    report = run_heal(settings=settings, tests_path=Path(output_dir))
                st.session_state.last_generated_files = [str(x) for x in files]
                report_dict = report.to_dict()
                report_dict["generated_files"] = st.session_state.last_generated_files
                st.session_state.last_action_report = report_dict
                if report.ok:
                    st.success("流水线执行完成。")
                else:
                    st.warning("流水线执行完成，但仍有待处理问题。")

    with btn_col2:
        if st.button("仅生成测试", use_container_width=True):
            openapi_path = _resolve_openapi_path(source_mode, uploaded, local_openapi_path)
            if openapi_path is None:
                st.warning("请先上传 OpenAPI 文件，或填写一个存在的本地路径。")
            else:
                with st.spinner("正在生成 pytest 测试文件..."):
                    settings = load_settings(
                        config_path,
                        overrides=_build_overrides(base_url, enable_long_memory, model_name, max_rounds),
                    )
                    files = run_generate(settings=settings, openapi_path=openapi_path, output_dir=output_dir)
                st.session_state.last_generated_files = [str(x) for x in files]
                st.session_state.last_action_report = {
                    "mode": "generate",
                    "ok": True,
                    "rounds": 0,
                    "stopped_reason": "generated",
                    "current_file": None,
                    "failures_count": 0,
                    "short_memory_hit": False,
                    "long_memory_used": False,
                    "generated_files": st.session_state.last_generated_files,
                    "repair_history": [],
                    "handoff_report": None,
                    "final_result": {},
                }
                st.success(f"生成完成，共输出 {len(files)} 个测试文件。")

    with btn_col3:
        if st.button("仅对已有 tests 自愈", use_container_width=True):
            with st.spinner("正在执行 pytest 与自愈修复流程..."):
                settings = load_settings(
                    config_path,
                    overrides=_build_overrides(base_url, enable_long_memory, model_name, max_rounds),
                )
                report = run_heal(settings=settings, tests_path=Path(tests_dir))
            st.session_state.last_action_report = report.to_dict()
            if report.ok:
                st.success("自愈执行完成。")
            else:
                st.warning("自愈执行完成，但仍有待处理问题。")

    st.write("")
    if st.button("刷新最近报告", use_container_width=True):
        st.session_state.last_action_report = load_run_report()
        st.success("最近报告已刷新。")

    action_report = st.session_state.last_action_report
    if action_report is not None:
        _render_report(action_report, "当前操作结果")
    elif st.session_state.last_generated_files:
        st.info("最近一次生成文件已缓存，可以直接切到“最近报告”查看全量结果。")

with tab_report:
    latest = load_run_report()
    _render_latest_summary(latest)

with tab_about:
    st.markdown(
        """
        <div class="panel-card">
            <div class="section-title">项目能力地图</div>
            <div class="mini-note">
                1. 解析 OpenAPI / Swagger，构建 CRUD 场景并生成 pytest。<br/>
                2. 运行 pytest，捕获错误堆栈、失败片段与日志。<br/>
                3. 使用 LangChain + LangGraph 编排诊断、修复、回归与记忆写入。<br/>
                4. 仅把回归通过的修复结果写入记忆，避免污染长期知识库。
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    st.markdown("#### 当前配置预览")
    preview = {
        "config_path": config_path,
        "base_url": base_url or "(使用 config.yaml)",
        "model_name": model_name or "(使用 config.yaml)",
        "enable_long_memory": enable_long_memory,
        "max_rounds": max_rounds,
        "output_dir": output_dir,
        "tests_dir": tests_dir,
    }
    st.code(json.dumps(preview, ensure_ascii=False, indent=2), language="json")
