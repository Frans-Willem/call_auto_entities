# call_auto_entities
Home Assistant integration to call services with a filtered list of entities, with a filter syntax equivalent to the popular lovelace auto entities plugin.

## Examples
### Automatically update a group
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
