"""Styles tab.  Port of StylesPanel.

Six combat-style tabs of ability checkboxes with the same level
gating as the attributes tab.  There are no associated abilities
and no spell-list upkeep here.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from . import context
from .dbmodel import DBElement, DBList, ElementType
from .errors import DBException

_TAB_NAMES = ["Strong Steel", "Fast Steel", "Group Steel",
              "Strong Silver", "Fast Silver", "Group Silver"]


def _style_fields(name_a, name_b, name_c):
    return [
        ["Level 1", "Level 2", "Level 3", "Level 4", "Level 5"],
        [name_a + " I", name_a + " II", name_a + " III", "", ""],
        [name_b + " I", name_b + " II", name_b + " III", "", ""],
        [name_c + " I", name_c + " II", name_c + " III", "", ""],
    ]


_FIELD_NAMES = [
    _style_fields("Cut at the Jugular", "Crushing Blow",
                  "Bloody Rage"),
    _style_fields("Paralysis", "Hail of Blows", "Sever Sinews"),
    _style_fields("Precise Hit", "Half-Spin", "Trip"),
    _style_fields("Deep Cut", "Mortal Blow", "Patinado"),
    _style_fields("Crippling Pain", "Flash Cuts", "Sinister"),
    _style_fields("Critical Hit", "Tempest", "Tempest"),
]


def _style_labels(prefix):
    return [
        [prefix + "1", prefix + "2", prefix + "3", prefix + "4",
         prefix + "5"],
        [prefix + "1 Upgrade1", prefix + "2 Upgrade1",
         prefix + "3 Upgrade1", "", ""],
        [prefix + "1 Upgrade2", prefix + "2 Upgrade2",
         prefix + "3 Upgrade2", "", ""],
        [prefix + "1 Upgrade3", prefix + "2 Upgrade3",
         prefix + "3 Upgrade3", "", ""],
    ]


_DATABASE_LABELS = [
    _style_labels("StyleSteelStrong"),
    _style_labels("StyleSteelFast"),
    _style_labels("StyleSteelGroup"),
    _style_labels("StyleSilverStrong"),
    _style_labels("StyleSilverFast"),
    _style_labels("StyleSilverGroup"),
]


class StylesPanel(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        self.tabs = len(_FIELD_NAMES)
        self.rows = len(_FIELD_NAMES[0])
        self.cols = len(_FIELD_NAMES[0][0])
        self.vars = [[[None] * self.cols for _ in range(self.rows)]
                     for _ in range(self.tabs)]
        self.levels = [0] * self.tabs
        self.label_map = {}

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)
        for tab in range(self.tabs):
            frame = ttk.Frame(notebook, padding=8)
            for row in range(self.rows):
                for col in range(self.cols):
                    name = _FIELD_NAMES[tab][row][col]
                    if name:
                        var = tk.BooleanVar()
                        check = ttk.Checkbutton(
                            frame, text=name, variable=var,
                            command=lambda t=tab, r=row, c=col:
                            self._on_toggle(t, r, c))
                        check.grid(row=row, column=col, sticky="w",
                                   padx=5, pady=5)
                        self.vars[tab][row][col] = var
                        self.label_map[
                            _DATABASE_LABELS[tab][row][col]] = (
                                tab, row, col)
            notebook.add(frame, text=_TAB_NAMES[tab])

    def _abilities(self):
        top = context.database.top_level_struct.value
        top = top.get_element("Mod_PlayerList").value
        player = top.get_element_at(0).value
        return player.get_element("CharAbilities").value

    def _on_toggle(self, tab, row, col):
        if context.data_changing:
            return
        try:
            var = self.vars[tab][row][col]
            ability_label = _DATABASE_LABELS[tab][row][col]
            abilities = self._abilities()

            if var.get():
                self._add(tab, row, col, ability_label, abilities,
                          var)
            else:
                self._remove(tab, row, col, ability_label,
                             abilities, var)
        except DBException as exc:
            context.log_exception(
                "Unable to update database field", exc)
        except Exception as exc:
            context.log_exception(
                "Exception while processing action event", exc)

    def _add(self, tab, row, col, ability_label, abilities, var):
        add_ability = True
        if row == 0:
            if col > self.levels[tab] + 1:
                messagebox.showwarning(
                    "Missing level",
                    "Lower ability level must be obtained first",
                    parent=self)
                add_ability = False
        elif col > self.levels[tab]:
            messagebox.showwarning(
                "Missing level",
                "The ability level must be obtained first",
                parent=self)
            add_ability = False

        if add_ability:
            fields = DBList(2)
            fields.add_element(DBElement(
                ElementType.STRING, 0, "RnAbName", ability_label))
            fields.add_element(DBElement(
                ElementType.BYTE, 0, "RnAbStk", 0))
            abilities.add_element(DBElement(
                ElementType.STRUCT, 48879, "", fields))
            if row == 0 and col > self.levels[tab]:
                self.levels[tab] = col
            context.data_modified = True
        else:
            context.data_changing = True
            var.set(False)
            context.data_changing = False

    def _remove(self, tab, row, col, ability_label, abilities,
                var):
        remove_ability = True
        if row == 0:
            if col < self.levels[tab]:
                messagebox.showwarning(
                    "Higher level",
                    "All higher ability levels must be removed "
                    "first", parent=self)
                remove_ability = False
            else:
                for i in range(1, self.rows):
                    other = self.vars[tab][i][col]
                    if other is not None and other.get():
                        messagebox.showwarning(
                            "Ability upgrades",
                            "All ability level upgrades must be "
                            "removed first", parent=self)
                        remove_ability = False
                        break

        if remove_ability:
            count = abilities.element_count()
            for i in range(count):
                fields = abilities.get_element_at(i).value
                if fields.get_string("RnAbName") == ability_label:
                    abilities.remove_element_at(i)
                    context.data_modified = True
                    break
            if row == 0 and col == self.levels[tab]:
                self.levels[tab] = col - 1
        else:
            context.data_changing = True
            var.set(True)
            context.data_changing = False

    def set_fields(self, db_list):
        for tab in range(self.tabs):
            for row in range(self.rows):
                for col in range(self.cols):
                    var = self.vars[tab][row][col]
                    if var is not None:
                        var.set(False)
            self.levels[tab] = -1

        element = db_list.get_element("CharAbilities")
        if element is None:
            raise DBException("CharAbilities field not found")
        ability_list = element.value
        for index in range(ability_list.element_count()):
            fields = ability_list.get_element_at(index).value
            ability_name = fields.get_string("RnAbName")
            location = self.label_map.get(ability_name)
            if location is not None:
                tab, row, col = location
                self.vars[tab][row][col].set(True)
                if row == 0 and col > self.levels[tab]:
                    self.levels[tab] = col

    def get_fields(self, db_list):
        pass
