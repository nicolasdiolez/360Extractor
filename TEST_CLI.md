# CLI testing

This former standalone guide has been consolidated to avoid contradictory instructions.

- [Install and run](README.md#install-from-source)
- [CLI arguments and examples](docs/CLI.md)
- [JSON settings and naming](docs/SETTINGS.md)
- [Studio/CLI acceptance protocol and binary checks](docs/CLI_TESTING_PROTOCOL.md)

Cube face indices only apply with `--layout cube`; the default Ring layout uses View_* names. Each extraction creates a new run folder inside the destination. The tool exports supported GPS, not IMU orientation, and accepts JSON configurations, not YAML.
