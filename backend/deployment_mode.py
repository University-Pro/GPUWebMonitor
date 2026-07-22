import os


PUBLIC_MODE = "public"
LAN_MODE = "lan"
VALID_DEPLOYMENT_MODES = {PUBLIC_MODE, LAN_MODE}
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def load_deployment_mode(value=None):
    """Return a validated server-side deployment mode."""
    mode = (value if value is not None else os.environ.get(
        "GPU_MONITOR_DEPLOYMENT_MODE",
        LAN_MODE,
    )).strip().lower()
    if mode not in VALID_DEPLOYMENT_MODES:
        allowed = ", ".join(sorted(VALID_DEPLOYMENT_MODES))
        raise RuntimeError(
            f"Invalid GPU_MONITOR_DEPLOYMENT_MODE={mode!r}; expected one of: {allowed}"
        )
    return mode


def load_boolean_setting(name, default):
    value = os.environ.get(name)
    if value is None:
        return bool(default)
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise RuntimeError(f"Invalid {name}={value!r}; expected a boolean value")
