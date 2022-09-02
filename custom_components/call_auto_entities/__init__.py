from __future__ import annotations
import logging
import json
import re
from typing import List, Dict

from homeassistant.core import HomeAssistant, ServiceCall, callback, State
from homeassistant.helpers.typing import ConfigType
from .const import DOMAIN, SERVICE_WITH_ARRAY, SERVICE_UPDATE_GROUP
from .filters import create_filter_from_dictionary
from homeassistant.helpers.entity_registry import RegistryEntry as EntityEntry
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant import helpers
from homeassistant.config_entries import ConfigEntry, ConfigEntries

_LOGGER = logging.getLogger(__name__)

def async_find_entities(hass: HomeAssistant, includes: List[Dict[str, object]], excludes: List[Dict[str, object]]) -> List[State]:
        entities : List[State] = []
        # Build up list of entities using includes
        for include in includes:
            filter_fn = create_filter_from_dictionary(include)
            include_entities = [entity_state for entity_state in hass.states.async_all() if filter_fn(hass, entity_state)]
            entities = entities + include_entities
        # Remove using excludes
        for exclude in excludes:
            filter_fn = create_filter_from_dictionary(exclude)
            entities = [entity_state for entity_state in entities if not filter_fn(hass, entity_state)]
        return entities

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    @callback
    async def with_array(call: ServiceCall) -> None:
        # Build up data for service call
        call_data = call.data.get("data", {})
        call_domain, call_service = call.data.get("service").split(".",1)
        call_array_key = call.data.get("array_key", "entity_id")
        entities : List[State] = async_find_entities(hass, call.data.get("includes", []), call.data.get("excludes", []))
        call_data[call_array_key] = [entity.entity_id for entity in entities]

        _LOGGER.info(f'Calling {call_domain} {call_service} with {call_data}')

        await hass.services.async_call(call_domain, call_service, call_data)

    async def update_group(call: ServiceCall) -> None:
        entity_registry : EntityRegistry = helpers.entity_registry.async_get(hass)
        group_entity_id = call.data.get("entity_id")
        entity : EntityEntry | None = entity_registry.async_get(group_entity_id)
        if entity is None:
            _LOGGER.error(f"No group entity found with name '{group_entity_id}'")
            return
        config_entry_id = entity.config_entry_id
        if config_entry_id is None:
            _LOGGER.error(f"No config entry associated with '{group_entity_id}'")
            return

        config_entry : ConfigEntry = hass.config_entries.async_get_entry(config_entry_id)
        if config_entry_id is None:
            _LOGGER.error(f"Config entry for '{group_entity_id}' not found")
            return

        if config_entry.domain != "group":
            _LOGGER.error(f"'{group_entity_id}' is not a group")
            return

        new_options = config_entry.options.copy()
        filtered_entities = async_find_entities(hass, call.data.get("includes", []), call.data.get("excludes", []))
        new_options['entities'] = [entity.entity_id for entity in filtered_entities]

        hass.config_entries.async_update_entry(config_entry, options=new_options)
        _LOGGER.info(f"'{group_entity_id}' updated with members: {new_options['entities']}")

    hass.services.async_register(DOMAIN, SERVICE_WITH_ARRAY, with_array)
    hass.services.async_register(DOMAIN, SERVICE_UPDATE_GROUP, update_group)
    return True
