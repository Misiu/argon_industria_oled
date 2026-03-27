# GitHub Copilot Instructions

This repository contains a Home Assistant custom integration for the Argon Industria OLED module (a hardware display for Raspberry Pi 5).

## Project Overview

- **Technology**: Python 3.12, Home Assistant integration framework
- **Hardware**: Argon Industria OLED module via I²C (I²C address 0x3C, data control byte 0x6A, on /dev/i2c-1 or /dev/i2c-0)
- **Dependencies**: `smbus-cffi` (I²C communication), `Pillow` (image rendering)
- **Based on**: [Argon40 ArgonOne Script](https://github.com/okunze/Argon40-ArgonOne-Script/blob/master/source/scripts/argoneonoled.py)

## Python Requirements

- **Compatibility**: Python 3.12+
- **Language Features**: Use modern Python features when appropriate:
  - Type hints for all functions, methods, and variables
  - f-strings (preferred over `%` or `.format()`)
  - Dataclasses for data structures
- **Formatting**: Follow [PEP 8](https://peps.python.org/pep-0008/) style guidelines
- **Language**: American English for all code, comments, and documentation

## Code Organization

### Repository Structure
- `custom_components/argon_industria_oled/`: Main integration code
  - `__init__.py`: Integration setup and coordinator initialization
  - `config_flow.py`: Configuration UI and validation
  - `coordinator.py`: Data fetching and display updates (DataUpdateCoordinator)
  - `display.py`: Low-level I²C and OLED rendering
  - `const.py`: All constants and configuration keys
  - `strings.json`: User-facing text (keep in sync with translations/)
  - `translations/`: Localized strings (currently en.json)
  - `manifest.json`: Integration metadata and dependencies

### Documentation Standards
- **File Headers**: Short and concise
  ```python
  """Low-level routines for interacting with the Argon Industria OLED display."""
  ```
- **Method/Function Docstrings**: Required for all public methods
- **Hardware Assumptions**: Document hardware-specific behavior in docstrings
- **Side Effects**: Clearly document I/O operations and state changes

## Async Programming

All external I/O operations must be async or run in executor.

### Blocking Operations
- **Use Executor**: For all blocking I/O operations (I²C, filesystem, network)
  ```python
  result = await hass.async_add_executor_job(blocking_function, args)
  ```
- **Never Block Event Loop**: Avoid file operations, `time.sleep()`, blocking I²C calls

### Data Update Coordinator
- **Pattern**: Use `DataUpdateCoordinator` for periodic data fetching
  ```python
  class ArgonIndustriaOledCoordinator(DataUpdateCoordinator[dict[str, str]]):
      def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
          super().__init__(
              hass,
              logger=_LOGGER,
              name=DOMAIN,
              update_interval=COORDINATOR_UPDATE_INTERVAL,
          )
  ```
- **Update Interval**: Current setting is 30 seconds (COORDINATOR_UPDATE_INTERVAL)

## Integration Guidelines

### Configuration Flow
- **Version Control**: Set `VERSION = 1` in config flow
- **Hardware Validation**: Verify I²C availability and OLED communication before setup
- **Error Handling**: Define errors in `strings.json` under `config.error`
- **Welcome Display**: Show welcome message on successful initialization

### Options Flow
- **Support Reconfiguration**: Allow users to update display content settings
- **Preserve Data**: Merge `config_entry.data` and `config_entry.options` for current settings

### Error Handling
- **Hardware Errors**: Raise `HomeAssistantError` with clear, user-friendly messages
- **I²C Detection**: Try bus 1 first (Raspberry Pi 5), then bus 0 (older models)
- **Graceful Degradation**: Close resources properly on errors

### Hardware Guards
- **Import Guards**: Wrap hardware imports with try/except for testability
  ```python
  try:
      from smbus import SMBus
  except ImportError as err:
      raise RuntimeError("smbus-cffi must be installed") from err
  ```
- **Device Detection**: Check `/dev/i2c-*` existence before opening bus
- **Safe Cleanup**: Always close I²C bus in finally blocks or when errors occur

## Testing & Validation

### Quality CI checks (`.github/workflows/quality.yaml`)
All four checks **must pass** before every commit.  Run them in this order:

```bash
ruff format --check .         # format check — fix with: ruff format .
ruff check .                  # lint
mypy custom_components/argon_industria_oled
pylint custom_components/argon_industria_oled
```

If `ruff format --check .` would reformat any file, run `ruff format .` to fix it and re-run the check.

### Additional validation
- **hassfest**: Run before committing (validates manifest.json and structure)
  ```bash
  hassfest
  ```
- **HACS validation**: Run to ensure HACS compatibility
  ```bash
  python3 -m script.hacs
  ```
- **Both checks must pass** for CI to succeed

## Translation Updates

When changing user-facing text, update BOTH:
1. `strings.json` (base definitions)
2. `translations/en.json` (and any other language files)

Keep translation keys consistent between files.

## Additional Resources

See `AGENTS.md` for detailed contributor guidelines and testing procedures.
