"""Signs tab.  Port of SignsPanel.

Five sign tabs.  Toggling a box manages a character ability and,
for the level and powerup rows, the matching entry in the player's
KnownList0 spell list.  Note the Axii tab uses the database prefix
"Axi" rather than "Axii".
"""

import tkinter as tk
from tkinter import messagebox, ttk

from . import context
from .dbmodel import DBElement, DBList, ElementType
from .errors import DBException

_TAB_NAMES = ["Aard", "Igni", "Quen", "Axii", "Yrden"]

_FIELD_NAMES = [
    [["Level 1", "Level 2", "Level 3", "Level 4", "Level 5"],
     ["Student", "Apprentice", "Specialist", "Expert", "Master"],
     ["Stun", "Disarm", "Blasting Fist", "Extended Duration",
      "Gale"],
     ["", "Gust", "Thunder", "Added Efficiency", ""]],
    [["Level 1", "Level 2", "Level 3", "Level 4", "Level 5"],
     ["Student", "Apprentice", "Specialist", "Expert", "Master"],
     ["Harm's Way I", "Harm's Way II", "Burning Blade",
      "Inferno", "Extended Duration"],
     ["", "Incineration", "Wall of Fire", "Added Efficiency", ""]],
    [["Level 1", "Level 2", "Level 3", "Level 4", "Level 5"],
     ["Student", "Apprentice", "Specialist", "Expert", "Master"],
     ["Barrier I", "Barrier II", "Barrier III", "Survival Zone",
      "Resonance"],
     ["", "Extended Duration", "Added Intensity",
      "Added Efficiency", ""]],
    [["Level 1", "Level 2", "Level 3", "Level 4", "Level 5"],
     ["Student", "Apprentice", "Specialist", "Expert", "Master"],
     ["Spell", "Hypnosis", "Faze", "Terror", "Ally"],
     ["", "Extended Duration I", "Extended Duration II",
      "Added Efficiency", ""]],
    [["Level 1", "Level 2", "Level 3", "Level 4", "Level 5"],
     ["Student", "Apprentice", "Specialist", "Expert", "Master"],
     ["Pain Sign", "Prowess", "Stupor Sign", "Blinding Sign",
      "Circle of Death"],
     ["", "Inscriptions", "Crippling Sign", "Added Efficiency",
      ""]],
]


def _sign_labels(prefix):
    return [
        [prefix + "1", prefix + "2", prefix + "3", prefix + "4",
         prefix + "5"],
        [prefix + "1 Powerup", prefix + "2 Powerup",
         prefix + "3 Powerup", prefix + "4 Powerup",
         prefix + "5 Powerup"],
        [prefix + "1 Upgrade1", prefix + "2 Upgrade1",
         prefix + "3 Upgrade1", prefix + "4 Upgrade1",
         prefix + "5 Upgrade1"],
        ["", prefix + "2 Upgrade2", prefix + "3 Upgrade2",
         prefix + "4 Upgrade2", ""],
    ]


_DATABASE_LABELS = [
    _sign_labels("Aard"), _sign_labels("Igni"),
    _sign_labels("Quen"), _sign_labels("Axi"),
    _sign_labels("Yrden"),
]

_ASSOCIATED_SPELLS = [0, 3, 1, 4, 2]


