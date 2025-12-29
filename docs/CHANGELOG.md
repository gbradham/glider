# Changelog

All notable changes to GLIDER will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial public release
- Visual flow programming interface (Builder mode)
- Touch-optimized experiment runner (Runner mode)
- Arduino support via Telemetrix
- Raspberry Pi GPIO support
- Experiment serialization (.glider files)
- Data recording to CSV
- Plugin system for extensibility
- Comprehensive documentation

### Hardware Support
- Arduino Uno, Mega, Nano
- Raspberry Pi GPIO
- Digital I/O, Analog Input, PWM, Servo

### Built-in Nodes
- StartExperiment, EndExperiment
- Delay, Loop, WaitForInput
- Output (digital write)
- Input (digital/analog read)

---

## Version History Template

Future releases will follow this format:

## [1.0.0] - YYYY-MM-DD

### Added
- New features

### Changed
- Changes to existing features

### Deprecated
- Features to be removed in future versions

### Removed
- Removed features

### Fixed
- Bug fixes

### Security
- Security improvements

---

## Versioning

GLIDER uses Semantic Versioning:

- **MAJOR** version: Incompatible API changes
- **MINOR** version: New functionality (backwards compatible)
- **PATCH** version: Bug fixes (backwards compatible)

### Pre-release Labels

- `alpha` - Early development, unstable
- `beta` - Feature complete, testing
- `rc` - Release candidate, final testing

Example: `1.0.0-beta.1`

---

## Migration Guides

When breaking changes occur, migration guides will be provided here.

### Upgrading from 0.x to 1.0

*(Will be documented when applicable)*

---

## File Format Versions

| GLIDER Version | Schema Version | Notes |
|----------------|----------------|-------|
| 1.0.x | 1.0.0 | Initial release |

Old experiment files are automatically migrated to the current schema version.

---

## Links

- [Releases](https://github.com/LaingLab/glider/releases)
- [Issues](https://github.com/LaingLab/glider/issues)
- [Documentation](https://github.com/LaingLab/glider/tree/main/docs)
