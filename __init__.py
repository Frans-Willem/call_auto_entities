from __future__ import annotations
import logging
import json
import re

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.typing import ConfigType
from homeassistant import helpers

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

def create_group_filter(group_name):
    def filter(hass, entity_state):
        group = hass.states.get(group_name)
        if not group:
            return False
        group_members = group.attributes.get("entity_id")
        if not isinstance(group_members, list):
            return False
        return entity_state.entity_id in group_members
    return filter

def combine_filters_and(filters):
    def filter_fn(hass, entity_state):
        for current_filter_fn in filters:
            if not current_filter_fn(hass, entity_state):
                return False
        return True
    return filter_fn

def combine_filters_or(filters):
    def filter_fn(hass, entity_state):
        for current_filter_fn in filters:
            if current_filter_fn(hass, entity_state):
                return True
        return False
    return filter_fn

def create_attribute_filter(attribute_keys, pattern):
    def filter_fn(hass, entity_state):
        value = entity_state.attributes
        for key in attribute_keys:
            if isinstance(value, dict):
                value = dict.get(key)
            elif isinstance(value, list):
                value = value[int(key)]
            else:
                value = None
        if value is None:
            return False
        return match(pattern, value)
    return filter_fn

def create_attributes_filter(attributes):
    # Assume attributes is a dict
    current_filters = []

    for attribute_name, attribute_pattern in attributes.items():
        attribute_name = attribute_name.split(" ")[0] # Drop suffixes
        attribute_names = attribute_name.split(":")
        current_filters.append(create_attribute_filter(attribute_names, attribute_pattern))

    return combine_filters_and(current_filters)

def create_filter_from_dictionary(d):
    current_filters = []

    for filter_name, pattern in d.items():
        current_filters.append(filter_constructors.get(filter_name)(pattern))

    return combine_filters_and(current_filters)

def create_not_filter(pattern):
    current_filter_fn = create_filter_from_dictionary(pattern)
    def filter_fn(hass, entity_state):
        return not current_filter_fn(hass, entity_state)
    return filter_fn

def create_or_filter(patterns: [dict]):
    current_filters = []
    for pattern in patterns:
        current_filters.append(create_filter_from_dictionary(pattern))

    return combine_filters_or(current_filters)

def get_entity_from_state(hass, entity_state):
    entity_registry = helpers.entity_registry.async_get(hass)
    return entity_registry.async_get(entity_state.entity_id)

def get_device_from_device_id(hass, device_id):
    device_registry = helpers.device_registry.async_get(hass)
    return device_registry.async_get(device_id)

def get_area_from_area_id(hass, area_id):
    area_registry = helpers.area_registry.async_get(hass)
    return area_registry.async_get(area_id)

def get_device_from_state(hass, entity_state):
    entity = get_entity_from_state(hass, entity_state)
    if not entity or entity.device_id is None:
        return None
    return get_device_from_device_id(hass, entity.device_id)

def get_area_from_state(hass, entity_state):
    entity = get_entity_from_state(hass, entity_state)
    if not entity:
        return False
    if not entity.area_id is None:
        area = get_area_from_area_id(hass, entity.area_id)
        if not area is None:
            return area
    if entity.device_id is None:
        return None
    device = get_device_from_device_id(entity.device_id)
    if device is None or device.area_id is None:
        return None
    return get_area_from_area_id(hass, device.area_id)

def create_device_filter(device_filter_fn):
    def filter_fn(hass, entity_state):
        device = get_device_from_state(hass, entity_state)
        if not device:
            return False
        return device_filter_fn(hass, device)
    return filter_fn

def create_area_filter(area_filter_fn):
    def filter_fn(hass, entity_state):
        area = get_area_from_state(hass, entity_state)
        if area is None:
            return False
        return area_filter_fn(hass, area)
    return filter_fn

def create_entity_filter(entity_filter_fn):
    def filter_fn(hass, entity_state):
        entity = get_entity_from_state(hass, entity_state)
        if entity is None:
            return False
        return entity_filter_fn(hass, entity)
    return filter_fn


filter_constructors = {
        "options": lambda pattern: lambda hass, entity_state: True,
        "sort": lambda pattern: lambda hass, entity_state: True,
        "domain": lambda pattern: lambda hass,  entity_state: match(pattern, entity_state.entity_id.split(".")[0]),
        "entity_id": lambda pattern: lambda hass, entity_state: match(pattern, entity_state.entity_id),
        "state": lambda pattern: lambda hass, entity_state: match(pattern, entity_state.state),
        "name": lambda pattern: lambda hass, entity_state: match(pattern, entity_state.attributes.get("friendly_name")),
        "group": create_group_filter,
        "attributes": create_attributes_filter,
        "not": create_not_filter,
        "or": create_or_filter,
        "device": create_device_filter(lambda hass, device: (match(pattern, device.name_by_user) or match(pattern, device.name))),
        "device_manufacturer": create_device_filter(lambda hass, device: match(pattern, device.manufacturer)),
        "device_model": create_device_filter(lambda hass, device: match(pattern, device.model)),
        "area": create_area_filter(lambda hass, area: (match(pattern, area.name) or match(pattern, area.area_id))),
        "entity_category": create_entity_filter(lambda hass, entity: match(pattern, entity.entity_category)),
        # Skipping last_changed, last_updated, last_triggered, hate these
        "integration": create_entity_filter(lambda hass, entity: match(pattern, entity.platform)),
}

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    @callback
    def call_array(call: ServiceCall) -> None:
        _LOGGER.warning('with_auto_entities.call_array called!')
        entities = []
        # Build up list of entities using includes
        for include in call.data.get("includes", []):
            filter_fn = create_filter_from_dictionary(include)
            include_entities = [entity_state for entity_state in hass.states.async_all() if filter_fn(hass, entity_state)]
            entities = entities + include_entities
        # Remove using excludes
        for exclude in call.data.get("excludes", []):
            filter_fn = create_filter_from_dictionary(exclude)
            entities = [entity_state for entity_state in entities if not filter_fn(hass, entity_state)]
        _LOGGER.warning(f'All entities: {[entity.entity_id for entity in entities]}')

    hass.services.async_register(DOMAIN, "call_array", call_array)
    return True
