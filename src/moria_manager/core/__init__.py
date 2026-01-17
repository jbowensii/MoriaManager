"""Core business logic module.

This module contains the core functionality for save game management and game detection.

Submodules:
    save_parser: MoriaSaveParser for parsing UE4 GVAS save files with CSDC compression
    backup_index: BackupIndexManager for tracking backups with display name mapping
    game_detector: GameDetector for auto-detecting Steam and Epic installations
    trade_data: Parser for DT_OrderDecks.json merchant trade data

The save parser handles the proprietary Return to Moria save format which uses
Unreal Engine 4.27's GVAS format with zlib-compressed CSDC blocks.
"""

from .game_detector import GameDetector

__all__ = [
    "GameDetector",
]
