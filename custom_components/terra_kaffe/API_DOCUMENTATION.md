# Terra Kaffe API Documentation

This document contains findings from analyzing the Terra Kaffe mobile app API.

## API Architecture

The Terra Kaffe app uses two main APIs:

1. **Afero API** (`api2.gk7qmfrz.afero.net`) - Device control and state management
2. **Terra Kaffe Services API** (`api.terrakaffeservices.com`) - User data, drinks, profiles

## Authentication

### OAuth Token Endpoint
- **URL**: `https://auth1.gk7qmfrz.afero.net/auth/realms/tkf/protocol/openid-connect/token`
- **Method**: `POST`
- **Content-Type**: `application/x-www-form-urlencoded`

### Password Login (Initial Setup)
```
grant_type=password
client_id=tk_android
username=<EMAIL>
password=<PASSWORD>
```

### Token Refresh
```
grant_type=refresh_token
refresh_token=<TOKEN>
```

**Response**:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "expires_in": 120,
  "refresh_expires_in": 1800,
  "token_type": "Bearer"
}
```

**Client IDs**:
- Android: `tk_android`
- iOS: `tk_ios`

## Afero API Endpoints

All endpoints require `Authorization: Bearer <ACCESS_TOKEN>` header.

### Get User Info
- **Endpoint**: `GET /v1/users/me`
- **Base URL**: `https://api2.gk7qmfrz.afero.net`
- **Response**: User info including `accountAccess[0].account.accountId`

### Get Devices
- **Endpoint**: `GET /v1/accounts/{accountId}/devices`
- **Query Params**: `?expansions=state,attributes,timezone,tags,extendedData`
- **Response**: Array of devices with current state and attributes

### Get Single Device
- **Endpoint**: `GET /v1/accounts/{accountId}/devices/{deviceId}`
- **Query Params**: `?expansions=state,attributes,extendedData`
- **Response**: Device with state and attributes

### Get Device Profiles
- **Endpoint**: `GET /v1/accounts/{accountId}/deviceProfiles`
- **Query Params**: `?imageSize=3x&locale=en_US`
- **Response**: Array of device profiles with attribute schemas

### Send Commands (Write Attributes)
- **Endpoint**: `POST /v1/accounts/{accountId}/devices/{deviceId}/requests`
- **Content-Type**: `application/json`
- **Body**:
```json
[{"type": "attribute_write", "attrId": 1, "value": "1"}]
```
- **Response**: `202 Accepted`
```json
[{"status": "SUCCESS", "requestId": 119, "statusCode": 202, "timestampMs": 1767055654276}]
```

**Valid request types**:
- `attribute_read` - Read attribute value
- `attribute_write` - Write attribute value
- `notify_viewing` - Notification viewing

### Get Conclave Access (Real-Time Updates)
- **Endpoint**: `POST /v1/accounts/{accountId}/conclaveAccess`
- **Body**: `{"user": true}`
- **Response**: WebSocket connection info

## Device Profiles

### TK-02 Coffee Machine
- **Profile ID**: `587e0ef9-a173-43d5-8590-ff13f79ec113`
- **Device Type**: `TK-02`
- **Total Attributes**: 112

### Enterprise Hub
- **Profile ID**: `262de6b1-e3b1-11ed-a6fc-42010af5d123`

## TK-02 Attribute Reference

### Core Status Attributes
| ID | Name | Type | R/W | Description |
|----|------|------|-----|-------------|
| 1 | Device Status | SINT8 | RW | 0=Sleep, 1=Wake, 2=Going to Wake, 3=Going to Sleep |
| 2 | Coffee Order | UTF8S | R | Current coffee order |
| 3 | Drink History | UTF8S | RW | Recent drink history |
| 4 | Bean Level | SINT16 | R | Bean hopper level |
| 5 | Waste Bin Level | SINT8 | R | Waste bin fill level |
| 6 | Care Status | SINT32 | RW | Maintenance status bits |
| 7 | Grind Settings | UTF8S | R | Format: "level\|offset" |
| 9 | Maintenance Performed | SINT8 | R | Maintenance status |
| 10 | Drink Order | UTF8S | RW | Send drink order to machine |
| 11 | Drink Order Error | UTF8S | R | Error message |
| 12 | Drink Order Received | UTF8S | R | Order confirmation |
| 13 | Brewing Status | SINT8 | RW | 0=Ready, 1=Brewing, 2=Pre-warmup, 3=Paused, 4=Cleaning, 5=Error |
| 14 | Brewing Progress | SINT8 | RW | Progress percentage |
| 15 | Cancel Brew | BOOLEAN | RW | Cancel current brew |
| 16 | Current Espresso Profile | UTF8S | RW | Active profile ID |
| 17 | Stats | UTF8S | RW | Format: "val1^val2^val3" |
| 18 | Total Cup Count | SINT64 | RW | Total cups brewed |
| 19 | Espresso Shot Count | SINT64 | RW | Total espresso shots |

### Settings Attributes
| ID | Name | Type | R/W | Description |
|----|------|------|-----|-------------|
| 20 | Language | SINT8 | RW | Language setting |
| 21 | Time Zone | SINT8 | R | Timezone |
| 22 | Time Format | SINT8 | RW | 12/24 hour format |
| 23 | Water Hardness | SINT8 | RW | Water hardness level |
| 24 | Drink Menu Order | UTF8S | RW | Menu order config |
| 25 | Notification Settings | SINT16 | RW | Notification flags |
| 26 | Screen Saver Enabled | BOOLEAN | RW | Screen saver on/off |
| 27 | Screen Brightness | SINT8 | RW | Brightness level |
| 28 | PIN | SINT16 | RW | Machine PIN |
| 29 | Locked | BOOLEAN | RW | Machine locked state |
| 45 | Preground Selected | BOOLEAN | RW | Pre-ground mode |
| 46 | WiFi Enabled | BOOLEAN | RW | WiFi on/off |
| 47 | WiFi SSID | UTF8S | R | Connected network |
| 49 | Device Friendly Name | UTF8S | RW | Custom device name |
| 50 | Wake Drink | UTF8S | RW | Wake-up drink recipe |

