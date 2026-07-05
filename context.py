"""Global runtime state, mirroring the static fields of Main.java.

Low-level modules read this module instead of importing the GUI
entry point, which keeps the import graph acyclic.  The startup
code in main.py assigns these as the program initializes.
"""

import sys
import threading
import traceback

# Platform / path state
file_separator = None
line_separator = None
use_shell_folder = True
install_path = None
install_data_path = None
game_path = None
tmp_dir = None

# Properties file handling
prop_file = None
properties = None

# Localized strings and language.  The Witcher's English language
# id is 3 and its string table is dialog_3.tlk (it does NOT use the
# usual Aurora 0=English numbering).  The id is normally taken from
# the Windows registry / platform at startup; this is the fallback,
# defaulting to English.
strings_database = None
language_id = 3

# Resource lookup and templates
resource_files = None
item_templates = None

# Open databases and related files
save_database = None
database_file = None
database = None
save_prefix = None
mod_name = None
mod_file = None
mod_database = None
quests = None
player_name = None
player_file = None
player_database = None
smm_name = None
smm_file = None
smm_database = None

# Top-level GUI window
main_window = None

# Edit-tracking flags
data_modified = False
data_changing = False

# Deferred error reporting (filled from worker threads, shown on
# the main thread).  Mirrors the deferred-exception path in Main.
_pending_errors = []
_pending_lock = threading.Lock()


def get_string(string_ref):
    return strings_database.get_string(string_ref)


def get_label(string_ref):
    return strings_database.get_label(string_ref)


def get_heading(string_ref):
    return strings_database.get_heading(string_ref)


def log_exception(text, exc):
    """Record an error.  Always logged to stderr; the GUI flushes
    pending records to a dialog on the main thread.
    """
    detail = "".join(
        traceback.format_exception(type(exc), exc,
                                   exc.__traceback__))
    sys.stderr.write(text + "\n" + detail + "\n")
    with _pending_lock:
        _pending_errors.append((text, str(exc)))


def take_pending_errors():
    with _pending_lock:
        errors = list(_pending_errors)
        _pending_errors.clear()
    return errors
