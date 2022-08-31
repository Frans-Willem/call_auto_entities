# call_auto_entities
Home Assistant integration to call services with a filtered list of entities, with a filter syntax equivalent to the popular lovelace auto entities plugin.

## Examples
### Update or create an old-style group
```
service: call_auto_entities.with_array
data:
	service: group.set
	data:
		object_id: inside_lights
		name: Inside lights
	array_key: entities
	includes:
		- domain: light
	excludes:
		- area: Garden
```
### Update a new-style (helpers defined) group
```
service: call_auto_entities.update_group
data:
	entity_id: light.inside_lights_group
	includes:
		- domain: light
	excludes:
		- area: Garden
		- entity_id: light.inside_lights_group
```
