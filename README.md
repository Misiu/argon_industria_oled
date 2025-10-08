# WIP Argon Industria OLED Home Assistant Integration

This repository contains a custom [Home Assistant](https://www.home-assistant.io/) integration that drives the Argon Industria OLED module connected to a Raspberry Pi 5 via I²C. The integration detects the display, renders useful status information, and keeps the content up to date directly from Home Assistant.

## Features
- **HACS ready**: Installable through [HACS](https://hacs.xyz/).
- **Guided configuration**: Config flow verifies that I²C is enabled and the display is reachable before you pick the content you want to show.
- **Flexible content**: Choose between network IP address, CPU temperature, or any Home Assistant sensor entity for each display line.
- **Automatic refresh**: The display updates periodically to keep information current.

## Hardware
- Argon Industria OLED module (55mm × 90mm) — see the [datasheet](https://files.waveshare.com/wiki/ARGON-ONE-V5-OLED-Module/FOR_PRINT_ARGON_INDUSTRIA_OLED_55mmx90mm_20241219.pdf).
- Raspberry Pi 5 with the module attached to the 40-pin header and I²C enabled.

### Enabling I²C
The integration requires I²C to be enabled on your Raspberry Pi. For Home Assistant OS users, the easiest way to enable I²C is to install the **HassOS I2C Configurator** add-on:
- Add-on repository: https://github.com/adamoutler/HassOSConfigurator
- Community discussion: https://community.home-assistant.io/t/add-on-hassos-i2c-configurator/264167

The integration will automatically detect the I²C bus (trying bus 1 first, then bus 0 for older Raspberry Pi models).

## Installation via HACS
1. In Home Assistant, open **HACS → Integrations**.
2. Click the three-dot menu and choose **Custom repositories**.
3. Enter `https://github.com/Misiu/Argon-Industria-V5-OLED` as the repository URL and select **Integration** as the category.
4. Add the repository, then search for “Argon Industria OLED” and install it.
5. Restart Home Assistant when prompted.

## Configuration
1. Navigate to **Settings → Devices & Services** and click **Add Integration**.
2. Search for **Argon Industria OLED**.
3. The config flow will:
   - Auto-detect the I²C bus (tries `/dev/i2c-1` first, then `/dev/i2c-0` for older models).
   - Ensure the display responds at address `0x3C`.
   - Show a welcome message on the OLED.
4. After hardware checks succeed, choose what each display line should show:
   - **IP address**: The first active IPv4 address on the host.
   - **CPU temperature**: Read from the main SoC thermal zone.
   - **Sensor value**: Provide the entity ID of any Home Assistant sensor.

You can update these selections later from the integration’s options.

## Development
### Requirements
- Python 3.12+
- [Home Assistant Core dev environment](https://developers.home-assistant.io/docs/development_environment)
- OLED dependencies: `smbus-cffi`, `Pillow`

### Local setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements_dev.txt  # optional helper tools
```

### Validation
Run the same checks used in CI:
```bash
hassfest
python3 -m script.hacs
```

## License
Distributed under the MIT License. See `LICENSE` for details.
