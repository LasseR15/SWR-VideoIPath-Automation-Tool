import logging
import re
import urllib.parse
import uuid
from typing import Any

from typing_extensions import deprecated

from videoipath_automation_tool.utils.cross_app_errors import ApiMalformedResponseError, ApiQueryTooLongError
from videoipath_automation_tool.validators.device_id import validate_device_id
from videoipath_automation_tool.validators.virtual_device_id import validate_virtual_device_id

# Characters that are meaningful in the projection grammar and must survive encoding.
# Everything else (spaces, double quotes, ...) is percent-encoded.
_SAFE = "/*,'=()"

# Conservative URI length ceiling (path only).
# The full UI projection from some calls (thousands of chars) triggers HTTP 414 behind the proxy.
MAX_QUERY_LENGTH = 4000

# Base path for all rest api calls
_REST_API_PATH = "/rest/v2"


def format_repr(obj: object, /, **fields: Any) -> str:
    """Return a concise ``ClassName(k=v, ...)`` representation.

    Callable values are evaluated defensively and skipped if evaluation fails.
    ``None`` values are omitted to keep developer-facing representations useful.
    """
    parts: list[str] = []
    for key, value in fields.items():
        if callable(value):
            try:
                value = value()
            except Exception:  # noqa: BLE001, S112
                # Representations must not fail because an optional property is unavailable.
                continue
        if value is not None:
            parts.append(f"{key}={value!r}")
    return f"{type(obj).__name__}({', '.join(parts)})"


def field_diffs(
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, tuple[object, object]]:
    """Return top-level field differences in the same shape used by commit conflicts."""
    diffs: dict[str, tuple[object, object]] = {}
    for key in set(baseline) | set(current):
        before = baseline.get(key)
        after = current.get(key)
        if before != after:
            diffs[key] = (before, after)
    return diffs


# --- Fallback Logger ---
def create_fallback_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.debug(f"No logger provided. Creating fallback logger: '{name}'.")
    return logger


# --- Generate UUID4 ---
def generate_uuid_4():
    return str(uuid.uuid4())


# --- Natural Sort Device ID list ---
def extract_natural_sort_key(s: str):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", s)]


def extract_items_from_rsp(data: dict[str, Any], *path: str) -> list[dict[str, Any]]:
    """Walk ``data`` down ``path`` and return the ``_items`` list (empty if any node is absent)."""
    node: Any = data
    for key in path:
        if not isinstance(node, dict):
            return []
        node = node.get(key)
        if node is None:
            return []
    if isinstance(node, dict):
        items = node.get("_items", [])
        return items if isinstance(items, list) else []
    return []


def extract_required_items_from_rsp(data: dict[str, Any], *path: str) -> list[dict[str, Any]]:
    """Return a required ``_items`` collection or raise for malformed response data."""
    node: Any = data
    traversed: list[str] = []
    for key in path:
        traversed.append(key)
        if not isinstance(node, dict) or key not in node or node[key] is None:
            raise ApiMalformedResponseError(tuple(traversed), "an object")
        node = node[key]
    if not isinstance(node, dict) or not isinstance(node.get("_items"), list):
        raise ApiMalformedResponseError((*path, "_items"), "a list")
    return node["_items"]


def encode_req_path(path: str) -> str:
    """Percent-encode a collector query path, preserving projection-grammar characters and validate length."""
    encoded = urllib.parse.quote(path, safe=_SAFE)
    if len(encoded) > MAX_QUERY_LENGTH:
        raise ApiQueryTooLongError(len(encoded), MAX_QUERY_LENGTH)
    return encoded


def build_req_path_data(path: str) -> str:
    return encode_req_path(_REST_API_PATH + "/data" + path)


def build_req_path_actions(path: str) -> str:
    return encode_req_path(_REST_API_PATH + "/actions" + path)


def extract_header_dict_from_rsp(response: Any) -> dict[str, Any]:
    header = getattr(response, "header", None)
    if header is None:
        return {}
    return header.model_dump(mode="json") if hasattr(header, "model_dump") else dict(header)


def build_post_envelope(response: Any) -> dict[str, Any]:
    """Reassemble a ``{data, header}`` dict from a ResponseV2Post for DTO validation."""
    return {"data": response.data, "header": extract_header_dict_from_rsp(response)}


# --- Deprecated Functions for Device ID Validation ---
# --- Device ID string validation ---
@deprecated("Use 'validate_device_id' from 'videoipath_automation_tool.validators.device_id' instead.")
def _validate_device_id_string(device_id: str) -> bool:
    """Validate the device_id string."""
    try:
        validate_device_id(device_id)
        return True
    except ValueError:
        return False


@deprecated("Use 'validate_virtual_device_id' from 'videoipath_automation_tool.validators.virtual_device_id' instead.")
def _validate_virtual_device_id_string(device_id: str) -> bool:
    """Validate the virtual device_id string."""
    try:
        validate_virtual_device_id(device_id)
        return True
    except ValueError:
        return False


@deprecated(
    "This function is deprecated. Use 'validate_device_id' and 'validate_virtual_device_id' from "
    "'videoipath_automation_tool.validators' instead."
)
def validate_device_id_string(device_id: str, include_virtual: bool = False) -> bool:
    """Validate the device_id string. Optionally include virtual device_id strings."""
    if include_virtual:
        return _validate_device_id_string(device_id) or _validate_virtual_device_id_string(device_id)
    return _validate_device_id_string(device_id)