class SignsPanel(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        self.tabs = len(_FIELD_NAMES)
        self.rows = len(_FIELD_NAMES[0])
        self.cols = len(_FIELD_NAMES[0][0])
        self.vars = [[[None] * self.cols for _ in range(self.rows)]
                     for _ in range(self.tabs)]
        self.sign_levels = [[-1, -1] for _ in range(self.tabs)]
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

    def _player_and_abilities(self):
        top = context.database.top_level_struct.value
        top = top.get_element("Mod_PlayerList").value
        player = top.get_element_at(0).value
        abilities = player.get_element("CharAbilities").value
        return player, abilities

    def _on_toggle(self, tab, row, col):
        if context.data_changing:
            return
        try:
            var = self.vars[tab][row][col]
            ability_label = _DATABASE_LABELS[tab][row][col]
            player, abilities = self._player_and_abilities()

            if var.get():
                self._add(tab, row, col, ability_label, player,
                          abilities, var)
            else:
                self._remove(tab, row, col, ability_label, player,
                             abilities, var)
        except DBException as exc:
            context.log_exception(
                "Unable to update database field", exc)
        except Exception as exc:
            context.log_exception(
                "Exception while processing action event", exc)

    def _add(self, tab, row, col, ability_label, player, abilities,
             var):
        add_sign = True
        if row == 0:
            if col > self.sign_levels[tab][0] + 1:
                messagebox.showwarning(
                    "Missing level",
                    "Lower sign level must be obtained first",
                    parent=self)
                add_sign = False
        elif row == 1:
            if col > self.sign_levels[tab][1] + 1:
                messagebox.showwarning(
                    "Missing powerup",
                    "Lower sign level powerup must be obtained "
                    "first", parent=self)
                add_sign = False
        elif col > self.sign_levels[tab][0]:
            messagebox.showwarning(
                "Missing level",
                "The sign level must be obtained first",
                parent=self)
            add_sign = False

        if add_sign:
            fields = DBList(2)
            fields.add_element(DBElement(
                ElementType.STRING, 0, "RnAbName", ability_label))
            fields.add_element(DBElement(
                ElementType.BYTE, 0, "RnAbStk", 0))
            abilities.add_element(DBElement(
                ElementType.STRUCT, 48879, "", fields))

            if row < 2 and col > self.sign_levels[tab][row]:
                self._add_spell(tab, row, col, player)
                self.sign_levels[tab][row] = col

            context.data_modified = True
        else:
            context.data_changing = True
            var.set(False)
            context.data_changing = False

    def _add_spell(self, tab, row, col, player):
        updated = False
        low = _ASSOCIATED_SPELLS[tab] * 10
        high = low + 9
        known = None
        element = player.get_element("KnownList0")
        if element is not None:
            known = element.value
            for i in range(known.element_count()):
                fields = known.get_element_at(i).value
                spell = fields.get_integer("Spell")
                if low <= spell <= high and (spell & 0x1) == row:
                    fields.set_integer("Spell", low + 2 * col + row)
                    updated = True
                    break

        if not updated:
            if known is None:
                known = DBList(1)
                player.add_element(DBElement(
                    ElementType.LIST, 0, "KnownList0", known))
            fields = DBList(1)
            fields.add_element(DBElement(
                ElementType.WORD, 0, "Spell", low + 2 * col + row))
            known.add_element(DBElement(
                ElementType.STRUCT, 2, "", fields))

    def _remove(self, tab, row, col, ability_label, player,
                abilities, var):
        remove_sign = True
        if row == 0:
            if col < self.sign_levels[tab][0]:
                messagebox.showwarning(
                    "Higher level",
                    "All higher sign levels must be removed first",
                    parent=self)
                remove_sign = False
            else:
                for i in range(1, self.rows):
                    other = self.vars[tab][i][col]
                    if other is not None and other.get():
                        messagebox.showwarning(
                            "Sign upgrades",
                            "All sign level upgrades must be "
                            "removed first", parent=self)
                        remove_sign = False
                        break
        elif row == 1 and col < self.sign_levels[tab][1]:
            messagebox.showwarning(
                "Higher powerup",
                "All higher sign powerups must be removed first",
                parent=self)
            remove_sign = False

        if remove_sign:
            count = abilities.element_count()
            for i in range(count):
                fields = abilities.get_element_at(i).value
                if fields.get_string("RnAbName") == ability_label:
                    abilities.remove_element_at(i)
                    context.data_modified = True
                    break

            if row < 2 and col == self.sign_levels[tab][row]:
                self._remove_spell(tab, row, col, player)
                self.sign_levels[tab][row] = col - 1
                context.data_modified = True
        else:
            context.data_changing = True
            var.set(True)
            context.data_changing = False

    def _remove_spell(self, tab, row, col, player):
        low = _ASSOCIATED_SPELLS[tab] * 10
        high = low + 9
        element = player.get_element("KnownList0")
        if element is not None:
            known = element.value
            for i in range(known.element_count()):
                fields = known.get_element_at(i).value
                spell = fields.get_integer("Spell")
                if low <= spell <= high and (spell & 0x1) == row:
                    if col == 0:
                        known.remove_element_at(i)
                        break
                    fields.set_integer("Spell", spell - 2)
                    break

    def set_fields(self, db_list):
        for tab in range(self.tabs):
            for row in range(self.rows):
                for col in range(self.cols):
                    var = self.vars[tab][row][col]
                    if var is not None:
                        var.set(False)
            self.sign_levels[tab][0] = -1
            self.sign_levels[tab][1] = -1

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
                if row < 2 and col > self.sign_levels[tab][row]:
                    self.sign_levels[tab][row] = col

    def get_fields(self, db_list):
        pass
