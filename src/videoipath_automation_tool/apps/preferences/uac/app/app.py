from __future__ import annotations

import logging

from videoipath_automation_tool.apps.preferences.uac.api import UacAPI
from videoipath_automation_tool.apps.preferences.uac.app.read import UacReadMixin
from videoipath_automation_tool.apps.preferences.uac.app.write import UacWriteMixin
from videoipath_automation_tool.apps.preferences.uac.snapshot import UacSnapshot
from videoipath_automation_tool.connector.vip_connector import VideoIPathConnector


class UacApp(UacReadMixin, UacWriteMixin):
    """User-facing UAC API with lazy reads and revision-safe writes."""

    def __init__(
        self,
        vip_connector: VideoIPathConnector,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or logging.getLogger("videoipath_automation_tool_uac_app")
        self._uac_api = UacAPI(vip_connector=vip_connector, logger=self._logger)
        self._snapshot: UacSnapshot | None = None
        self._logger.debug("UAC app initialized.")


__all__ = ["UacApp"]
