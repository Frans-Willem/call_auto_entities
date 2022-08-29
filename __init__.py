from __future__ import annotations
import logging
import json
import re

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.typing import ConfigType

DOMAIN = "with_auto_entities"
_LOGGER = logging.getLogger(__name__)

def match(pattern, value):
    if isinstance(pattern, str) and pattern.startswith("$$"):
        pattern = pattern[2:]
        value = json.dumps(value)
    if isinstance(value, str) and isinstance(pattern, str):
        if (pattern.startswith("/") and pattern.endswith("/")) or "*" in pattern:
            if not pattern.startswith("/"):
                pattern = pattern.replace(".", "\\.").replace("*",".*")
                pattern = "^" + pattern+ "$"
            else:
                pattern = pattern[1:-1]
            return (re.search(pattern, value) is not None)

    if isinstance(pattern, str):
        if pattern.startswith("<="):
            return float(value) <= float(pattern[2:])
        if pattern.startswith(">="):
            return float(value) >= float(pattern[2:])
        if pattern.startswith("<"):
            return float(value) < float(pattern[1:])
        if pattern.startswith(">"):
            return float(value) > float(pattern[1:])
        if pattern.startswith("!"):
            return not float(value) == float(pattern[1:])
        if pattern.startswith("="):
            return float(value) == float(pattern[1:])

    return pattern == value

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:

    @callback
    def call_array(call: ServiceCall) -> None:
        _LOGGER.warning('with_auto_entities.call_array called!')
        entities = [state.entity_id for state in hass.states.async_all()]
        _LOGGER.warning(f'All entities: {entities}')

    hass.services.async_register(DOMAIN, "call_array", call_array)
    return True
