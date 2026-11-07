"""An address listed twice is one tag."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.s7.config_flow import split_tags
from custom_components.s7.const import CONF_HOST, CONF_PORT, CONF_RACK, CONF_SLOT, CONF_TAGS, DOMAIN


async def _setup(hass: HomeAssistant, port: int, tags: list[str], **options) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1", CONF_RACK: 0, CONF_SLOT: 0, CONF_PORT: port, CONF_TAGS: tags},
        options=options,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_saved_duplicate_still_sets_up(hass: HomeAssistant, s7_server) -> None:
    entry = await _setup(hass, s7_server[1], ["DB1.DBD0:REAL", "DB1.DBW4:INT", "DB1.DBD0:REAL"])
    assert entry.state is ConfigEntryState.LOADED
    assert hass.data[DOMAIN][entry.entry_id].data == {"DB1.DBD0:REAL": 23.5, "DB1.DBW4:INT": 42}
    await hass.config_entries.async_unload(entry.entry_id)


def test_split_tags_drops_repeats_and_keeps_order() -> None:
    assert split_tags("DB1,R0\nM0.0; DB1,R0\n") == ["DB1,R0", "M0.0"]
