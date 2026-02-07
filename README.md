# Moria Manager

[![Version](https://img.shields.io/badge/version-1.7.0-blue.svg)](https://github.com/jbowensii/MoriaManager/releases)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)]()

A comprehensive save game, mod, and server manager for **Lord of the Rings: Return to Moria**.

---

## Table of Contents

- [Features](#features)
- [Screenshots](#screenshots)
- [Installation](#installation)
- [Configuration](#configuration)
- [File Locations](#file-locations)
- [Requirements](#requirements)
- [Building from Source](#building-from-source)
- [License](#license)

---

## Features

### Save Game Management

- **Automatic save detection** — Finds game saves in the standard LocalAppData location
- **Backup saves** — Create timestamped backups of individual saves or all saves at once
- **Restore saves** — Restore any previous backup to replace the current save
- **Import saves** — Import save files from external sources
- **Multiple save support** — Manages saves across different game worlds/servers
- **Deletion management** — Optional deletion of saves and backups with confirmation dialogs

### Mod Management

- **Two-pane interface**:
  - **Available Mods** — Mods stored in your backup directory (not active)
  - **Installed Mods** — Mods in the game's `Paks` folder (active in-game)
- **Install mods** — Copy mods from Available to Installed with drag-and-drop support
- **Uninstall mods** — Move mods back to Available or delete them
- **Create folders** — Organize mods into subfolders
- **Supports .pak, .ucas, .utoc** mod file formats

### Trade Manager

- **Track in-game trades** — View all available merchant trade items from the game
- **Quantity tracking** — 4-digit quantity field (0-9999) with increment/decrement controls
- **Checkbox persistence** — Mark trades as completed; state is saved to XML
- **Smart collapse** — Merchants collapse by default; expand only if they have checked items
- **Clear All button** — Reset all checkboxes and quantities at once
- **Search/filter** — Find specific trade items quickly
- **Lazy loading** — Trade Manager loads on first use for faster startup

### Materials Calculator

- **Crafting calculator** — Select weapons and armor to calculate required materials
- **Weapons & Armor lists** — Alphabetically sorted with checkboxes for selection
- **Dwarf count** — Adjust calculations for 1-8 dwarves
- **Game type filter** — Campaign or Sandbox mode (filters by available recipes)
- **Gather button** — Calculate total materials needed for selected items
- **Clear selections** — Reset all selections with one click

### Server Management

- **FTP and SFTP support** — Connect to remote game servers
- **Server list** — Store multiple server configurations per installation
- **Encrypted passwords** — Server passwords are encrypted at rest
- **Remote file operations** — Browse, download, upload, and delete files on remote servers
- **Connection management** — Background-threaded connections with keepalive
- **Interactive terminal** — Browse remote directories with pwd, ls, cd commands

### Multi-Installation Support

- **Steam and Epic Games** support with auto-detection
- **Multiple installations** — Configure and switch between different game installs
- **Custom paths** — Manually specify game and save locations if needed
- **Per-installation settings** — Each installation maintains its own server list and configuration

### Settings & Configuration

- **Configurable logging** — Enable/disable logging via `settings.ini`
- **Enable Deletion setting** — Control whether deletion is allowed in backup/restore screens
- **Installation path display** — Settings dialog shows detected game paths
- **Path detection status** — Visual indicators show detection status

---

## Screenshots

<p align="center">
  <img width="800" alt="Backup Screen" src="https://github.com/user-attachments/assets/0449ef38-1531-4285-9a65-c0a0289b3249" />
</p>

<p align="center">
  <img width="800" alt="Mod Manager" src="https://github.com/user-attachments/assets/96083aab-84ad-479d-a3bd-814b94d33a6b" />
</p>

<p align="center">
  <img width="800" alt="Trade Manager" src="https://github.com/user-attachments/assets/dd1e21d4-8bfd-41be-b259-2911c531c183" />
</p>

---

## Installation

1. Download `MoriaManager.exe` from the [Releases](https://github.com/jbowensii/MoriaManager/releases) page
2. Run the executable — no installation required
3. On first run, configure your backup directory and game installation

---

## Configuration

### Settings File

The application uses a `settings.ini` file located in `%APPDATA%\MoriaManager\` for user preferences:

```ini
[General]
logging = false
```

| Setting | Values | Description |
|---------|--------|-------------|
| `logging` | `true` / `false` | Enable or disable application logging (default: `false`) |

### Logs

When logging is enabled, log files are created in `%APPDATA%\MoriaManager\logs\`.

---

## File Locations

| Item | Default Location |
|------|------------------|
| Game (Steam) | `C:\Program Files (x86)\Steam\steamapps\common\Lord of the Rings Return to Moria` |
| Game (Epic) | `C:\Program Files\Epic Games\LordOfTheRingsReturnToMoria` |
| Saves | `%LOCALAPPDATA%\Moria\Saved\SaveGames` |
| Backups | User-configured (prompted on first run) |
| Config | `%APPDATA%\MoriaManager\configuration.xml` |
| Settings | `%APPDATA%\MoriaManager\settings.ini` |
| Logs | `%APPDATA%\MoriaManager\logs\` |

---

## Requirements

- **Operating System:** Windows 10 or Windows 11
- **Game:** Lord of the Rings: Return to Moria (Steam or Epic Games version)

---

## Building from Source

### Prerequisites

- Python 3.10 or higher
- pip

### Setup

```bash
# Clone the repository
git clone https://github.com/jbowensii/MoriaManager.git
cd MoriaManager

# Install dependencies
pip install -r requirements.txt

# Run the application
python -m moria_manager
```

### Build Executable

```bash
# Install PyInstaller
pip install pyinstaller

# Build the executable
pyinstaller build/moria_manager.spec
```

The executable will be created in the `dist/` folder.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## Support

- **Issues:** [GitHub Issues](https://github.com/jbowensii/MoriaManager/issues)
- **Video Demo:** [YouTube](https://youtu.be/1Vm_W0fmGQ0)
