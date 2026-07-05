"""Main application window.  Port of MainWindow.java.

Holds the menu bar and the eight editor tabs.  The tab area stays
hidden until a save loads.  File operations run their work on a
background task behind a modal progress dialog and then refresh the
panels from the loaded databases.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import context
from .attributes_panel import AttributesPanel
from .difficulty_panel import DifficultyPanel
from .dialogs import ProgressDialog
from .equip_panel import EquipPanel
from .errors import DBException
from .guicommon import flush_errors
from .inventory_panel import InventoryPanel
from .quests_panel import QuestsPanel
from .signs_panel import SignsPanel
from .stats_panel import StatsPanel
from .styles_panel import StylesPanel
from .tasks import LoadFile, PackFile, SaveFile, UnpackSave

_TITLE = "The Witcher Save Editor"
_VERSION = "3.0.1"


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(_TITLE)
        self.title_modified = False
        self.window_minimized = False

        width = 800
        height = 600
        value = context.properties.get("window.main.size")
        if value is not None:
            parts = value.split(",")
            width = max(int(parts[0]), width)
            height = max(int(parts[1]), height)
        geometry = "%dx%d" % (width, height)
        value = context.properties.get("window.main.position")
        if value is not None:
            parts = value.split(",")
            geometry += "+%d+%d" % (int(parts[0]), int(parts[1]))
        self.geometry(geometry)
        self.minsize(800, 600)

        self._build_menu()

        self.notebook = ttk.Notebook(self)
        self.stats_panel = StatsPanel(self.notebook)
        self.attributes_panel = AttributesPanel(self.notebook)
        self.signs_panel = SignsPanel(self.notebook)
        self.styles_panel = StylesPanel(self.notebook)
        self.equip_panel = EquipPanel(self.notebook)
        self.inventory_panel = InventoryPanel(self.notebook)
        self.quests_panel = QuestsPanel(self.notebook)
        self.difficulty_panel = DifficultyPanel(self.notebook)
        self.notebook.add(self.stats_panel, text="Stats")
        self.notebook.add(self.attributes_panel, text="Attributes")
        self.notebook.add(self.signs_panel, text="Signs")
        self.notebook.add(self.styles_panel, text="Styles")
        self.notebook.add(self.equip_panel, text="Equipment")
        self.notebook.add(self.inventory_panel, text="Inventory")
        self.notebook.add(self.quests_panel, text="Quests")
        self.notebook.add(self.difficulty_panel, text="Difficulty")
        self.notebook_visible = False

        self.protocol("WM_DELETE_WINDOW", self.exit_program)
        self.bind("<Unmap>", self._on_unmap)
        self.bind("<Map>", self._on_map)

    def _build_menu(self):
        menu_bar = tk.Menu(self)

        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Open", command=self.open_file)
        file_menu.add_command(label="Save", command=self.save_file)
        file_menu.add_command(label="Close",
                              command=self._close_command)
        file_menu.add_separator()
        file_menu.add_command(label="Exit",
                              command=self.exit_program)
        menu_bar.add_cascade(label="File", menu=file_menu)

        actions_menu = tk.Menu(menu_bar, tearoff=0)
        actions_menu.add_command(label="Unpack Save",
                                 command=self.unpack_save)
        actions_menu.add_command(label="Repack Save",
                                 command=self.pack_save)
        menu_bar.add_cascade(label="Actions", menu=actions_menu)

        help_menu = tk.Menu(menu_bar, tearoff=0)
        help_menu.add_command(label="About",
                              command=self.about_program)
        menu_bar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menu_bar)

    def _on_unmap(self, event):
        if event.widget is self:
            self.window_minimized = True

    def _on_map(self, event):
        if event.widget is self:
            self.window_minimized = False

    def _show_notebook(self):
        if not self.notebook_visible:
            self.notebook.pack(fill="both", expand=True)
            self.notebook_visible = True

    def _hide_notebook(self):
        if self.notebook_visible:
            self.notebook.pack_forget()
            self.notebook_visible = False

    def update_title(self, title):
        if title is not None:
            self.title(title)
            self.title_modified = False
        elif context.save_database is None:
            self.title(_TITLE)
            self.title_modified = False
        elif context.data_modified and not self.title_modified:
            self.title(_TITLE + " - "
                       + context.save_database.get_name() + "*")
            self.title_modified = True
        elif not context.data_modified and self.title_modified:
            self.title(_TITLE + " - "
                       + context.save_database.get_name())
            self.title_modified = False

    # -- menu commands -------------------------------------------

    def _close_command(self):
        if context.save_database is None:
            messagebox.showerror("No Save",
                                 "No save file is open", parent=self)
            return
        self.close_file()
        self.update_title(None)

    def open_file(self):
        try:
            if not self.close_file():
                return

            current = context.properties.get("current.directory")
            if current is None or not os.path.isdir(current):
                current = os.path.join(context.game_path, "saves")

            path = filedialog.askopenfilename(
                parent=self, title="Select Save File",
                initialdir=current,
                filetypes=[("Witcher saves", "*.TheWitcherSave"),
                           ("All files", "*.*")])
            if not path:
                return
            context.properties["current.directory"] = \
                os.path.dirname(path)
            self.load_save(path)

            if context.save_database is not None:
                self.update_title(
                    _TITLE + " - "
                    + context.save_database.get_name())
            else:
                self.update_title(None)
        except Exception as exc:
            context.log_exception(
                "Exception while processing action event", exc)
            flush_errors(self)

    def load_save(self, path):
        save_name = os.path.basename(path)
        dot = save_name.rfind(".")
        if dot > 0:
            save_name = save_name[:dot]

        dialog = ProgressDialog(self, "Loading " + save_name)
        task = LoadFile(dialog, path)
        task.start()
        success = dialog.show_dialog()
        flush_errors(self)

        if success:
            try:
                context.data_changing = True

                top = context.database.top_level_struct.value
                top = top.get_element("Mod_PlayerList").value
                player = top.get_element_at(0).value

                self.stats_panel.set_fields(player)
                self.attributes_panel.set_fields(player)
                self.signs_panel.set_fields(player)
                self.styles_panel.set_fields(player)
                self.equip_panel.set_fields(player)
                self.inventory_panel.set_fields(player)
                self.quests_panel.set_fields(player)
                self.difficulty_panel.set_fields(player)

                self.notebook.select(0)
                self._show_notebook()

                context.data_changing = False
                context.data_modified = False
            except DBException as exc:
                context.log_exception(
                    "Database format is not valid", exc)
                flush_errors(self)
            except Exception as exc:
                context.log_exception(
                    "I/O error while building tabbed panes", exc)
                flush_errors(self)

    def save_file(self):
        if context.save_database is None:
            messagebox.showerror("No Save",
                                 "No save file is open", parent=self)
            return False
        saved = False
        try:
            top = context.database.top_level_struct.value
            top = top.get_element("Mod_PlayerList").value
            player = top.get_element_at(0).value
            self.stats_panel.get_fields(player)
            self.attributes_panel.get_fields(player)
            self.signs_panel.get_fields(player)
            self.styles_panel.get_fields(player)
            self.equip_panel.get_fields(player)
            self.inventory_panel.get_fields(player)
            self.quests_panel.get_fields(player)
            self.difficulty_panel.get_fields(player)

            dialog = ProgressDialog(
                self, "Saving " + context.save_database.get_name())
            task = SaveFile(dialog)
            task.start()
            saved = dialog.show_dialog()
            flush_errors(self)
            if saved:
                context.data_modified = False
        except DBException as exc:
            context.log_exception(
                "Database format is not valid", exc)
            flush_errors(self)
        self.update_title(None)
        return saved

    def close_file(self):
        if context.save_database is None:
            return True

        if context.data_modified:
            option = messagebox.askyesnocancel(
                "Save Modified",
                "The current save has been modified.  Do you want "
                "to save the changes?", parent=self)
            if option is None:
                return False
            if option and not self.save_file():
                return False

        context.database = None
        context.mod_database = None
        context.save_database = None
        context.data_modified = False
        self._hide_notebook()
        return True

    def unpack_save(self):
        if context.save_database is None:
            messagebox.showerror("No Save",
                                 "No save file is open", parent=self)
            return
        try:
            extract = context.properties.get("extract.directory")
            initial = extract if (extract
                                  and os.path.isdir(extract)) else None
            directory = filedialog.askdirectory(
                parent=self, title="Select Destination Directory",
                initialdir=initial)
            if not directory:
                return
            context.properties["extract.directory"] = directory
            if not os.path.exists(directory):
                os.makedirs(directory)

            dialog = ProgressDialog(
                self,
                "Unpacking " + context.save_database.get_name())
            task = UnpackSave(dialog, directory)
            task.start()
            success = dialog.show_dialog()
            flush_errors(self)
            if success:
                messagebox.showinfo(
                    "Save Unpacked",
                    "Save game unpacked to " + directory,
                    parent=self)
        except Exception as exc:
            context.log_exception(
                "Exception while processing action event", exc)
            flush_errors(self)

    def pack_save(self):
        if context.save_database is None:
            messagebox.showerror("No Save",
                                 "No save file is open", parent=self)
            return
        try:
            if context.data_modified:
                proceed = messagebox.askokcancel(
                    "Save Modified",
                    "The current save has been modified and these "
                    "changes will be lost.  Do you want to "
                    "continue?", parent=self)
                if not proceed:
                    return

            extract = context.properties.get("extract.directory")
            initial = extract if (extract
                                  and os.path.isdir(extract)) else None
            directory = filedialog.askdirectory(
                parent=self, title="Select Source Directory",
                initialdir=initial)
            if not directory:
                return
            context.properties["extract.directory"] = directory
            if not os.path.exists(directory):
                messagebox.showerror(
                    "Directory not found",
                    "Source directory does not exist", parent=self)
                return

            context.data_modified = False
            dialog = ProgressDialog(
                self, "Packing " + context.save_database.get_name())
            task = PackFile(dialog, directory)
            task.start()
            saved = dialog.show_dialog()
            flush_errors(self)

            path = context.save_database.file
            self.close_file()
            if saved:
                self.load_save(path)
            self.update_title(None)
        except Exception as exc:
            context.log_exception(
                "Exception while processing action event", exc)
            flush_errors(self)

    def exit_program(self):
        try:
            self.close_file()

            if context.mod_file and os.path.exists(context.mod_file):
                os.remove(context.mod_file)
            if context.database_file \
                    and os.path.exists(context.database_file):
                os.remove(context.database_file)

            if not self.window_minimized:
                self.update_idletasks()
                x = self.winfo_x()
                y = self.winfo_y()
                w = self.winfo_width()
                h = self.winfo_height()
                context.properties["window.main.position"] = \
                    "%d,%d" % (x, y)
                context.properties["window.main.size"] = \
                    "%d,%d" % (w, h)

            self._save_properties()
        except Exception as exc:
            context.log_exception(
                "Exception while closing application window", exc)
        self.destroy()

    def about_program(self):
        lines = [
            _TITLE + " Version " + _VERSION,
            "",
            "User name: " + os.environ.get("USER",
                                           os.environ.get(
                                               "USERNAME", "")),
            "Home directory: " + os.path.expanduser("~"),
            "",
            "TW install path: " + str(context.install_path),
            "TW data path: " + str(context.game_path),
            "Temporary data path: " + str(context.tmp_dir),
            "Language identifier: " + str(context.language_id),
        ]
        messagebox.showinfo("About " + _TITLE, "\n".join(lines),
                            parent=self)

    def _save_properties(self):
        if context.prop_file is None:
            return
        try:
            directory = os.path.dirname(context.prop_file)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
            with open(context.prop_file, "w",
                      encoding="latin-1") as out:
                for key in sorted(context.properties):
                    out.write(key + "="
                              + context.properties[key] + "\n")
        except OSError as exc:
            context.log_exception("Unable to save properties", exc)
