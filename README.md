# 1CNG_NOC_AutoDetector

CLI-based AI NOC system for monitoring and detection using **only CLI outputs** collected over SSH/Telnet.

## Workflow

`OBSERVE → COLLECT → NORMALIZE → ANALYZE → CORRELATE → ALERT → REPORT`

## Quick start

1. Create config:

```bash
cp config/config.example.yaml config/config.yaml
```

2. Run a one-shot scan:

```bash
python nocctl.py scan --config config/config.yaml
```

3. Run scheduler:

```bash
python nocctl.py schedule --config config/config.yaml
```

## Plugins

Plugins live under `autodetector/plugins/builtin/<os_name>/`.

To onboard a new vendor/OS you provide exactly 3 files:

- `command_map.yaml`
- `variable_map.yaml`
- `parser.py`

(Optionally `help.yaml` for `nocctl help <os> <topic>`.)

### Plugin SDK commands

List builtin plugins:

```bash
python nocctl.py --config config/config.yaml plugin list
```

Validate a plugin schema:

```bash
python nocctl.py --config config/config.yaml plugin validate cisco_ios
```

Create a new plugin skeleton:

```bash
python nocctl.py --config config/config.yaml plugin init my_new_os
```

Bootstrap skeletons for all OSes in the builtin registry:

```bash
python nocctl.py --config config/config.yaml plugin bootstrap
```