### Maintenance Counters
| ID | Name | Type | R/W | Description |
|----|------|------|-----|-------------|
| 39 | Clean Brew Unit State | UTF8S | RW | Format: "current/max" |
| 40 | Descale Unit State | UTF8S | RW | Format: "current/max" |
| 41 | Water Filter Count | UTF8S | RW | Format: "current/max" |
| 42 | Waste Bin Count | UTF8S | RW | Format: "current/max" |

### Device Info
| ID | Name | Type | R/W | Description |
|----|------|------|-----|-------------|
| 100 | Device Serial | UTF8S | RW | Serial number |
| 101 | Device Model | UTF8S | RW | Model/firmware version |
| 102 | Device OS | UTF8S | RW | OS version |

### Version Info
| ID | Name | Type | R/W | Description |
|----|------|------|-----|-------------|
| 2001 | Bootloader Version | SINT64 | R | Bootloader version |
| 2003 | Application Version | SINT64 | R | Application version |
| 2004 | Profile Version | SINT64 | R | Profile version |

### WiFi Info
| ID | Name | Type | R/W | Description |
|----|------|------|-----|-------------|
| 65005 | WiFi Bars | SINT8 | R | Signal strength (RSSI) |
| 65006 | WiFi Steady State | SINT8 | R | WiFi steady state |
| 65007 | WiFi Setup State | SINT8 | R | WiFi setup state |

### Saved Drinks (200-209)
Each slot stores a drink recipe in format: `drinkUID^timestamp^name^recipe`

### Espresso Profiles (300-309)
Each slot stores an espresso profile configuration.

## Drink Recipe Format

Recipes use a compact format: `$<type>|<param1>|<param2>...`

### Recipe Types
| Code | Drink |
|------|-------|
| $0 | Hot Water |
| $1 | Steamed Milk |
| $10 | Drip Coffee |
| $11 | Iced Coffee |
| $50 | Espresso |
| $51 | Americano |
| $52 | Cappuccino |
| $53 | Latte |
| $54 | Flat White |
| $55 | Macchiato |
| $56 | Cortado |
| $57 | Latte Macchiato |

### Recipe Parameters
| Parameter | Description |
|-----------|-------------|
| `e<n>` | Espresso shots |
| `f<n>` | Foam/milk amount (ml) |
| `w<n>:t<n>` | Water amount and temperature |
| `s<n>` | Strength |
| `d<n>` | Dose |
| `x<n>` | Volume (ml) |
| `t<n>` | Temperature |
| `g<n>` | Grind setting |
| `b<n>` | Bloom time |

### Examples
- Latte: `$53|e1|f115` (1 espresso shot, 115ml foam)
- Drip: `$10|s1|d12|x195|t2|g4|b10`
- Hot Water: `$0|w100:t3` (100ml water, temp level 3)

## Terra Kaffe Services API

Secondary API for user-specific data and drink recipes.

### Get User
- **Endpoint**: `POST https://api.terrakaffeservices.com/api/User/`
- **Body**: `{"aferoAccountId": "<ACCOUNT_ID>"}`
- **Response**: User info including `userId`

### Get Default Drinks
- **Endpoint**: `GET https://api.terrakaffeservices.com/api/DefaultDrinks/`
- **Response**: Array of default drink definitions

### Get User Drinks
- **Endpoint**: `GET https://api.terrakaffeservices.com/api/UserDrinks/{userId}`
- **Response**: User's saved/customized drinks

### Get User Espresso Profiles
- **Endpoint**: `GET https://api.terrakaffeservices.com/api/UserEspressoProfile/{userId}`
- **Response**: User's espresso profiles

### Get Bootstrap
- **Endpoint**: `GET https://api.terrakaffeservices.com/api/v1/bootstrap`
- **Response**: News, alerts, app version info

## Real-Time Updates (Conclave WebSocket)

For real-time device state updates:

1. Call `POST /v1/accounts/{accountId}/conclaveAccess` with `{"user": true}`
2. Connect to WebSocket: `wss://conclave-stream1.gk7qmfrz.afero.net`
3. Subscribe to device attribute changes

**Conclave Hosts**:
- HTTP API: `conclave-api1.gk7qmfrz.afero.net`
- WebSocket: `conclave-stream1.gk7qmfrz.afero.net`

## Device Extended Data

The `extendedData` field contains additional device information:
```json
{
  "icode": "leedtkf52",
  "wifiMac": "c4d8d54d2bfc",
  "bleMac": "c4d8d54d2bfe"
}
```

## Device State

The `deviceState` field contains connection status:
```json
{
  "available": true,
  "visible": true,
  "rebooted": false,
  "connectable": false,
  "connected": false,
  "dirty": false,
  "direct": true,
  "rssi": 0,
  "linked": true
}
```

## Implementation Notes

1. **Authentication**: Use Afero OAuth (ROPC flow) for device access, not Terra Kaffe Services login
2. **Account ID**: Retrieved from `/v1/users/me` endpoint's `accountAccess[0].account.accountId`
3. **Attribute Writes**: Must include `"type": "attribute_write"` in request body
4. **Attribute Values**: Always sent as strings, even for numeric types
5. **Maintenance Counters**: Parse "current/max" format to calculate percentage

