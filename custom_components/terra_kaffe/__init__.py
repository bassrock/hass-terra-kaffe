"""The Terra Kaffe integration."""

from __future__ import annotations

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .api import TerraKaffeAPI, TerraKaffeAPIError, TerraKaffeAuthError
from .const import CONF_REFRESH_TOKEN, DOMAIN, LOGGER
from .coordinator import TerraKaffeConfigEntry, TerraKaffeDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: TerraKaffeConfigEntry) -> bool:
    """Set up Terra Kaffe from a config entry."""
    api = TerraKaffeAPI(hass)

    # Try to use refresh token first, fall back to username/password
    refresh_token = entry.data.get(CONF_REFRESH_TOKEN)
    if refresh_token:
        api.set_tokens(access_token="", refresh_token=refresh_token)
        try:
            token_data = await api.async_refresh_access_token()
            # Update the stored refresh token if it changed
            if token_data.get("refresh_token") != refresh_token:
                hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_REFRESH_TOKEN: api.refresh_token},
                )
        except TerraKaffeAuthError:
            LOGGER.debug("Refresh token expired, trying username/password")
            refresh_token = None

    if not refresh_token:
        # Fall back to username/password authentication
        username = entry.data.get(CONF_USERNAME)
        password = entry.data.get(CONF_PASSWORD)
        if not username or not password:
            raise ConfigEntryAuthFailed("No valid authentication credentials")
        try:
            await api.async_login(username, password)
            # Update the refresh token
            hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, CONF_REFRESH_TOKEN: api.refresh_token},
            )
        except TerraKaffeAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except TerraKaffeAPIError as err:
            raise ConfigEntryNotReady(f"Failed to connect: {err}") from err

    # Test connection
    try:
        if not await api.async_test_connection():
            raise ConfigEntryNotReady("Failed to verify API connection")
    except TerraKaffeAuthError as err:
        raise ConfigEntryAuthFailed("Authentication failed") from err
    except TerraKaffeAPIError as err:
        raise ConfigEntryNotReady(f"Failed to connect: {err}") from err

    # Create coordinator
    coordinator = TerraKaffeDataUpdateCoordinator(hass, entry, api)
    entry.runtime_data = coordinator

    # Perform initial refresh
    await coordinator.async_config_entry_first_refresh()

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TerraKaffeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
