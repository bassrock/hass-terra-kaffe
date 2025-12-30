"""API for Terra Kaffe Afero platform."""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import logging
from typing import Any

import aiohttp
from aiohttp import ClientError, ClientSession, ClientTimeout
from aiohttp.client_exceptions import ClientConnectorError, ClientResponseError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import AFERO_CLIENT_ID, AFERO_SERVICE_URL, AFERO_TOKEN_URL

_LOGGER = logging.getLogger(__name__)


class TerraKaffeAPIError(Exception):
    """Base exception for Terra Kaffe API errors."""


class TerraKaffeAuthError(TerraKaffeAPIError):
    """Authentication error."""


class TerraKaffeAPI:
    """Afero API client for Terra Kaffe."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: ClientSession | None = None,
    ) -> None:
        """Initialize the API client."""
        self.hass = hass
        self._session = session or async_get_clientsession(hass)
        self._base_url = AFERO_SERVICE_URL
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expiry: datetime | None = None
        self._account_id: str | None = None
        # Set timeout for API requests (30 seconds total, 10 seconds connect)
        self._timeout = ClientTimeout(total=30, connect=10)

    def set_tokens(
        self,
        access_token: str,
        refresh_token: str | None = None,
        expires_in: int | None = None,
    ) -> None:
        """Set the authentication tokens."""
        self._access_token = access_token
        if refresh_token:
            self._refresh_token = refresh_token
        if expires_in:
            self._token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)

    @property
    def refresh_token(self) -> str | None:
        """Return the refresh token."""
        return self._refresh_token

    @property
    def _headers(self) -> dict[str, str]:
        """Return default headers for API requests."""
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def async_login(self, username: str, password: str) -> dict[str, Any]:
        """Authenticate with username and password using Afero OAuth.

        Uses the Resource Owner Password Credentials (ROPC) flow directly
        with Afero's OAuth server to get tokens that work with the device API.
        """
        try:
            # Use direct Afero OAuth login (ROPC flow)
            data = {
                "grant_type": "password",
                "client_id": AFERO_CLIENT_ID,
                "username": username,
                "password": password,
            }
            _LOGGER.debug("Attempting login to: %s", AFERO_TOKEN_URL)
            _LOGGER.debug(
                "Login data (username masked): username=%s",
                username[:3] + "***" if len(username) > 3 else "***",
            )
            async with self._session.post(
                AFERO_TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self._timeout,
            ) as response:
                _LOGGER.debug(
                    "Login response status: %s, headers: %s",
                    response.status,
                    dict(response.headers),
                )

                # Handle response
                if response.status == 200:
                    # Success - extract token from OAuth response
                    token_data = await response.json()
                    access_token = token_data.get("access_token")
                    refresh_token = token_data.get("refresh_token")
                    expires_in = token_data.get("expires_in")

                    if not access_token:
                        raise TerraKaffeAPIError("No access token in login response")

                    self.set_tokens(
                        access_token=access_token,
                        refresh_token=refresh_token,
                        expires_in=expires_in,
                    )
                    _LOGGER.debug("Login successful, token set")

                    # Fetch account ID from /v1/users/me endpoint
                    await self._fetch_account_id()

                    return token_data
                if response.status == 401:
                    # Try to get error details from response body
                    text = await response.text()
                    error_desc = "Invalid email or password"
                    if text:
                        try:
                            error_data = json.loads(text)
                            error_desc = error_data.get(
                                "error_description",
                                error_data.get("error", error_desc),
                            )
                            _LOGGER.debug("Auth error details: %s", error_data)
                        except (ValueError, json.JSONDecodeError):
                            pass
                    _LOGGER.error(
                        "Authentication failed with 401 (Unauthorized), "
                        "please verify your credentials are correct"
                    )
                    raise TerraKaffeAuthError(error_desc)
                if response.status == 400:
                    error_msg = "Authentication failed"
                    try:
                        error_data = await response.json()
                        error_msg = error_data.get(
                            "error_description",
                            error_data.get("error", error_msg),
                        )
                        _LOGGER.debug("Auth error (400): %s", error_data)
                    except (ValueError, json.JSONDecodeError):
                        text = await response.text()
                        _LOGGER.error("Failed to parse 400 error: %s", text[:200])
                    raise TerraKaffeAuthError(error_msg)
                # Unexpected status
                text = await response.text()
                _LOGGER.error(
                    "Unexpected login response status %s: %s",
                    response.status,
                    text[:200],
                )
                response.raise_for_status()
        except ClientConnectorError as err:
            _LOGGER.error("Failed to connect to Afero API: %s", err)
            raise TerraKaffeAPIError(
                f"Unable to connect to Afero API at {AFERO_TOKEN_URL}. "
                "Please check your internet connection and try again."
            ) from err
        except aiohttp.ServerTimeoutError as err:
            _LOGGER.error("Timeout connecting to Afero API: %s", err)
            raise TerraKaffeAPIError(
                "Connection to Afero API timed out. "
                "The service may be temporarily unavailable."
            ) from err
        except ClientResponseError as err:
            if err.status in (401, 403):
                raise TerraKaffeAuthError("Invalid credentials") from err
            _LOGGER.error("API error during login: %s (status: %s)", err, err.status)
            raise TerraKaffeAPIError(f"Authentication failed: {err}") from err
        except ClientError as err:
            _LOGGER.error("Connection error during login: %s", err)
            raise TerraKaffeAPIError(f"Connection error: {err}") from err

        # Should not reach here, but return empty dict for type safety
        return {}

    async def _fetch_account_id(self) -> None:
        """Fetch the account ID from /v1/users/me endpoint."""
        try:
            async with self._session.get(
                f"{self._base_url}/v1/users/me",
                headers=self._headers,
                timeout=self._timeout,
            ) as response:
                if response.status == 200:
                    user_data = await response.json()
                    account_access = user_data.get("accountAccess", [])
                    if account_access:
                        self._account_id = account_access[0]["account"]["accountId"]
                        _LOGGER.debug(
                            "Fetched account ID from API: %s", self._account_id
                        )
                else:
                    _LOGGER.warning(
                        "Failed to fetch account ID: status %s", response.status
                    )
        except (ClientError, TimeoutError) as e:
            _LOGGER.warning("Failed to fetch account ID: %s", e)

    async def async_refresh_access_token(self) -> dict[str, Any]:
        """Refresh the access token using the refresh token."""
        if not self._refresh_token:
            raise TerraKaffeAuthError("No refresh token available")

        try:
            data = {
                "grant_type": "refresh_token",
                "client_id": AFERO_CLIENT_ID,
                "refresh_token": self._refresh_token,
            }
            async with self._session.post(
                AFERO_TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self._timeout,
            ) as response:
                if response.status in (400, 401):
                    raise TerraKaffeAuthError("Refresh token expired")
                response.raise_for_status()
                token_data = await response.json()

                self.set_tokens(
                    access_token=token_data["access_token"],
                    refresh_token=token_data.get("refresh_token", self._refresh_token),
                    expires_in=token_data.get("expires_in"),
                )
                return token_data
        except ClientConnectorError as err:
            _LOGGER.error(
                "Failed to connect to Afero API during token refresh: %s", err
            )
            raise TerraKaffeAPIError(
                f"Unable to connect to Afero API at {AFERO_TOKEN_URL}. "
                "Please check your internet connection and try again."
            ) from err
        except aiohttp.ServerTimeoutError as err:
            _LOGGER.error(
                "Timeout connecting to Afero API during token refresh: %s", err
            )
            raise TerraKaffeAPIError(
                "Connection to Afero API timed out. "
                "The service may be temporarily unavailable."
            ) from err
        except ClientResponseError as err:
            if err.status in (400, 401):
                raise TerraKaffeAuthError("Refresh token expired") from err
            _LOGGER.error(
                "API error during token refresh: %s (status: %s)", err, err.status
            )
            raise TerraKaffeAPIError(f"Token refresh failed: {err}") from err
        except ClientError as err:
            _LOGGER.error("Connection error during token refresh: %s", err)
            raise TerraKaffeAPIError(f"Connection error: {err}") from err

    async def _ensure_token_valid(self) -> None:
        """Ensure the access token is valid, refreshing if needed."""
        if self._token_expiry and datetime.now() >= self._token_expiry:
            await self.async_refresh_access_token()

    async def async_get_accounts(self) -> list[dict[str, Any]]:
        """Get user accounts.

        Uses the /v1/users/me endpoint to get account information.
        """
        await self._ensure_token_valid()

        # If we don't have an account ID yet, fetch it
        if not self._account_id:
            await self._fetch_account_id()

        if self._account_id:
            # Return the account ID in the expected format
            return [{"accountId": self._account_id, "id": self._account_id}]

        # If we still don't have an account ID, raise an error
        raise TerraKaffeAPIError(
            "Failed to retrieve account information. Please try re-authenticating."
        )

    async def async_get_devices(self, account_id: str) -> list[dict[str, Any]]:
        """Get devices for an account."""
        await self._ensure_token_valid()
        try:
            async with self._session.get(
                f"{self._base_url}/v1/accounts/{account_id}/devices",
                headers=self._headers,
                params={"expansions": "state,attributes,timezone,tags"},
                timeout=self._timeout,
            ) as response:
                response.raise_for_status()
                data = await response.json()
                # Handle different response formats
                if isinstance(data, list):
                    return data
                return data.get("items", data.get("devices", []))
        except ClientConnectorError as err:
            _LOGGER.error("Failed to connect to Terra Kaffe API: %s", err)
            raise TerraKaffeAPIError(
                f"Unable to connect to Terra Kaffe API at {self._base_url}. "
                f"Please check your internet connection and try again."
            ) from err
        except aiohttp.ServerTimeoutError as err:
            _LOGGER.error("Timeout connecting to Terra Kaffe API: %s", err)
            raise TerraKaffeAPIError(
                "Connection to Terra Kaffe API timed out. "
                "The service may be temporarily unavailable."
            ) from err
        except ClientResponseError as err:
            if err.status == 401:
                raise TerraKaffeAuthError("Invalid access token") from err
            _LOGGER.error("API error getting devices: %s (status: %s)", err, err.status)
            raise TerraKaffeAPIError(f"Failed to get devices: {err}") from err
        except ClientError as err:
            _LOGGER.error("Connection error getting devices: %s", err)
            raise TerraKaffeAPIError(f"Connection error: {err}") from err

    async def async_get_device_state(
        self, account_id: str, device_id: str
    ) -> dict[str, Any]:
        """Get device state/attributes."""
        await self._ensure_token_valid()
        try:
            async with self._session.get(
                f"{self._base_url}/v1/accounts/{account_id}/devices/{device_id}",
                headers=self._headers,
                params={"expansions": "state,attributes,extendedData"},
                timeout=self._timeout,
            ) as response:
                response.raise_for_status()
                return await response.json()
        except ClientConnectorError as err:
            _LOGGER.error("Failed to connect to Terra Kaffe API: %s", err)
            raise TerraKaffeAPIError(
                f"Unable to connect to Terra Kaffe API at {self._base_url}. "
                f"Please check your internet connection and try again."
            ) from err
        except aiohttp.ServerTimeoutError as err:
            _LOGGER.error("Timeout connecting to Terra Kaffe API: %s", err)
            raise TerraKaffeAPIError(
                "Connection to Terra Kaffe API timed out. "
                "The service may be temporarily unavailable."
            ) from err
        except ClientResponseError as err:
            if err.status == 401:
                raise TerraKaffeAuthError("Invalid access token") from err
            _LOGGER.error(
                "API error getting device state: %s (status: %s)", err, err.status
            )
            raise TerraKaffeAPIError(f"Failed to get device state: {err}") from err
        except ClientError as err:
            _LOGGER.error("Connection error getting device state: %s", err)
            raise TerraKaffeAPIError(f"Connection error: {err}") from err

    async def async_set_attribute(
        self,
        account_id: str,
        device_id: str,
        attribute_id: int,
        value: Any,
    ) -> None:
        """Set a device attribute."""
        await self._ensure_token_valid()
        try:
            # Afero uses a request/response pattern for attribute writes
            # API expects values as strings (even for numeric attributes)
            # Based on network capture, attribute values are always strings
            # The request must include a "type" field: "attribute_write" for writes
            send_value = str(value)

            request_body = [
                {"type": "attribute_write", "attrId": attribute_id, "value": send_value}
            ]
            _LOGGER.debug(
                "Setting attribute %s to value %s (type: %s) on device %s",
                attribute_id,
                send_value,
                type(send_value).__name__,
                device_id,
            )
            async with self._session.post(
                f"{self._base_url}/v1/accounts/{account_id}/devices/{device_id}/requests",
                headers=self._headers,
                json=request_body,
                timeout=self._timeout,
            ) as response:
                if response.status >= 400:
                    # Capture error details before raising
                    error_msg = f"Failed to set attribute {attribute_id}"
                    try:
                        text = await response.text()
                        if text:
                            try:
                                error_data = json.loads(text)
                                error_msg = error_data.get(
                                    "message",
                                    error_data.get("error", error_msg),
                                )
                                _LOGGER.error("API error response: %s", error_data)
                            except (ValueError, json.JSONDecodeError):
                                _LOGGER.error(
                                    "API error response (text): %s", text[:500]
                                )
                                error_msg = f"{error_msg}: {text[:500]}"
                    except (aiohttp.ClientError, TimeoutError) as e:
                        _LOGGER.debug("Error reading response: %s", e)
                    _LOGGER.error(
                        "API error setting attribute %s: %s (status: %s)",
                        attribute_id,
                        error_msg,
                        response.status,
                    )
                    raise TerraKaffeAPIError(error_msg)
                _LOGGER.debug("Successfully set attribute %s", attribute_id)
        except ClientConnectorError as err:
            _LOGGER.error("Failed to connect to Terra Kaffe API: %s", err)
            raise TerraKaffeAPIError(
                f"Unable to connect to Terra Kaffe API at {self._base_url}. "
                "Please check your internet connection and try again."
            ) from err
        except aiohttp.ServerTimeoutError as err:
            _LOGGER.error("Timeout connecting to Terra Kaffe API: %s", err)
            raise TerraKaffeAPIError(
                "Connection to Terra Kaffe API timed out. "
                "The service may be temporarily unavailable."
            ) from err
        except ClientResponseError as err:
            if err.status == 401:
                raise TerraKaffeAuthError("Invalid access token") from err
            # Error should have been handled above, but catch any edge cases
            _LOGGER.error(
                "API error setting attribute: %s (status: %s)", err, err.status
            )
            raise TerraKaffeAPIError(
                f"Failed to set attribute {attribute_id}: {err}"
            ) from err
        except ClientError as err:
            _LOGGER.error("Connection error setting attribute: %s", err)
            raise TerraKaffeAPIError(f"Connection error: {err}") from err

    async def async_test_connection(self) -> bool:
        """Test the API connection."""
        try:
            await self.async_get_accounts()
        except TerraKaffeAPIError:
            return False
        else:
            return True
