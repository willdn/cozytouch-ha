from homeassistant.components.climate import HVACMode

DOMAIN = "cozytouch"

BASE_URL = "https://apis.groupe-atlantic.com"
TOKEN_PATH = "/users/token"
MAGELLAN_PATH = "/magellan"

CLIENT_ID = "Ct_1JVyTmILX8IefA7aUNBjFnZUa"
CLIENT_SECRET = "2EcNDz_dy342UJqo2Z7pSJNvUv0a"

# Capability IDs (from fr.modulotech.app.domain.model.devices.Capabilities)
CAP_HVAC_MODE            = 7    # SYSTEM_OPERATION_SERVICE_REQUESTED_CAPABILITY — HVAC operating mode
CAP_HEATING_TARGET       = 40
CAP_AMBIENT_TEMP         = 117
CAP_HEATING_STATUS       = 153
CAP_ROOM_NAME            = 154
CAP_HEATING_MIN          = 160
CAP_HEATING_MAX          = 161
CAP_COOLING_MIN          = 162
CAP_COOLING_MAX          = 163
CAP_HVAC_MODE_AVAILABLE  = 166  # currently available HVAC modes
CAP_COOLING_TARGET       = 177
CAP_SYSTEM_MODE          = 184  # scheduling/programme mode (basic/prog/auto) — NOT HVAC mode
CAP_AVAILABLE_MODES      = 217
CAP_WIFI_CONNECTED       = 218
CAP_HVAC_MODE_SUPPORTED  = 100022  # HVAC modes the device supports
CAP_FAN_SPEED            = 100801  # VENTILATION_CURRENT_SPEED_MODE
CAP_QUIET_MODE           = 100802  # VENTILATION_QUIET_MODE

# Cap 7 (HVAC_MODE) → HVACMode mapping.
# Source: fr.modulotech.app.domain.model.devices.features.service.Service
SYSTEM_MODE_MAP: dict[int, HVACMode] = {
    0: HVACMode.OFF,
    2: HVACMode.AUTO,
    3: HVACMode.COOL,
    4: HVACMode.HEAT,
    7: HVACMode.FAN_ONLY,
    8: HVACMode.DRY,
}
SYSTEM_MODE_REVERSE: dict[HVACMode, int] = {v: k for k, v in SYSTEM_MODE_MAP.items()}

# Cap 100801 (FAN_SPEED) — source: VentilationSpeedMode.java
FAN_SPEED_MAP: dict[int, str] = {1: "low", 2: "medium", 3: "high", 4: "auto"}
FAN_SPEED_REVERSE: dict[str, int] = {v: k for k, v in FAN_SPEED_MAP.items()}

PRESET_NONE  = "none"
PRESET_QUIET = "quiet"

POLL_INTERVAL_SECONDS = 60
# Polite delay between per-device capability fetches
REQUEST_DELAY_SECONDS = 1.0
# Refresh token this many seconds before expiry
TOKEN_REFRESH_BUFFER = 60
