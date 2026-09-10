from lang_agent.graph.router import (
    route_after_classification,
    route_after_retest,
    route_after_short_memory,
    route_after_test_run,
)


def test_route_after_test_run():
    assert route_after_test_run({"last_exit_code": 0, "failed_tests": []}) == "passed"
    assert route_after_test_run({"last_exit_code": 1, "failed_tests": [{"file": "a.py"}]}) == "failed"
    assert route_after_test_run({"last_exit_code": 1, "failed_tests": []}) == "errored"


def test_route_after_classification():
    assert route_after_classification({"error_category": "code_bug"}) == "code_bug"
    assert route_after_classification({"error_category": "api_bug"}) == "api_bug"
    assert route_after_classification({"error_category": "env_bug"}) == "env_bug"
    assert route_after_classification({"error_category": "other"}) == "unknown"


def test_route_after_short_memory():
    assert route_after_short_memory({"short_memory_hit": True}) == "hit"
    assert route_after_short_memory({"short_memory_hit": False}) == "miss"


def test_route_after_retest():
    assert route_after_retest({"last_exit_code": 0, "failed_tests": [], "repair_round": 1, "max_rounds": 3}) == "passed"
    assert route_after_retest({"last_exit_code": 1, "failed_tests": [{"file": "x"}], "repair_round": 1, "max_rounds": 3}) == "retry"
    assert route_after_retest({"last_exit_code": 1, "failed_tests": [{"file": "x"}], "repair_round": 3, "max_rounds": 3}) == "handoff"


def test_route_after_classification_confidence_gate():
    # 没给置信度时按旧逻辑放行（兼容性）
    assert route_after_classification({"error_category": "code_bug"}) == "code_bug"
    # 高置信度 code_bug 正常走修复链
    assert route_after_classification({"error_category": "code_bug", "diagnosis_confidence": 0.9}) == "code_bug"
    assert route_after_classification({"error_category": "code_bug", "diagnosis_confidence": 0.7}) == "code_bug"
    # 低置信度 code_bug 直接 handoff，避免误修
    assert route_after_classification({"error_category": "code_bug", "diagnosis_confidence": 0.69}) == "handoff"
    assert route_after_classification({"error_category": "code_bug", "diagnosis_confidence": 0.0}) == "handoff"
    # api_bug / env_bug 不管置信度都是原分类
    assert route_after_classification({"error_category": "api_bug", "diagnosis_confidence": 0.0}) == "api_bug"
    assert route_after_classification({"error_category": "env_bug", "diagnosis_confidence": 0.1}) == "env_bug"
    # 非法/缺失 confidence 的 code_bug 不被 handoff 误伤（类型容错）
    assert route_after_classification({"error_category": "code_bug", "diagnosis_confidence": "not-a-float"}) == "code_bug"

