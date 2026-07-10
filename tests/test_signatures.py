from lang_agent.signatures import extract_error_signature, extract_error_type


def test_extract_error_type_and_signature():
    log = """
E   AssertionError: assert 500 < 500
E    +  where 500 = <Response [500]>.status_code
"""
    assert extract_error_type(log) == "AssertionError"
    sig = extract_error_signature(log)
    assert "status_code" in sig
