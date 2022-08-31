import re
import json
import logging
from typing import List, Dict, Callable, TypedDict, Optional

from homeassistant.helpers.entity_registry import RegistryEntry as EntityEntry
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.device_registry import DeviceRegistry, DeviceEntry
from homeassistant.helpers.area_registry import AreaRegistry, AreaEntry
from homeassistant.core import HomeAssistant, State
from homeassistant import helpers

_LOGGER = logging.getLogger(__name__)

Pattern = object
FilterFn = Callable[[HomeAssistant, State], bool]
EntityFilterFn = Callable[[HomeAssistant, EntityEntry], bool]
DeviceFilterFn = Callable[[HomeAssistant, DeviceEntry], bool]
AreaFilterFn = Callable[[HomeAssistant, AreaEntry], bool]
FilterFnBuilder = Callable[[object], FilterFn]

def match(pattern: Pattern, value: object) -> bool:
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

    if isinstance(pattern, str) and (isinstance(value, str) or isinstance(value, float)or isinstance(value, int)):
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

    if pattern == value:
        return True
    return False

def empty_filter_fn(hass: HomeAssistant, entity_state: State) -> bool:
    return True

def create_group_filter(group_pattern: object) -> FilterFn:
    if not isinstance(group_pattern, str):
        _LOGGER.error("group filter should have string type")
        return empty_filter_fn
    group_name : str = group_pattern

    def filter(hass: HomeAssistant, entity_state: State) -> bool:
        group : Optional[State] = hass.states.get(group_pattern)
        if not group:
            return False
        group_members = group.attributes.get("entity_id")
        if not isinstance(group_members, list):
            return False
        return entity_state.entity_id in group_members
    return filter

def combine_filters_and(filters: List[FilterFn]) -> FilterFn:
    def filter_fn(hass: HomeAssistant, entity_state: State) -> bool:
        for current_filter_fn in filters:
            if not current_filter_fn(hass, entity_state):
                return False
        return True
    return filter_fn

def combine_filters_or(filters: List[FilterFn]) -> FilterFn:
    def filter_fn(hass: HomeAssistant, entity_state: State) -> bool:
        for current_filter_fn in filters:
            if current_filter_fn(hass, entity_state):
                return True
        return False
    return filter_fn

def create_attribute_filter(attribute_keys: List[str], pattern: Pattern) -> FilterFn:
    def filter_fn(hass: HomeAssistant, entity_state: State) -> bool:
        value = entity_state.attributes
        for key in attribute_keys:
            if isinstance(value, dict):
                value = value.get(key)
            elif isinstance(value, list):
                value = value[int(key)]
            else:
                value = None
        if value is None:
            return False
        return match(pattern, value)
    return filter_fn

def create_attributes_filter(attributes_pattern: object) -> FilterFn:
    if not isinstance(attributes_pattern, dict):
        _LOGGER.error("attributes filter should have object type")
        return empty_filter_fn

    # Assume attributes is a dict
    current_filters = []

    for attribute_name, attribute_pattern in attributes_pattern.items():
        if not isinstance(attribute_name, str):
            _LOGGER.error("attributes filter keys should have string type")
            continue
        attribute_name = attribute_name.split(" ")[0] # Drop suffixes
        attribute_names : List[str] = attribute_name.split(":")
        current_filters.append(create_attribute_filter(attribute_names, attribute_pattern))

    return combine_filters_and(current_filters)

def create_filter_from_dictionary(d: Dict[str, object]) -> FilterFn:
    current_filters = []

    for filter_name, pattern in d.items():
        filter_constructor = filter_constructors.get(filter_name)
        if filter_constructor is None:
            _LOGGER.error(f"No filter with name '{filter_name}' available")
            continue
        current_filters.append(filter_constructor(pattern))

    return combine_filters_and(current_filters)

def create_not_filter(pattern: object) -> FilterFn:
    if not isinstance(pattern, dict) or not all(isinstance(key, str) for key in pattern.keys()):
        _LOGGER.error("not filter should have object argument")
        return empty_filter_fn
    # TODO: More checking to see if all keys are indeed strings ?
    current_filter_fn = create_filter_from_dictionary(pattern)
    def filter_fn(hass: HomeAssistant, entity_state: State) -> bool:
        return not current_filter_fn(hass, entity_state)
    return filter_fn

