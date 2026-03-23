# Argon Industria OLED Home Assistant Integration

Custom Home Assistant integration for the Argon ONE V5 Industria OLED module (SSD1306, 128x64, I2C address `0x3C`).

## Current Direction
- Domain: `argon_industria_oled`
- Local hardware control on Raspberry Pi via I2C
- Dependencies used by the integration runtime:
  - `smbus2`
  - `Pillow`
- Draw service syntax aligned with OpenDisplay style to reduce friction for users already familiar with OpenDisplay.

## Features
- Automatic display detection during config flow
- Startup splash logo on OLED (kept visible)
- `drawcustom` service with OpenDisplay-like payload syntax
- `clear` and `show_logo` services
- Health state via coordinator + connected binary sensor

## Installation (HACS)
Before installing this integration, make sure I2C is enabled on Home Assistant OS.

### Enable I2C on Home Assistant OS (Required)
This follows the same practical flow used in `Misiu/argon40` and community guidance from the HassOS I2C Configurator thread.

Important:
- Restarting Home Assistant from UI is not enough.
- You need full host reboots (power-cycle style), twice.

Steps:
1. Install and run the HassOS I2C Configurator add-on:
  - Community reference: `https://community.home-assistant.io/t/add-on-hassos-i2c-configurator/264167`
2. Wait until add-on logs report completion.
3. Perform first full reboot of the host (not only HA Core restart).
4. After it boots, perform second full reboot of the host.
5. Only after these two reboots continue with integration installation.

If I2C still does not appear:
- Run the add-on again and repeat the two full host reboots.
- Verify hardware power stability (undervoltage can break I2C bring-up).

1. Open Home Assistant: Settings -> Devices & Services -> HACS -> Integrations.
2. Add custom repository:
   - URL: `https://github.com/Misiu/Argon-Industria-V5-OLED`
   - Category: Integration
3. Install integration and restart Home Assistant.
4. Add integration: Settings -> Devices & Services -> Add Integration -> Argon OLED.

## drawcustom Syntax (OpenDisplay-like)
Service: `argon_industria_oled.drawcustom`

Top-level fields:
- `clear` (optional, bool, default: `true`)
- `payload` (required, list of draw elements)

### Example
```yaml
service: argon_industria_oled.drawcustom
data:
  clear: true
  payload:
    - type: text
      value: "Hello"
      x: 0
      y: 0
      size: 14

    - type: line
      x_start: 0
      y_start: 16
      x_end: 127
      y_end: 16
      width: 1

    - type: rectangle
      x_start: 2
      y_start: 20
      x_end: 125
      y_end: 45
      fill: false

    - type: pixel
      x: 64
      y: 32
```

## Supported Draw Types

### 1) text
Required:
- `type: text`
- `value`
- `x`
- `y`

Optional:
- `size` (default used when omitted)

```yaml
- type: text
  value: "CPU 42C"
  x: 4
  y: 4
  size: 12
```

### 2) multiline
Required:
- `type: multiline`
- `value`
- `x`
- `y`

Optional:
- `delimiter` (default: `|`)
- `offset_y` (default: `0`)
- `size`
- `spacing`

```yaml
- type: multiline
  value: "Line 1|Line 2|Line 3"
  delimiter: "|"
  x: 0
  y: 0
  offset_y: 0
  size: 12
  spacing: 2
```

### 3) line
Required:
- `type: line`
- `x_start`
- `y_start`
- `x_end`

Optional:
- `y_end` (defaults to `y_start`)
- `width` (default: `1`)

```yaml
- type: line
  x_start: 0
  y_start: 10
  x_end: 127
  y_end: 10
  width: 1
```

### 4) rectangle
Required:
- `type: rectangle`
- `x_start`, `y_start`, `x_end`, `y_end`

Optional:
- `fill` (`true/false`, default: `false`)

```yaml
- type: rectangle
  x_start: 10
  y_start: 10
  x_end: 100
  y_end: 40
  fill: false
```

### 5) filled_rectangle
Required:
- `type: filled_rectangle`
- `x_start`, `y_start`, `x_end`, `y_end`

Optional:
- `outline` (`true/false`, default: `true`)

```yaml
- type: filled_rectangle
  x_start: 20
  y_start: 20
  x_end: 60
  y_end: 40
  outline: true
```

### 6) dlimg
Required:
- `type: dlimg`
- `url` (currently local file path)
- `x`, `y`

Optional:
- `xsize`, `ysize`

```yaml
- type: dlimg
  url: "/config/www/oled/logo.png"
  x: 0
  y: 0
  xsize: 64
  ysize: 32
```

### 7) pixel
Required:
- `type: pixel`
- `x`, `y`

```yaml
- type: pixel
  x: 5
  y: 5
```

## Other Services
- `argon_industria_oled.clear`: clears display.
- `argon_industria_oled.show_logo`: redraws startup splash/logo.

## Hardware Notes
- Bus: `1`
- Address: `0x3C`
- Resolution: `128x64`
- Linux path expected: `/dev/i2c-1`

## Development Checks
Run before commit:
```bash
hassfest
python3 -m script.hacs
```

## License
MIT (see LICENSE).
