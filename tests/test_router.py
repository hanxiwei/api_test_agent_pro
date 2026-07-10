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

