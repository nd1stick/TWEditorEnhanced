"""Stats tab.  Port of StatsPanel.

A grid of numeric fields bound to character statistics.  This is
the one panel whose get_fields writes values back to the database;
the others apply their edits live as the user toggles controls.
"""

import tkinter as tk
from tkinter import ttk

from .guicommon import mark_modified
from .numeric import NumericField

_FIELD_NAMES = [
    ["Level", "Vitality", "Bronze Talents"],
    ["Experience", "Endurance", "Silver Talents"],
    ["Gold", "Toxicity", "Gold Talents"],
]

_DATABASE_NAMES = [
    ["ExpLevel", "CurrentHitPoints", "TalentBronze"],
    ["Experience", "CurrentEndurance", "TalentSilver"],
    ["Gold", "CurrentToxicity", "TalentGold"],
]


class StatsPanel(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        rows = len(_FIELD_NAMES)
        self.stat_fields = [[None] * 3 for _ in range(rows)]

        for i in range(rows):
            for j in range(3):
                name = _FIELD_NAMES[i][j]
                if name:
                    label = ttk.Label(self, text=name)
                    label.grid(row=2 * i, column=j, padx=20,
                               pady=(8, 0), sticky="w")
                    field = NumericField(self, columns=8)
                    field.add_change_listener(mark_modified)
                    field.grid(row=2 * i + 1, column=j, padx=20,
                               pady=(0, 8), sticky="w")
                    self.stat_fields[i][j] = field

    def set_fields(self, db_list):
        for i in range(len(_DATABASE_NAMES)):
            for j in range(3):
                field = self.stat_fields[i][j]
                if field is not None:
                    field.set_value(
                        db_list.get_integer(_DATABASE_NAMES[i][j]))

    def get_fields(self, db_list):
        for i in range(len(_DATABASE_NAMES)):
            for j in range(3):
                field = self.stat_fields[i][j]
                if field is not None:
                    db_list.set_integer(_DATABASE_NAMES[i][j],
                                        field.get_value())
