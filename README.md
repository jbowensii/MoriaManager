# Moria Manager

A save game and mod manager for **Lord of the Rings: Return to Moria**.

---

## Release v1.2

### New Features

#### Settings Dialog Improvements
- **Installation Path display** - Settings dialog now shows game installation paths for Steam and Epic
- **Custom Installation support** - Custom installation now supports both Installation Path and Save Path configuration
- **Path detection status** - Visual indicators show whether game/saves are detected at default locations

#### Performance Improvements
- **Lazy loading for Trade Manager** - Trade Manager UI is now loaded on first use instead of at startup, significantly improving application startup time
- **Resize debouncing** - Trade Manager column rebuilds are now debounced to prevent multiple rapid rebuilds during window resize

### Bug Fixes
- Improved startup performance by deferring Trade Manager initialization

---

## Release v1.1

### New Features

#### Deletion Management
- **Enable Deletion setting** - New configuration option to enable/disable deletion functionality
- **Delete saves and backups** - Remove individual files or entire worlds/characters from backup and restore screens
- **Delete mods** - Remove mods from the Available Mods pane (always enabled, separate from deletion setting)
- **Visual indicators** - Yellow border highlights restore entries with no backups remaining
- **Confirmation dialogs** - Context-aware delete prompts (shows "Delete World", "Delete Character", "Delete Mod", etc.)

#### Trade Manager Improvements
- **Quantity tracking** - 4-digit quantity field (0-9999) with up/down arrows for each trade item
- **Smart collapse** - Merchants collapse by default; only expand if they have checked items
- **State persistence** - Quantities are saved alongside checkbox state

#### UI/UX Improvements
- **Red trash icon** - Visual delete button appears on selected items when deletion is enabled
- **Dual-pane refresh** - Both left and right panes refresh after deletion operations
- **Fixed UTF-16 parsing** - Proper display of world names with special characters

### Bug Fixes
- Fixed delete confirmation dialog button cutoff issue
- Fixed selection restoration after single file deletion
- Fixed tooltip "sticking" on screen issue

---

## Features

### Save Game Management
- **Automatic save detection** - Finds game saves in the standard LocalAppData location
- **Backup saves** - Create timestamped backups of individual saves or all saves at once
- **Restore saves** - Restore any previous backup to replace the current save
- **Multiple save support** - Manages saves across different game worlds/servers

### Mod Management
- **Two-pane interface**:
  - **Available Mods** - Mods stored in your backup directory (not active)
  - **Installed Mods** - Mods in the game's `Paks` folder (active in-game)
- **Install mods** - Copy mods from Available to Installed (with drag-and-drop support)
- **Uninstall mods** - Move mods back to Available or delete them
- **Create folders** - Organize mods into subfolders
- **Supports .pak, .ucas, .utoc** mod file formats

### Trade Manager
- **Track in-game trades** - View all available trade items from the game's data
- **Checkbox persistence** - Mark trades as completed; state is saved to XML
- **Clear All button** - Reset all checkboxes at once
- **Search/filter** - Find specific trade items quickly

### Multi-Installation Support
- **Steam and Epic Games** support with auto-detection
- **Multiple installations** - Configure and switch between different game installs
- **Custom paths** - Manually specify game and save locations if needed

## Screenshots

<img width="2597" height="1702" alt="image" src="https://github.com/user-attachments/assets/0449ef38-1531-4285-9a65-c0a0289b3249" />
<img width="2607" height="1697" alt="image" src="https://github.com/user-attachments/assets/96083aab-84ad-479d-a3bd-814b94d33a6b" />
<img width="2604" height="1683" alt="image" src="https://github.com/user-attachments/assets/dd1e21d4-8bfd-41be-b259-2911c531c183" />

## Installation

1. Download `MoriaManager.exe` from the [Releases](https://github.com/jbowensii/MoriaManager/releases) page
2. Run the executable - no installation required
3. On first run, configure your backup directory and game installation

## File Locations

| Item | Default Location |
|------|------------------|
| Game (Steam) | `C:\Program Files (x86)\Steam\steamapps\common\Lord of the Rings Return to Moria` |
| Game (Epic) | `C:\Program Files\Epic Games\LordOfTheRingsReturnToMoria` |
| Saves | `%LOCALAPPDATA%\Moria\Saved\SaveGames` |
| Backups | User-configured (prompted on first run) |
| Config | `%APPDATA%\MoriaManager\config.xml` |

## Requirements

- Windows 10/11
- Lord of the Rings: Return to Moria (Steam or Epic Games version)

Watch what it can do here... Non-public BETA video demonstration here: https://youtu.be/1Vm_W0fmGQ0 
All issues shown in the video have been resolved and tested, please enter bugs on github.
