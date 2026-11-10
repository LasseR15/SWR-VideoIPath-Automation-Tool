import logging
import re
import urllib.parse
import uuid
from typing import Any

from typing_extensions import deprecated

from videoipath_automation_tool.utils.cross_app_errors import ApiQueryTooLongError
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
