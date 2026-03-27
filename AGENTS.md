# Contributor Guidelines for Argon Industria OLED Integration

Welcome! This repository hosts the Home Assistant custom integration for the Argon Industria OLED module. Please follow the guidelines below when adding or editing files inside this repository.

## General Guidance
- Write idiomatic, well-typed Python 3.12 code that follows [PEP 8](https://peps.python.org/pep-0008/) unless a more specific rule applies.
- Prefer small, focused modules and functions. Avoid large monolithic functions—extract helpers when logic becomes complex.
- Include detailed module- and function-level docstrings explaining hardware assumptions and side-effects.
- All blocking I/O (hardware access, filesystem, shell, network) **must** execute in the executor using `hass.async_add_executor_job`.
- Guard hardware-specific code so that unit tests and validation tools can run without the device attached. Raise `HomeAssistantError` with clear messages when checks fail.
- Always keep translations in sync: update both `strings.json` and language-specific files in `translations/` when you change user-facing text.

## Repository Structure
- `custom_components/argon_industria_oled/`: Home Assistant integration source. Maintain `__all__` exports where appropriate and keep constants in `const.py`.
- `.github/workflows/`: Automation pipelines (hassfest, HACS). Update these when workflows change and keep them minimal.
- Documentation belongs in `README.md`. If you add new configuration options, ensure they are described there as well as in config flow strings.

## Testing & Tooling

### Quality CI checks (`.github/workflows/quality.yaml`)
All four checks **must pass** before every commit.  Run them in this order:

```bash
ruff format --check .         # format check — fixes: ruff format .
ruff check .                  # lint
mypy custom_components/argon_industria_oled
pylint custom_components/argon_industria_oled
```

If `ruff format --check .` fails, auto-fix with `ruff format .` and re-verify.

### Additional validation
- Before committing, run `hassfest` and the HACS action locally when possible. Workflows must remain green.
- When adding Python dependencies, pin exact versions in `manifest.json` and justify them in code comments if they are hardware-specific.

Thanks for contributing and helping keep the integration reliable!
