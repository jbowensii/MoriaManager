"""Moria Manager - Save game and mod manager for Lord of the Rings: Return to Moria.

This application provides:
    - Save game backup and restore for worlds and characters
    - Mod management (install, uninstall, organize mods)
    - Trade manager for tracking merchant orders
    - Server information storage with encrypted password support
    - Support for both Steam and Epic Games installations

The application uses CustomTkinter for a modern GUI interface and stores
configuration in %APPDATA%/MoriaManager.

Package Structure:
    app: Main application entry point and orchestrator
    config: Configuration management, paths, schemas, and security
    core: Business logic for save parsing, backup indexing, and game detection
    gui: User interface components (main window, dialogs, widgets)
    assets: Icons, images, and asset loading utilities

Quick Start:
    Run from command line::

        python -m moria_manager

    Or programmatically::

        from moria_manager.app import main
        main()

Configuration:
    - Config file: %APPDATA%/MoriaManager/configuration.xml
    - Log file: %APPDATA%/MoriaManager/moria_manager.log
    - Backup indexes: %APPDATA%/MoriaManager/index_*.xml
"""

__version__ = "1.2.0"
__app_name__ = "Moria Manager"
