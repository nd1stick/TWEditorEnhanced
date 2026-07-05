"""Quests tab.  Port of QuestsPanel.

Four lists bucket quests by state.  Examining a quest walks its
MainPhase phases (and nested subquest phases) to find the current
description, then shows it in the examine dialog.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from . import context
from .dialogs import show_examine_dialog
from .errors import DBException


class _QuestList:
    def __init__(self, notebook, title, examine, reset):
        self.quests = []
        frame = ttk.Frame(notebook, padding=8)
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(list_frame, height=26, width=40,
                                  activestyle="none",
                                  exportselection=False)
        scroll = ttk.Scrollbar(list_frame, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scroll.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=5)
        ttk.Button(button_frame, text="Examine",
                   command=examine).pack(side="left", padx=3)
        ttk.Button(button_frame, text="Reset",
                   command=reset).pack(side="left", padx=3)
        notebook.add(frame, text=title)

    def set_quests(self, quests):
        self.quests = quests
        self.listbox.delete(0, "end")
        for quest in quests:
            self.listbox.insert("end", quest.quest_name)
        self.listbox.selection_clear(0, "end")

    def selected(self):
        selection = self.listbox.curselection()
        if not selection:
            return None
        return self.quests[selection[0]]

    def remove_at(self, index):
        del self.quests[index]
        self.listbox.delete(index)
        self.listbox.selection_clear(0, "end")

    def insert_sorted(self, quest):
        name = quest.quest_name
        index = 0
        while index < len(self.quests):
            if name < self.quests[index].quest_name:
                break
            index += 1
        self.quests.insert(index, quest)
        self.listbox.insert(index, quest.quest_name)


class QuestsPanel(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)
        self.started = _QuestList(
            notebook, "Started",
            examine=lambda: self._examine(self.started),
            reset=lambda: self._reset(self.started))
        self.completed = _QuestList(
            notebook, "Completed",
            examine=lambda: self._examine(self.completed),
            reset=lambda: self._reset(self.completed))
        self.failed = _QuestList(
            notebook, "Failed",
            examine=lambda: self._examine(self.failed),
            reset=lambda: self._reset(self.failed))
        self.not_started = _QuestList(
            notebook, "Not Started",
            examine=lambda: self._examine(self.not_started),
            reset=lambda: self._reset(self.not_started))

    def _examine(self, quest_list):
        try:
            quest = quest_list.selected()
            if quest is None:
                messagebox.showwarning(
                    "No quest selected",
                    "You must select a quest to examine",
                    parent=self)
                return
            self._examine_quest(quest)
        except DBException as exc:
            context.log_exception(
                "Unable to access database field", exc)
        except Exception as exc:
            context.log_exception(
                "Exception while processing action event", exc)

    def _reset(self, quest_list):
        try:
            selection = quest_list.listbox.curselection()
            if not selection:
                messagebox.showwarning(
                    "No quest selected",
                    "You must select a quest to reset",
                    parent=self)
                return
            index = selection[0]
            quest = quest_list.quests[index]

            if quest.quest_state == quest.QUEST_NOT_STARTED:
                messagebox.showinfo(
                    "Already Not Started",
                    "This quest is already in the Not Started "
                    "state.", parent=self)
                return

            if not messagebox.askokcancel(
                    "Reset Quest",
                    "Reset '" + quest.quest_name + "' to Not "
                    "Started?  The quest phase state will be "
                    "cleared and the quest will re-trigger in "
                    "game.", parent=self):
                return

            quest.reset()
            quest_list.remove_at(index)
            self.not_started.insert_sorted(quest)

            context.data_modified = True
            if context.main_window is not None:
                context.main_window.update_title(None)
        except DBException as exc:
            context.log_exception(
                "Unable to update database field", exc)
        except Exception as exc:
            context.log_exception(
                "Exception while processing action event", exc)

    def _examine_quest(self, quest):
        fields = quest.quest_element.value
        fields = fields.get_element("MainPhase").value
        fields = fields.get_element_at(0).value
        current_phase = fields.get_integer("CurrPhase")
        element = fields.get_element("Phases")
        if element is None or element.type != 15:
            raise DBException(
                "No phase list found for quest "
                + quest.resource_name)
        phase_list = element.value
        current_phase = min(current_phase,
                            phase_list.element_count())

        while current_phase > 0:
            phase_fields = phase_list.get_element_at(
                current_phase - 1).value
            subquest_fields = self._locate_subquest(phase_fields)
            if (phase_fields.get_integer("Completed") == 1
                    or phase_fields.get_integer("Failed") == 1) \
                    and len(phase_fields.get_string(
                        "LocDescription")) > 0:
                fields = phase_fields
                break
            if subquest_fields is not None:
                fields = subquest_fields
                break
            current_phase -= 1

        parts = []
        string = fields.get_string("LocPhaseName")
        parts.append("<b>")
        parts.append(string if len(string) > 0 else
                     quest.quest_name)
        parts.append("</b><br><br>")

        string = fields.get_string("LocDescription")
        if len(string) > 0:
            parts.append(string)
            parts.append("<br><br>")

        string = fields.get_string("LocShortDescript")
        if len(string) > 0:
            parts.append("<i>")
            parts.append(string)
            parts.append("</i><br><br>")

        parts.append("Quest file: ")
        parts.append(quest.resource_name)
        show_examine_dialog(context.main_window, quest.quest_name,
                            "".join(parts))

    def _locate_subquest(self, fields):
        result = None
        element = fields.get_element("Phases")
        if element is not None and element.type == 15:
            quest_list = element.value
            count = quest_list.element_count()
            for i in range(count - 1, -1, -1):
                quest_fields = quest_list.get_element_at(i).value
                subquest_fields = self._locate_subquest(
                    quest_fields)
                if subquest_fields is not None:
                    result = subquest_fields
                    break
                if (quest_fields.get_integer("Completed") == 1
                        or quest_fields.get_integer("Failed") == 1) \
                        and len(quest_fields.get_string(
                            "LocDescription")) > 0:
                    result = quest_fields
                    break
        return result

    def set_fields(self, db_list):
        started = []
        completed = []
        failed = []
        not_started = []
        for quest in context.quests:
            state = quest.quest_state
            if state == 1:
                self._insert(started, quest)
            elif state == 2:
                self._insert(completed, quest)
            elif state == 3:
                self._insert(failed, quest)
            elif state == 0:
                self._insert(not_started, quest)

        self.started.set_quests(started)
        self.completed.set_quests(completed)
        self.failed.set_quests(failed)
        self.not_started.set_quests(not_started)

    def get_fields(self, db_list):
        pass

    @staticmethod
    def _insert(quest_list, quest):
        name = quest.quest_name
        index = 0
        while index < len(quest_list):
            if name < quest_list[index].quest_name:
                break
            index += 1
        quest_list.insert(index, quest)
