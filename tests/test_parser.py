from lang_agent.parser import parse_openapi


def test_parse_openapi_petstore():
    endpoints = parse_openapi("data/petstore.yaml")
    assert len(endpoints) >= 4
    methods = {(e.method, e.path) for e in endpoints}
    assert ("get", "/pets") in methods
    assert ("post", "/pets") in methods
    assert ("get", "/pets/{petId}") in methods

