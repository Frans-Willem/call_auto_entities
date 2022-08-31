# call\_auto\_entities
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
This will create or update an old-style group with entity id group.inside\_lights, and all lights that are not in the garden.

### Update a new-style (helpers defined) group
```
service: call_auto_entities.update_group
data:
	entity_id: light.inside_lights_group
	includes:
		- domain: light
	excludes:
		- area: Garden # Exclude any outside lights
		- integration: group # Exclude existing groups
```
This will update a new-style (e.g. helpers) group with entity id light.inside\_lights\_group, and all lights that are not in the garden and are not already a group.

