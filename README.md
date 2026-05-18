# Cozytouch Home Assistant Integration

A custom Home Assistant integration for Atlantic/Cozytouch climate systems (AC/heat pump zones). Exposes each room zone as a `climate` entity with full temperature and mode control.

---

## Requirements

- Home Assistant 2024.1 or newer
- An Atlantic/Cozytouch account (the same credentials you use in the Cozytouch mobile app)
- Your Cozytouch gateway must already be paired and online

---

## Installation

### Option A — Manual (recommended for now)

1. In your Home Assistant config directory, create the folder `custom_components/` if it doesn't already exist.

2. Copy the entire `cozytouch/` folder from this directory into `custom_components/`:

   ```
   <HA config dir>/
   └── custom_components/
       └── cozytouch/
           ├── __init__.py
           ├── manifest.json
           ├── const.py
           ├── api.py
           ├── coordinator.py
           ├── config_flow.py
           ├── climate.py
           ├── strings.json
           └── translations/
               └── en.json
   ```

   On a standard Home Assistant OS install, the config directory is `/config/`.  
   From a Windows machine via Samba share it is typically `\\<ha-ip>\config\`.

3. Restart Home Assistant.  
   Settings → System → Restart → Restart Home Assistant.

### Option B — HACS (recommended)

1. In Home Assistant, open **HACS** (install it first from [hacs.xyz](https://hacs.xyz) if needed).
2. Click the **⋮** menu (top right) → **Custom repositories**.
3. Paste the GitHub URL of this repository and set the category to **Integration**, then click **Add**.
4. The **Cozytouch** integration now appears in HACS. Click it → **Download**.
5. Restart Home Assistant.
6. Proceed to [Adding the Integration](#adding-the-integration) below.

---

## Adding the Integration

1. Go to **Settings → Devices & Services → Integrations**.
2. Click **+ Add Integration** (bottom right).
3. Search for **Cozytouch** and select it.
4. Enter your Atlantic/Cozytouch account **email** and **password**.
5. Click **Submit**.

If your credentials are correct, the integration will:
- Authenticate with the Cozytouch cloud API
- Discover all room zones linked to your account
- Create one `climate` entity per zone

---

## Entities

Each room zone becomes a **Climate entity** with the following capabilities:

| Feature | Detail |
|---|---|
| Current temperature | Reads from the zone's ambient temperature sensor |
| Target temperature | Heating setpoint (heat/auto mode) or cooling setpoint (cool mode) |
| HVAC modes | `off`, `heat`, `cool`, `auto`, `fan_only`, `dry` |
| HVAC action | `idle`, `heating`, `cooling`, or `off` (live status) |
| Min/max temperature | Read from device capabilities (typically 7–30 °C) |

State is polled from the cloud every **60 seconds**.

The mode mapping is sourced from capability **7** (`SYSTEM_OPERATION_SERVICE_REQUESTED_CAPABILITY`) — confirmed by reverse-engineering `Service.java` in the v3.27.0 app:

| API value (cap 7) | HA mode |
|---|---|
| `0` | `off` |
| `2` | `auto` |
| `3` | `cool` |
| `4` | `heat` |
| `7` | `fan_only` (ventilation) |
| `8` | `dry` (dehumidify) |

---

## Troubleshooting

### Integration doesn't appear in the search

- Confirm the folder is named exactly `cozytouch` (lowercase) inside `custom_components/`.
- Confirm you restarted Home Assistant after copying the files.
- Check **Settings → System → Logs** for any import errors mentioning `cozytouch`.

### "Invalid email or password" during setup

- Check that you're using the same credentials as the Cozytouch mobile app.
- The username sent to the API is formatted as `GA-PRIVATEPERSON/<email>`. If your account is a professional/installer account this format may differ — check the logs for the raw HTTP error.

### No climate entities appear after setup

- Go to **Settings → Devices & Services → Integrations → Cozytouch** and check if any devices are listed.
- Check the logs for lines mentioning `Found 0 ROOM zone(s)`. This means the API response didn't contain any devices with "ROOM" in their `modelFamily` or `name` field.
- Run the CLI tool to inspect your raw device data:

  ```bash
  cd /path/to/reverse-engineer-cozytouch
  python cozytouch.py --email you@example.com --password secret devices
  ```

  Look at the `modelFamily` and `name` fields. If neither contains "ROOM", open `coordinator.py` and update the `_is_room_device()` function to match your device's fields.

### Entities show "unavailable"

- The access token expires every 5 minutes. The integration refreshes it automatically. If you see persistent unavailability, check the logs for `Token refresh failed` — this triggers a re-auth prompt in the HA UI.
- Check that your Cozytouch gateway is online in the mobile app.

### Temperature or mode changes don't apply

- The integration writes to the Cozytouch cloud API, which then relays the command to your gateway. There may be a delay of a few seconds.
- Confirm the change was applied by checking the Cozytouch mobile app.
- If the app shows no change, check the logs for HTTP errors from `write_capability`.

---

## File Reference

| File | Purpose |
|---|---|
| `__init__.py` | Entry setup and teardown |
| `manifest.json` | HA domain registration |
| `const.py` | Capability IDs, mode maps, API constants |
| `api.py` | Async HTTP client — auth, token refresh, reads, writes |
| `coordinator.py` | Polls the API every 60s, stores zone state |
| `config_flow.py` | Email/password setup UI |
| `climate.py` | `ClimateEntity` implementation per zone |
| `strings.json` | UI string keys |
| `translations/en.json` | English UI strings |