def create_or_filter(patterns: object) -> FilterFn:
    if not isinstance(patterns, list):
        _LOGGER.error("or filter should have list argument")
        return empty_filter_fn

    current_filters = []
    for pattern in patterns:
        if not isinstance(pattern, dict) or not all(isinstance(key, str) for key in pattern.keys()):
            _LOGGER.error("or filter should have list argument of objects")
            continue
        current_filters.append(create_filter_from_dictionary(pattern))

    return combine_filters_or(current_filters)

def get_entity_from_state(hass: HomeAssistant, entity_state: State) -> Optional[EntityEntry]:
    entity_registry : EntityRegistry = helpers.entity_registry.async_get(hass)
    entity : EntityEntry | None = entity_registry.async_get(entity_state.entity_id)
    return entity

def get_device_from_device_id(hass: HomeAssistant, device_id: str) -> Optional[DeviceEntry]:
    device_registry : DeviceRegistry = helpers.device_registry.async_get(hass)
    device : DeviceEntry | None = device_registry.async_get(device_id)
    return device

def get_area_from_area_id(hass: HomeAssistant, area_id: str) -> Optional[AreaEntry]:
    area_registry : AreaRegistry = helpers.area_registry.async_get(hass)
    area : AreaEntry | None = area_registry.async_get_area(area_id)
    return area

def get_device_from_state(hass: HomeAssistant, entity_state: State) -> Optional[DeviceEntry]:
    entity = get_entity_from_state(hass, entity_state)
    if not entity or entity.device_id is None:
        return None
    return get_device_from_device_id(hass, entity.device_id)

def get_area_from_state(hass: HomeAssistant, entity_state: State) -> Optional[AreaEntry]:
    entity = get_entity_from_state(hass, entity_state)
    if not entity:
        return None
    if not entity.area_id is None:
        area = get_area_from_area_id(hass, entity.area_id)
        if not area is None:
            return area
    if entity.device_id is None:
        return None
    device = get_device_from_device_id(hass, entity.device_id)
    if device is None or device.area_id is None:
        return None
    return get_area_from_area_id(hass, device.area_id)

def create_device_filter(device_filter_fn: DeviceFilterFn) -> FilterFn:
    def filter_fn(hass: HomeAssistant, entity_state: State) -> bool:
        device = get_device_from_state(hass, entity_state)
        if not device:
            return False
        return device_filter_fn(hass, device)
    return filter_fn

def create_area_filter(area_filter_fn: AreaFilterFn) -> FilterFn:
    def filter_fn(hass: HomeAssistant, entity_state: State) -> bool:
        area = get_area_from_state(hass, entity_state)
        if area is None:
            return False
        return area_filter_fn(hass, area)
    return filter_fn

def create_entity_filter(entity_filter_fn: EntityFilterFn) -> FilterFn:
    def filter_fn(hass: HomeAssistant, entity_state: State) -> bool:
        entity = get_entity_from_state(hass, entity_state)
        if entity is None:
            return False
        return entity_filter_fn(hass, entity)
    return filter_fn



filter_constructors : Dict[str, FilterFnBuilder] = {
        #"options": lambda pattern: lambda hass, entity_state: True,
        #"sort": lambda pattern: lambda hass, entity_state: True,
        "domain": lambda pattern: lambda hass,  entity_state: match(pattern, entity_state.entity_id.split(".")[0]),
        "entity_id": lambda pattern: lambda hass, entity_state: match(pattern, entity_state.entity_id),
        "state": lambda pattern: lambda hass, entity_state: match(pattern, entity_state.state),
        "name": lambda pattern: lambda hass, entity_state: match(pattern, entity_state.attributes.get("friendly_name")),
        "group": create_group_filter,
        "attributes": create_attributes_filter,
        "not": create_not_filter,
        "or": create_or_filter,
        "device": lambda pattern: create_device_filter(lambda hass, device: (match(pattern, device.name_by_user) or match(pattern, device.name))),
        "device_manufacturer": lambda pattern: create_device_filter(lambda hass, device: match(pattern, device.manufacturer)),
        "device_model": lambda pattern: create_device_filter(lambda hass, device: match(pattern, device.model)),
        "area": lambda pattern: create_area_filter(lambda hass, area: (match(pattern, area.name) or match(pattern, area.id))),
        "entity_category": lambda pattern: create_entity_filter(lambda hass, entity: match(pattern, entity.entity_category)),
        # Skipping last_changed, last_updated, last_triggered, hate these
        "integration": lambda pattern: create_entity_filter(lambda hass, entity: match(pattern, entity.platform)),
}
