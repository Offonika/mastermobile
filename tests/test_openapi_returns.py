"""Contract-level tests guarding the returns listing contract."""

from pathlib import Path
from typing import Any

import yaml

from apps.mw.src.db.models import ReturnStatus


def _load_openapi() -> dict[str, Any]:
    spec_path = Path("openapi.yaml")
    loaded = yaml.safe_load(spec_path.read_text())
    assert isinstance(loaded, dict)
    return loaded


def test_returns_status_parameter_matches_domain_enum() -> None:
    """Ensure the query parameter reuses the canonical return status values."""

    spec = _load_openapi()
    components = spec["components"]
    assert isinstance(components, dict)
    parameters = components["parameters"]
    assert isinstance(parameters, dict)
    status_param = parameters["ReturnStatus"]
    assert isinstance(status_param, dict)
    schema = status_param["schema"]
    assert isinstance(schema, dict)
    param_values = schema["enum"]
    assert isinstance(param_values, list)

    expected_values = sorted(status.value for status in ReturnStatus)

    assert sorted(param_values) == expected_values


def test_returns_status_parameter_is_used_by_list_endpoint() -> None:
    """The list endpoint must expose the reusable status filter."""

    spec = _load_openapi()
    paths = spec["paths"]
    assert isinstance(paths, dict)
    returns_path = paths["/api/v1/returns"]
    assert isinstance(returns_path, dict)
    get_operation = returns_path["get"]
    assert isinstance(get_operation, dict)
    parameters = get_operation["parameters"]
    assert isinstance(parameters, list)
    assert any(
        isinstance(parameter, dict) and parameter.get("$ref") == "#/components/parameters/ReturnStatus"
        for parameter in parameters
    ), "GET /api/v1/returns must reference the shared ReturnStatus query parameter"


def test_returns_status_schema_matches_query_parameter() -> None:
    """The response payload must follow the same enum as the query filter."""

    spec = _load_openapi()
    components = spec["components"]
    assert isinstance(components, dict)
    schemas = components["schemas"]
    assert isinstance(schemas, dict)
    return_schema = schemas["Return"]
    assert isinstance(return_schema, dict)
    properties = return_schema["properties"]
    assert isinstance(properties, dict)
    status_property = properties["status"]
    assert isinstance(status_property, dict)
    schema_values = status_property["enum"]
    assert isinstance(schema_values, list)

    expected_values = sorted(status.value for status in ReturnStatus)

    assert sorted(schema_values) == expected_values
