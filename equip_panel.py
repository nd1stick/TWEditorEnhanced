"""Equipment tab.  Port of EquipPanel.

Left: the current equipment list with examine/remove.  Right: a
category tree of available item templates with examine/add.  Adding
clones the template, marks it dropable and identified, sets the
stack size and enforces the weapon-slot limits.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from . import context
from .dbmodel import DBElement, DBList, ElementType
from .dialogs import show_examine_dialog
from .errors import DBException
from .model import InventoryItem

_CATEGORIES = ["Armor", "Silver Sword", "Steel Sword", "Trophy"]
_CATEGORY_MAPPINGS = [[1, 2], [2, 1], [29, 0], [39, 3]]


class EquipPanel(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        self.items = []
        self.templates = {}
        self.avail_done = False

        items_pane = ttk.Frame(self)
        ttk.Label(items_pane, text="Current Inventory",
                  anchor="center").pack(fill="x")
        list_frame = ttk.Frame(items_pane)
        list_frame.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(list_frame, height=20, width=35,
                                  activestyle="none",
                                  exportselection=False)
        scroll = ttk.Scrollbar(list_frame, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scroll.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        button_pane = ttk.Frame(items_pane)
        button_pane.pack()
        ttk.Button(button_pane, text="Examine Item",
                   command=self._examine_current).pack(side="left",
                                                       padx=3)
        ttk.Button(button_pane, text="Remove Item",
                   command=self._remove_selected).pack(side="left",
                                                       padx=3)

        avail_pane = ttk.Frame(self)
        ttk.Label(avail_pane, text="Available Items",
                  anchor="center").pack(fill="x")
        tree_frame = ttk.Frame(avail_pane)
        tree_frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tree_frame, show="tree",
                                 height=20, selectmode="browse")
        tree_scroll = ttk.Scrollbar(tree_frame,
                                    command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        avail_buttons = ttk.Frame(avail_pane)
        avail_buttons.pack()
        ttk.Button(avail_buttons, text="Examine Item",
                   command=self._examine_available).pack(
                       side="left", padx=3)
        ttk.Button(avail_buttons, text="Add Item",
                   command=self._add_selected).pack(side="left",
                                                    padx=3)

        items_pane.pack(side="left", fill="both", expand=True)
        ttk.Frame(self, width=15).pack(side="left")
        avail_pane.pack(side="left", fill="both", expand=True)

        self.category_iids = []
        for category in _CATEGORIES:
            iid = self.tree.insert("", "end", text=category,
                                   open=False)
            self.category_iids.append(iid)

    # -- player helpers ------------------------------------------

    def _player(self):
        top = context.database.top_level_struct.value
        top = top.get_element("Mod_PlayerList").value
        return top.get_element_at(0).value

    # -- examine -------------------------------------------------

    def _examine_current(self):
        try:
            selection = self.listbox.curselection()
            if not selection:
                messagebox.showwarning(
                    "No item selected",
                    "You must select an item to examine",
                    parent=self)
                return
            item = self.items[selection[0]]
            self._examine_item(item.name, item.element.value)
        except DBException as exc:
            context.log_exception(
                "Unable to process database field", exc)
        except Exception as exc:
            context.log_exception(
                "Exception while processing action event", exc)

    def _examine_available(self):
        try:
            template = self._selected_template()
            if template is None:
                messagebox.showwarning(
                    "No item selected",
                    "You must select an item to examine",
                    parent=self)
                return
            self._examine_item(template.item_name,
                               template.field_list)
        except DBException as exc:
            context.log_exception(
                "Unable to process database field", exc)
        except Exception as exc:
            context.log_exception(
                "Exception while processing action event", exc)

    def _examine_item(self, label, field_list):
        string = field_list.get_string("DescIdentified")
        if len(string) == 0:
            string = field_list.get_string("Description")
        show_examine_dialog(context.main_window, label, string)

    def _selected_template(self):
        selection = self.tree.selection()
        if not selection:
            return None
        return self.templates.get(selection[0])

    # -- add / remove --------------------------------------------

    def _remove_selected(self):
        try:
            selection = self.listbox.curselection()
            if not selection:
                messagebox.showwarning(
                    "No item selected",
                    "You must select an item to remove",
                    parent=self)
                return
            index = selection[0]
            item = self.items[index]
            item_element = item.element

            del self.items[index]
            self.listbox.delete(index)
            self.listbox.selection_clear(0, "end")

            item_list = self._player().get_element(
                "Equip_ItemList").value
            for i in range(item_list.element_count()):
                if item_list.get_element_at(i) is item_element:
                    item_list.remove_element_at(i)
                    break

            context.data_modified = True
            context.main_window.update_title(None)
        except DBException as exc:
            context.log_exception(
                "Unable to process database field", exc)
        except Exception as exc:
            context.log_exception(
                "Exception while processing action event", exc)

    def _add_selected(self):
        try:
            template = self._selected_template()
            if template is None:
                messagebox.showwarning(
                    "No item selected",
                    "You must select an item to add", parent=self)
                return

            template_list = template.field_list
            weapon_slot = template_list.get_integer("WeaponSlot")
            player = self._player()

            element = player.get_element("Equip_ItemList")
            if element is not None:
                sword_count = 0
                item_list = element.value
                for i in range(item_list.element_count()):
                    item_fields = item_list.get_element_at(i).value
                    if item_fields.get_integer("WeaponSlot") \
                            == weapon_slot:
                        if weapon_slot == 1:
                            sword_count += 1
                        if weapon_slot != 1 or sword_count == 2:
                            messagebox.showwarning(
                                "No slot",
                                "No equipment slot available for "
                                "this item", parent=self)
                            return

            # The original tool added a full stack (MaxStack,
            # often 25); default the added quantity to 1.
            stack_size = 1
            field_list = template_list.clone()
            field_list.set_integer("Dropable", 1, ElementType.BYTE)
            field_list.set_integer("Identified", 1,
                                   ElementType.BYTE)
            field_list.set_integer("StackSize", stack_size,
                                   ElementType.WORD)

            element = player.get_element("Equip_ItemList")
            if element is None:
                item_list = DBList(10)
                element = DBElement(ElementType.LIST, 0,
                                    "Equip_ItemList", item_list)
                player.add_element(element)
            else:
                item_list = element.value

            element = DBElement(ElementType.STRUCT, 0, "",
                                field_list)
            item_list.add_element(element)

            item = InventoryItem(template.item_name, element)
            self._insert_item(item)

            context.data_modified = True
            context.main_window.update_title(None)
        except DBException as exc:
            context.log_exception(
                "Unable to process database field", exc)
        except Exception as exc:
            context.log_exception(
                "Exception while processing action event", exc)

    # -- population ----------------------------------------------

    def set_fields(self, db_list):
        if not self.avail_done:
            for template in context.item_templates:
                base_item = template.base_item
                for mapping in _CATEGORY_MAPPINGS:
                    if mapping[0] == base_item:
                        self._insert_template(
                            self.category_iids[mapping[1]],
                            template)
                        break
            self.avail_done = True

        item_count = 0
        item_list = None
        element = db_list.get_element("Equip_ItemList")
        if element is not None and element.type == ElementType.LIST:
            item_list = element.value
            item_count = item_list.element_count()

        self.items = []
        self.listbox.delete(0, "end")
        for i in range(item_count):
            item_element = item_list.get_element_at(i)
            item_fields = item_element.value
            item_name = item_fields.get_string("LocalizedName")
            if len(item_name) > 0 \
                    and item_fields.get_integer("BaseItem") != 36:
                self._insert_item(
                    InventoryItem(item_name, item_element))
        self.listbox.selection_clear(0, "end")

    def get_fields(self, db_list):
        pass

    def _insert_template(self, category_iid, template):
        children = self.tree.get_children(category_iid)
        name = template.item_name
        index = len(children)
        for i, child in enumerate(children):
            if name < self.templates[child].item_name:
                index = i
                break
        iid = self.tree.insert(category_iid, index, text=name)
        self.templates[iid] = template

    def _insert_item(self, item):
        index = len(self.items)
        for j, existing in enumerate(self.items):
            if item < existing:
                index = j
                break
        self.items.insert(index, item)
        self.listbox.insert(index, str(item))
