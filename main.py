"""Application bootstrap.  Faithful port of Main.java.

Detects the platform, locates the game install and the installed
language, loads the localized string table (dialog_<language>.tlk),
reads the BIF key index, builds the resource-file map (each value is
a KeyEntry inside a BIF or an override file path), loads saved
properties, opens the main window, and loads the item templates
behind a progress dialog.

The Witcher's English language id is 3 and its string table is
dialog_3.tlk; the id is taken from the Windows registry (or the
platform default) at startup.
"""

import os
import platform
import subprocess
import sys
import tempfile

from . import context
from .dialogs import ProgressDialog
from .guicommon import flush_errors
from .keydb import KeyDatabase
from .mainwindow import MainWindow
from .stringsdb import StringsDatabase
from .tasks import LoadTemplates

_MAC_INSTALL = (
    "/Applications/The Witcher.app/Contents/"
    "Resources/drive_c/Program Files/The Witcher")

_LINUX_LOCATE = (
    'locate dialog_3.tlk | grep "Witcher.*Data" '
    '| sed -e "s|/Data/dialog_3.tlk||"')


def _documents_dir():
    return os.path.join(os.path.expanduser("~"), "Documents")


def _read_windows_registry():
    import winreg

    sub_keys = [
        r"Software\CD Projekt Red\The Witcher",
        r"Software\Wow6432Node\CD Projekt Red\The Witcher",
    ]
    for sub_key in sub_keys:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, sub_key)
        except OSError:
            continue
        if context.install_path is None:
            try:
                context.install_path = winreg.QueryValueEx(
                    key, "InstallFolder")[0]
            except OSError:
                pass
        if context.language_id == -1:
            try:
                context.language_id = int(
                    winreg.QueryValueEx(key, "Language")[0])
            except (OSError, ValueError):
                pass
        winreg.CloseKey(key)


def _locate_install(os_mac, os_linux, os_win):
    context.install_path = os.environ.get("TW_INSTALL_PATH")
    language = os.environ.get("TW_LANGUAGE")
    context.language_id = int(language) if language else -1

    if context.install_path is not None \
            and context.language_id != -1:
        return

    if os_mac:
        context.install_path = _MAC_INSTALL
        context.language_id = 3
    elif os_linux:
        try:
            output = subprocess.check_output(
                ["/bin/sh", "-c", _LINUX_LOCATE],
                stderr=subprocess.DEVNULL)
            lines = output.decode("utf-8", "replace").splitlines()
            if lines:
                context.install_path = lines[0]
        except (OSError, subprocess.SubprocessError):
            pass
        context.language_id = 3
    elif os_win:
        _read_windows_registry()

    if context.install_path is None:
        raise IOError(
            "Unable to locate The Witcher installation directory")
    if context.language_id == -1:
        # The Witcher English language id is 3; default to English.
        context.language_id = 3


def _process_overrides(directory):
    if not os.path.isdir(directory):
        return
    for entry in os.listdir(directory):
        path = os.path.join(directory, entry)
        if os.path.isdir(path):
            _process_overrides(path)
        else:
            name = entry.lower()
            dot = name.rfind(".")
            if dot > 0 and name[dot:] in (".2da", ".uti"):
                context.resource_files[name] = path


def _load_properties():
    context.properties = {}
    path = context.prop_file
    if path and os.path.isfile(path):
        try:
            with open(path, encoding="latin-1") as in_file:
                for line in in_file:
                    line = line.rstrip("\n").rstrip("\r")
                    if not line or line[0] in "#!":
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        context.properties[key.strip()] = value
        except OSError as exc:
            context.log_exception(
                "Unable to read properties file", exc)


def main():
    try:
        system = platform.system()
        os_mac = system == "Darwin"
        os_linux = system == "Linux"
        os_win = system == "Windows"

        context.file_separator = os.sep
        context.line_separator = os.linesep
        context.tmp_dir = tempfile.gettempdir()

        context.smm_file = os.path.join(
            context.tmp_dir, "TWEditor.smm")
        context.database_file = os.path.join(
            context.tmp_dir, "TWEditor.ifo")
        context.mod_file = os.path.join(
            context.tmp_dir, "TWEditor.mod")
        context.player_file = os.path.join(
            context.tmp_dir, "TWEditor.player")

        _locate_install(os_mac, os_linux, os_win)

        context.install_data_path = os.path.join(
            context.install_path, "Data")
        if not os.path.exists(context.install_data_path):
            os.makedirs(context.install_data_path)

        context.game_path = os.environ.get("TW_DATA_PATH")
        if context.game_path is None:
            if os_mac:
                sub = os.path.join(
                    "com.cdprojektred.TheWitcher", "The Witcher")
            else:
                sub = "The Witcher"
            context.game_path = os.path.join(_documents_dir(), sub)
        saves = os.path.join(context.game_path, "saves")
        if not os.path.exists(saves):
            os.makedirs(saves)

        tlk = os.path.join(
            context.install_data_path,
            "dialog_%d.tlk" % context.language_id)
        if not os.path.isfile(tlk):
            raise IOError(
                "Localized strings database " + tlk
                + " does not exist")
        context.strings_database = StringsDatabase(tlk)

        key_path = os.path.join(
            context.install_data_path, "main.key")
        key_database = KeyDatabase(key_path)
        context.resource_files = {}
        for entry in key_database.get_entries():
            name = entry.file_name.lower()
            dot = name.rfind(".")
            if dot > 0 and name[dot:] in (".2da", ".uti"):
                context.resource_files[name] = entry

        _process_overrides(context.install_data_path)

        prop_dir = os.path.join(
            os.path.expanduser("~"), "Application Data",
            "ScripterRon")
        if not os.path.exists(prop_dir):
            os.makedirs(prop_dir)
        context.prop_file = os.path.join(
            prop_dir, "TWEditor.properties")
        _load_properties()
        context.properties["install.path"] = context.install_path
        context.properties["game.path"] = context.game_path
        context.properties["temp.path"] = context.tmp_dir

        window = MainWindow()
        context.main_window = window
        window.update_idletasks()
        flush_errors(window)

        dialog = ProgressDialog(window, "Loading item templates")
        task = LoadTemplates(dialog)
        task.start()
        dialog.show_dialog()
        flush_errors(window)

        window.mainloop()
    except Exception as exc:
        import traceback
        traceback.print_exc()
        context.log_exception(
            "Exception during program initialization", exc)


if __name__ == "__main__":
    main()
