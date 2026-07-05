"""Difficulty tab.  Port of DifficultyPanel.

Three radio buttons.  Switching difficulty rewrites a difficulty
ability in the player abilities of both the module and player
databases and sets GameDiffSetting in the SMM database.  The
ability-rewrite mutates the tracked level between the two database
updates exactly as the original did.
"""

import tkinter as tk
from tkinter import ttk

from . import context
from .dbmodel import DBElement, DBList, ElementType
from .errors import DBException

_EASY = "Easy"
_MEDIUM = "Medium"
_HARD = "Hard"
_EASY_DIFF = "Difficulty_easy"
_MEDIUM_DIFF = "Difficulty_normal"


class DifficultyPanel(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        self.level = None
        self.var = tk.StringVar(value=_HARD)

        group = ttk.LabelFrame(self, text="Level", padding=10)
        group.pack()
        for text in (_EASY, _MEDIUM, _HARD):
            button = ttk.Radiobutton(
                group, text=text, value=text,
                variable=self.var, command=self._on_select)
            button.pack(side="left", padx=5)

    def _on_select(self):
        if context.data_changing:
            return
        cmd = self.var.get()
        if cmd == self.level:
            return

        top = context.database.top_level_struct.value
        mod = top.get_element("Mod_PlayerList").value
        mod_player = mod.get_element_at(0).value
        self._process_char_abilities(mod_player, cmd)

        player = context.player_database.top_level_struct.value
        self._process_char_abilities(player, cmd)

        smm = context.smm_database.top_level_struct.value
        self._process_game_diff(smm, cmd)

    def _process_char_abilities(self, db_list, cmd):
        try:
            ability_list = db_list.get_element(
                "CharAbilities").value

            if self.level in (_EASY, _MEDIUM):
                for i in range(ability_list.element_count()):
                    fields = ability_list.get_element_at(i).value
                    value = fields.get_element_at(0).value
                    if value in (_EASY_DIFF, _MEDIUM_DIFF):
                        if cmd == _EASY:
                            fields.set_string("RnAbName", _EASY_DIFF)
                        elif cmd == _MEDIUM:
                            fields.set_string("RnAbName",
                                              _MEDIUM_DIFF)
                        else:
                            ability_list.remove_element_at(i)
                        break
            else:
                for i in range(ability_list.element_count()):
                    fields = ability_list.get_element_at(i).value
                    value = fields.get_element_at(0).value
                    if value == "StyleSilverGroup1":
                        level_list = DBList(2)
                        if cmd == _EASY:
                            level_list.add_element(DBElement(
                                ElementType.STRING, 0, "RnAbName",
                                _EASY_DIFF))
                        elif cmd == _MEDIUM:
                            level_list.add_element(DBElement(
                                ElementType.STRING, 0, "RnAbName",
                                _MEDIUM_DIFF))
                        level_list.add_element(DBElement(
                            ElementType.BYTE, 0, "RnAbStk", 0))
                        ability_list.insert_element(
                            i + 1, DBElement(ElementType.STRUCT,
                                             48879, "", level_list))
                        break

            self.level = cmd
            context.data_modified = True
        except DBException as exc:
            context.log_exception(
                "Unable to update database field", exc)
        except Exception as exc:
            context.log_exception(
                "Exception while processing action event", exc)

    def _process_game_diff(self, db_list, cmd):
        try:
            if cmd == _EASY:
                db_list.set_integer("GameDiffSetting", 0)
            elif cmd == _MEDIUM:
                db_list.set_integer("GameDiffSetting", 1)
            else:
                db_list.set_integer("GameDiffSetting", 2)
        except DBException as exc:
            context.log_exception(
                "Unable to update database field", exc)
        except Exception as exc:
            context.log_exception(
                "Exception while processing action event", exc)

    def set_fields(self, db_list):
        self.level = _HARD
        self.var.set(_HARD)

        element = db_list.get_element("CharAbilities")
        if element is None:
            raise DBException("CharAbilities field not found")
        ability_list = element.value
        for i in range(ability_list.element_count()):
            fields = ability_list.get_element_at(i).value
            value = fields.get_element_at(0).value
            if value == _EASY_DIFF:
                self.level = _EASY
                self.var.set(_EASY)
                break
            if value == _MEDIUM_DIFF:
                self.level = _MEDIUM
                self.var.set(_MEDIUM)
                break

    def get_fields(self, db_list):
        pass
