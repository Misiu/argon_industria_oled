# Copilot Instructions for Argon Industria OLED Integration

This is a Home Assistant custom integration for the Argon Industria OLED module (a hardware display for Raspberry Pi 5).

## Project Overview
- **Technology**: Python 3.12, Home Assistant integration
- **Hardware**: Argon Industria OLED module via I²C (address 0x3C on /dev/i2c-1)
- **Dependencies**: `smbus-cffi` (I²C communication), `Pillow` (image rendering)

## Key Coding Standards
- Follow [PEP 8](https://peps.python.org/pep-0008/) style guidelines
- Use type hints for all functions and methods
- All blocking I/O must use `hass.async_add_executor_job` (filesystem, I²C, network)
- Write detailed docstrings explaining hardware assumptions and side effects
- Guard hardware-specific code for testability without physical device

## Repository Structure
- `custom_components/argon_industria_oled/`: Main integration code
  - `__init__.py`: Integration setup and coordinator initialization
  - `config_flow.py`: Configuration UI and validation
  - `coordinator.py`: Data fetching and display updates
  - `display.py`: Low-level I²C and OLED rendering
  - `const.py`: All constants and configuration keys
  - `strings.json`: User-facing text (keep in sync with translations/)
  - `translations/`: Localized strings (currently en.json)
  - `manifest.json`: Integration metadata and dependencies

## Testing & Validation
- Run `hassfest` before committing (validates manifest.json and structure)
- Run `python3 -m script.hacs` for HACS validation
- Both checks must pass for CI to succeed

## Home Assistant Patterns
- Config entries store user configuration
- Coordinators handle periodic data updates
- Display updates happen every 30 seconds (COORDINATOR_UPDATE_INTERVAL)
- Hardware errors raise `HomeAssistantError` with clear messages
- Use `async_add_executor_job` for all sync I/O operations

## Translation Updates
When changing user-facing text, update BOTH:
1. `strings.json` (base definitions)
2. `translations/en.json` (and any other language files)

See `AGENTS.md` for complete contributor guidelines.
