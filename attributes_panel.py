"""Attributes tab.  Port of AttributesPanel.

Four attribute tabs of ability checkboxes.  Toggling a box adds or
removes a character ability (and any associated hidden ability),
with level gating that mirrors the original: a base level needs the
prior level, an upgrade needs its base level, and removals require
higher levels and upgrades to be cleared first.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from . import context
from .dbmodel import DBElement, DBList, ElementType
from .errors import DBException

_TAB_NAMES = ["Strength", "Dexterity", "Stamina", "Intelligence"]

_FIELD_NAMES = [
    [["Level 1", "Level 2", "Level 3", "Level 4", "Level 5"],
     ["Buzz", "Position", "Vigor", "Bleeding Resistance",
      "Wound Resistance"],
     ["True Grit", "Regeneration", "Knockdown Resistance",
      "Stone Skin", "Added Vitality"],
     ["", "Brawl", "Survival Instinct", "Aggression", ""]],
    [["Level 1", "Level 2", "Level 3", "Level 4", "Level 5"],
     ["Flaying", "Deflect Arrows", "Bleeding Resistance",
      "Finesse", "Vigilance"],
     ["Predator", "Repel", "Agility", "Feint", "Precision"],
     ["", "Fistfight", "Limit Incineration",
      "Incineration Resistance", ""]],
    [["Level 1", "Level 2", "Level 3", "Level 4", "Level 5"],
     ["Heavyweight", "Absorption", "Endurance Regeneration",
      "Stun Resistance", "Potion Tolerance"],
     ["Mutation", "Poison Resistance", "Pain Resistance",
      "Brawn", "Added Endurance"],
     ["", "Endurance Regeneration", "Revive",
      "Altered Metabolism", ""]],
    [["Level 1", "Level 2", "Level 3", "Level 4", "Level 5"],
     ["Potion Brewing", "Herbalism", "Cleansing Ritual",
      "Focus", "Mental Endurance"],
     ["Rising Moon", "Monster Lore", "Ingredient Extraction",
      "Life Ritual", "Intensity"],
     ["", "Oil Preparation", "Bomb Preparation",
      "Magic Frenzy", ""]],
]

_DATABASE_LABELS = [
    [["Strength1", "Strength2", "Strength3", "Strength4",
      "Strength5"],
     ["Strength1 Upgrade1", "Strength2 Upgrade1",
      "Strength3 Upgrade1", "Strength4 Upgrade1",
      "Strength5 Upgrade1"],
     ["Strength1 Upgrade2", "Strength2 Upgrade2",
      "Strength3 Upgrade2", "Strength4 Upgrade2",
      "Strength5 Upgrade2"],
     ["", "Strength2 Upgrade3", "Strength3 Upgrade3",
      "Strength4 Upgrade3", ""]],
    [["Dexterity1", "Dexterity2", "Dexterity3", "Dexterity4",
      "Dexterity5"],
     ["Dexterity1 Upgrade1", "Dexterity2 Upgrade1",
      "Dexterity3 Upgrade1", "Dexterity4 Upgrade1",
      "Dexterity5 Upgrade1"],
     ["Dexterity1 Upgrade2", "Dexterity2 Upgrade2",
      "Dexterity3 Upgrade2", "Dexterity4 Upgrade2",
      "Dexterity5 Upgrade2"],
     ["", "Dexterity2 Upgrade3", "Dexterity3 Upgrade3",
      "Dexterity4 Upgrade3", ""]],
    [["Endurance1", "Endurance2", "Endurance3", "Endurance4",
      "Endurance5"],
     ["Endurance1 Upgrade1", "Endurance2 Upgrade1",
      "Endurance3 Upgrade1", "Endurance4 Upgrade1",
      "Endurance5 Upgrade1"],
     ["Endurance1 Upgrade2", "Endurance2 Upgrade2",
      "Endurance3 Upgrade2", "Endurance4 Upgrade2",
      "Endurance5 Upgrade2"],
     ["", "Endurance2 Upgrade3", "Endurance3 Upgrade3",
      "Endurance4 Upgrade3", ""]],
    [["Intelligence1", "Intelligence2", "Intelligence3",
      "Intelligence4", "Intelligence5"],
     ["Intelligence1 Upgrade1", "Intelligence2 Upgrade1",
      "Intelligence3 Upgrade1", "Intelligence4 Upgrade1",
      "Intelligence5 Upgrade1"],
     ["Intelligence1 Upgrade2", "Intelligence2 Upgrade2",
      "Intelligence3 Upgrade2", "Intelligence4 Upgrade2",
      "Intelligence5 Upgrade2"],
     ["", "Intelligence2 Upgrade3", "Intelligence3 Upgrade3",
      "Intelligence4 Upgrade3", ""]],
]

_ASSOCIATED_LABELS = [
    ["Dexterity1 Upgrade1", "Skinning"],
    ["Intelligence2 Upgrade1", "HerbGathering"],
    ["Intelligence2 Upgrade3", "GreaseMaking"],
    ["Intelligence3 Upgrade1", "RitualOfPurify"],
    ["Intelligence3 Upgrade2", "Anatomy"],
    ["Intelligence3 Upgrade3", "BombMaking"],
    ["Intelligence4 Upgrade2", "RitualOfLife"],
]

_BYPASS_LEVEL_REQUIREMENTS = {
    "Dexterity1 Upgrade1",      # Flaying
    "Intelligence1 Upgrade1",   # Potion Brewing
}

class AttributesPanel(ttk.Frame):
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

        if ability_label not in _BYPASS_LEVEL_REQUIREMENTS:
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
            self._append_ability(abilities, ability_label)
            for entry in _ASSOCIATED_LABELS:
                if ability_label == entry[0]:
                    self._append_ability(abilities, entry[1])
                    break
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
            self._delete_ability(abilities, ability_label)
            for entry in _ASSOCIATED_LABELS:
                if ability_label == entry[0]:
                    self._delete_ability(abilities, entry[1])
                    break
            if row == 0 and self.levels[tab] == col:
                self.levels[tab] = col - 1
        else:
            context.data_changing = True
            var.set(True)
            context.data_changing = False

    @staticmethod
    def _append_ability(abilities, ability_label):
        fields = DBList(2)
        fields.add_element(DBElement(
            ElementType.STRING, 0, "RnAbName", ability_label))
        fields.add_element(DBElement(
            ElementType.BYTE, 0, "RnAbStk", 0))
        abilities.add_element(DBElement(
            ElementType.STRUCT, 48879, "", fields))

    @staticmethod
    def _delete_ability(abilities, ability_label):
        count = abilities.element_count()
        for i in range(count):
            fields = abilities.get_element_at(i).value
            if fields.get_string("RnAbName") == ability_label:
                abilities.remove_element_at(i)
                context.data_modified = True
                return

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
