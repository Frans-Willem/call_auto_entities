from homeassistant import config_entries
from homeassistant import data_entry_flow
from .const import CONF_NAME, DOMAIN
from typing import Any, Dict

@config_entries.HANDLERS.register(DOMAIN)
class CallAutoEntitiesFlowHandler(config_entries.ConfigFlow):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self) -> None:
        pass

    async def async_step_user(self, user_input: Dict[str, Any] | None = None) -> data_entry_flow.FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if self.hass.data.get(DOMAIN):
            return self.async_abort(reason="single_instance_allowed")
        return self.async_create_entry(title=CONF_NAME,
                                       data={},
                                       )
