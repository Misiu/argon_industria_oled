# Argon Industria OLED Home Assistant Integration

Custom Home Assistant integration for the Argon ONE V5 Industria OLED module (SSD1306, 128x64, I2C address `0x3C`).

## Overview

- Domain: `argon_industria_oled`
- Local hardware control on Raspberry Pi via I2C
- Runtime dependencies: `smbus2`, `Pillow`
- Draw service syntax aligned with [OpenDisplay](https://github.com/OpenDisplay/Home_Assistant_Integration) to reduce friction for users already familiar with OpenDisplay.

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

1. Open Home Assistant: Settings → Devices & Services → HACS → Integrations.
2. Add custom repository:
   - URL: `https://github.com/Misiu/Argon-Industria-V5-OLED`
   - Category: Integration
3. Install integration and restart Home Assistant.
4. Add integration: Settings → Devices & Services → Add Integration → Argon OLED.

## drawcustom Service

Service: `argon_industria_oled.drawcustom`

| Parameter | Description                     | Required | Default |
|-----------|---------------------------------|----------|---------|
| `clear`   | Clear display before drawing    | No       | `true`  |
| `payload` | List of draw elements (YAML)    | Yes      | —       |

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

| # | Type | Description |
|---|------|-------------|
| 1 | [`text`](#text) | Draws text at a position |
| 2 | [`multiline`](#multiline) | Draws text split across multiple lines by a delimiter |
| 3 | [`line`](#line) | Draws a straight line |
| 4 | [`rectangle`](#rectangle) | Draws a hollow or optionally filled rectangle |
| 5 | [`filled_rectangle`](#filled_rectangle) | Draws a filled rectangle with an optional outline |
| 6 | [`dlimg`](#dlimg) | Pastes a local image file onto the display |
| 7 | [`pixel`](#pixel) | Draws a single pixel |
| 8 | [`progress_bar`](#progress_bar) | Draws a progress bar with optional percentage label |
| 9 | [`icon`](#icon) | Draws a Material Design Icon |

---

### text

Draws a single line of text at the specified position.

![text element](tests/images/type_text.png)

| Parameter | Description        | Required | Default | Notes                   |
|-----------|--------------------|----------|---------|-------------------------|
| `value`   | Text to display    | Yes      | —       | String                  |
| `x`       | X position         | Yes      | —       | Pixels from left edge   |
| `y`       | Y position         | Yes      | —       | Pixels from top edge    |
| `size`    | Font size          | No       | `20`    | Pixels                  |

```yaml
- type: text
  value: "CPU 42C"
  x: 4
  y: 4
  size: 12
```

---

### multiline

Splits text on a delimiter and draws each segment as a separate line using Pillow's `multiline_text`.

![multiline text element](tests/images/type_multiline.png)

| Parameter   | Description                     | Required | Default | Notes                               |
|-------------|---------------------------------|----------|---------|-------------------------------------|
| `value`     | Text with delimiter-separated lines | Yes  | —       | String                              |
| `x`         | X position                      | Yes      | —       | Pixels from left edge               |
| `y`         | Y position                      | Yes      | —       | Pixels from top edge                |
| `delimiter` | Character used to split lines   | No       | `\|`    | Single character; escape in YAML: `"\|"` |
| `offset_y`  | Additional vertical offset      | No       | `0`     | Pixels; added to `y` before drawing |
| `size`      | Font size                       | No       | `20`    | Pixels                              |
| `spacing`   | Extra spacing between lines     | No       | `2`     | Pixels                              |

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

---

### line

Draws a straight line between two points.

![line element](tests/images/type_line.png)

| Parameter | Description              | Required | Default    | Notes                        |
|-----------|--------------------------|----------|------------|------------------------------|
| `x_start` | Starting X position      | Yes      | —          | Pixels from left edge        |
| `y_start` | Starting Y position      | Yes      | —          | Pixels from top edge         |
| `x_end`   | Ending X position        | Yes      | —          | Pixels from left edge        |
| `y_end`   | Ending Y position        | No       | `y_start`  | Defaults to horizontal line  |
| `width`   | Line thickness           | No       | `1`        | Pixels; minimum `1`          |

```yaml
- type: line
  x_start: 0
  y_start: 10
  x_end: 127
  y_end: 10
  width: 1
```

---

### rectangle

Draws a rectangle outline; optionally fills the interior.

![rectangle element](tests/images/type_rectangle.png)

| Parameter | Description                    | Required | Default | Notes                            |
|-----------|--------------------------------|----------|---------|----------------------------------|
| `x_start` | Left edge X position           | Yes      | —       | Pixels from left edge            |
| `y_start` | Top edge Y position            | Yes      | —       | Pixels from top edge             |
| `x_end`   | Right edge X position          | Yes      | —       | Pixels from left edge            |
| `y_end`   | Bottom edge Y position         | Yes      | —       | Pixels from top edge             |
| `fill`    | Fill the interior with color   | No       | `false` | `true` / `false`                 |

```yaml
- type: rectangle
  x_start: 10
  y_start: 10
  x_end: 100
  y_end: 40
  fill: false
```

---

### filled_rectangle

Draws a filled rectangle; optionally adds an outline border.

![filled_rectangle element](tests/images/type_filled_rectangle.png)

| Parameter | Description                      | Required | Default | Notes            |
|-----------|----------------------------------|----------|---------|------------------|
| `x_start` | Left edge X position             | Yes      | —       | Pixels from left edge  |
| `y_start` | Top edge Y position              | Yes      | —       | Pixels from top edge   |
| `x_end`   | Right edge X position            | Yes      | —       | Pixels from left edge  |
| `y_end`   | Bottom edge Y position           | Yes      | —       | Pixels from top edge   |
| `outline` | Draw a border around the fill    | No       | `true`  | `true` / `false` |

```yaml
- type: filled_rectangle
  x_start: 20
  y_start: 20
  x_end: 60
  y_end: 40
  outline: true
```

---

### dlimg

Loads a local image file and pastes it onto the display canvas.
The image is converted to 1-bit (black & white) before pasting.

![dlimg element](tests/images/type_dlimg.png)

| Parameter | Description                           | Required | Default           | Notes                                 |
|-----------|---------------------------------------|----------|-------------------|---------------------------------------|
| `url`     | Absolute path to the image file       | Yes      | —                 | Local filesystem path, e.g. `/config/www/oled/logo.png` |
| `x`       | Paste X position (top-left corner)    | Yes      | —                 | Pixels from left edge                 |
| `y`       | Paste Y position (top-left corner)    | Yes      | —                 | Pixels from top edge                  |
| `xsize`   | Target width after resize             | No       | Image native width  | Pixels; skipped if `0`              |
| `ysize`   | Target height after resize            | No       | Image native height | Pixels; skipped if `0`              |

```yaml
- type: dlimg
  url: "/config/www/oled/logo.png"
  x: 0
  y: 0
  xsize: 64
  ysize: 32
```

---

### pixel

Draws a single pixel at the specified coordinates.

![pixel element](tests/images/type_pixel.png)

| Parameter | Description      | Required | Default | Notes                 |
|-----------|------------------|----------|---------|-----------------------|
| `x`       | X position       | Yes      | —       | Pixels from left edge |
| `y`       | Y position       | Yes      | —       | Pixels from top edge  |

```yaml
- type: pixel
  x: 5
  y: 5
```

---

### progress_bar

Draws a filled progress bar with an optional centred percentage label.
The label is composited with XOR so it is always legible — black text over the
filled region, white text over the empty region — at any progress value.

**Progress levels** (direction: right)

![progress bar at 0, 25, 50, 75, and 100 percent](tests/images/progress_bar_progress.png)

**Fill directions** at 60 %

![progress bar in all four fill directions](tests/images/progress_bar_directions.png)

**Percentage text** (`show_percentage: true`, XOR composited)

![progress bar with centred percentage label at 50 and 75 percent](tests/images/progress_bar_percentage.png)

**Visual styles** — standard / thick border / inverted colours

![standard, thick-border, and inverted-colour progress bars](tests/images/progress_bar_styles.png)

| Parameter        | Description                              | Required | Default  | Notes                                          |
|------------------|------------------------------------------|----------|----------|------------------------------------------------|
| `x_start`        | Left edge X position                     | Yes      | —        | Pixels from left edge                          |
| `y_start`        | Top edge Y position                      | Yes      | —        | Pixels from top edge                           |
| `x_end`          | Right edge X position                    | Yes      | —        | Pixels from left edge                          |
| `y_end`          | Bottom edge Y position                   | Yes      | —        | Pixels from top edge                           |
| `progress`       | Fill level                               | Yes      | —        | `0`–`100`; clamped to range                    |
| `direction`      | Fill direction                           | No       | `right`  | `right` / `left` / `up` / `down`               |
| `background`     | Color of the unfilled region             | No       | `black`  | `black` / `white`                              |
| `fill`           | Color of the filled region               | No       | `white`  | `black` / `white`                              |
| `outline`        | Border color                             | No       | `white`  | `black` / `white`                              |
| `width`          | Border thickness                         | No       | `1`      | Pixels; minimum `1`                            |
| `show_percentage`| Draw a centred `N%` label inside the bar | No       | `false`  | Label uses XOR compositing for contrast        |
| `size`           | Font size for the percentage label       | No       | `8`      | Pixels; only used when `show_percentage: true` |

```yaml
- type: progress_bar
  x_start: 4
  y_start: 50
  x_end: 123
  y_end: 62
  progress: 72
  direction: right
  show_percentage: true
```

---

### icon

Draws a [Material Design Icon](https://pictogrammers.com/library/mdi/) from
the bundled `materialdesignicons.ttf` font (MDI v7.4.47, 7 447 icons).

The icon is guaranteed to fit exactly inside the declared square.
For example `x=10, y=20, size=30` places the icon in the pixel region `(10, 20) → (39, 49)` —
nothing outside that square is touched.

![home and thermometer MDI icons](tests/images/type_icon.png)

| Parameter | Description                           | Required | Default | Notes                                                      |
|-----------|---------------------------------------|----------|---------|------------------------------------------------------------|
| `value`   | Icon name                             | Yes      | —       | With or without `mdi:` prefix, e.g. `"mdi:home"` or `"home"` |
| `x`       | Top-left corner X position            | Yes      | —       | Pixels from left edge                                      |
| `y`       | Top-left corner Y position            | Yes      | —       | Pixels from top edge                                       |
| `size`    | Side length of the icon square        | Yes      | —       | Pixels; minimum `6`                                        |
| `fill`    | Icon color                            | No       | `white` | `black` / `white`                                          |

```yaml
- type: icon
  value: "mdi:home"
  x: 4
  y: 4
  size: 24
  fill: white

- type: icon
  value: "thermometer"
  x: 68
  y: 4
  size: 20
```

---

## Other Services

| Service                             | Description                          |
|-------------------------------------|--------------------------------------|
| `argon_industria_oled.clear`        | Clears the display to black          |
| `argon_industria_oled.show_logo`    | Redraws the startup splash / logo    |

## Hardware Notes

| Property         | Value        |
|------------------|--------------|
| I2C bus          | `1`          |
| I2C address      | `0x3C`       |
| Resolution       | `128x64`     |
| Linux I2C path   | `/dev/i2c-1` |

## Development Checks

Run before commit:

```bash
python -m pip install -r requirements_dev.txt

ruff format --check .
ruff check .
mypy custom_components/argon_industria_oled
pylint custom_components/argon_industria_oled

hassfest
```

## License

MIT (see LICENSE).
