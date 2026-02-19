"""Entry point for running as python -m moria_manager.

Sets UTF-8 as the default encoding before any other imports to ensure
consistent behavior on all Windows locales (including non-Latin codepages
like Russian CP866, Chinese GBK, etc.).
"""

import os
import sys

# Force UTF-8 mode for the entire Python process.
# This affects open() default encoding, sys.stdin/stdout/stderr,
# and os.fsencode/fsdecode.  Must happen before other imports.
if sys.platform == "win32":
    # PYTHONUTF8=1 equivalent at runtime - forces UTF-8 for all
    # text streams and file I/O that don't specify an encoding.
    os.environ["PYTHONUTF8"] = "1"
    # Reconfigure stdout/stderr to use UTF-8 with error replacement
    # so logging and print() never crash on non-UTF8 consoles.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from moria_manager.app import main

if __name__ == "__main__":
    main()
