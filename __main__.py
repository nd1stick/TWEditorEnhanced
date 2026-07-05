"""Start The Witcher Save Editor.

Double-click this file to launch the program (a console window
opens alongside the editor; closing the editor closes it).  It can
also be started with "python -m tweditor" from the parent folder.

When this file is run directly, the folder above the tweditor
package is added to the import path so the package can be loaded,
then the program starts.
"""

import os
import sys

_package_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_package_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from tweditor.main import main

if __name__ == "__main__":
    main()
