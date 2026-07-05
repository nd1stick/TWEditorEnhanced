"""Inventory tab.  Port of InventoryPanel.

Like the equipment tab, but inventory items occupy a 6x14 slot
grid (rows 0-2 for normal items, rows 3-5 for alchemy
ingredients), and examining an alchemy ingredient lists its
substances, read once from alchemy_ingre.2da.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from . import context
from .dbmodel import DBElement, DBList, ElementType
from .dialogs import show_examine_dialog
from .errors import DBException
from .model import AlchemyIngredient, InventoryItem
from .textdb import TextDatabase

_CATEGORIES = ["Bomb", "Book", "Drink", "Food", "Gem", "Grease",
               "Ingredient", "Jewelry", "Magical", "Potion",
               "Quest", "Upgrade", "Other"]

_CATEGORY_MAPPINGS = [
    [20, 7], [21, 8], [22, 9], [23, 7], [30, 1], [32, 4],
    [33, 6], [34, 11], [37, 8], [38, 7], [40, 10], [44, 3],
    [45, 12], [46, 5], [47, 0], [48, 2],
]

_SUBSTANCE_NAMES = ["Vitriol", "Rebis", "Aether", "Quebirth",
                    "Hydragenum", "Vermilion", "Albedo",
                    "Nigredo", "Rubedo"]


class InventoryPanel(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        self.items = []
        self.templates = {}
        self.avail_done = False
        self.ingredients = None
        self.ingredients_map = None
        self.slots = [[False] * 14 for _ in range(6)]
        self.full_stack = tk.BooleanVar(value=False)

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
        ttk.Checkbutton(avail_buttons, text="Full Stack",
                        variable=self.full_stack).pack(
                            side="left", padx=3)

        items_pane.pack(side="left", fill="both", expand=True)
        ttk.Frame(self, width=15).pack(side="left")
        avail_pane.pack(side="left", fill="both", expand=True)

        self.category_iids = []
        for category in _CATEGORIES:
            iid = self.tree.insert("", "end", text=category,
                                   open=False)
            self.category_iids.append(iid)

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
        parts = []
        string = field_list.get_string("DescIdentified")
        if len(string) == 0:
            string = field_list.get_string("Description")
        if len(string) != 0:
            parts.append(string)

        alchemy_id = field_list.get_integer("AlchIngredient")
        if alchemy_id > 0:
            ingredient = self.ingredients_map.get(alchemy_id)
            if ingredient is not None:
                parts.append("<br><ul>")
                for substance in ingredient.substances:
                    parts.append("<li>")
                    parts.append(substance)
                parts.append("</ul>")

        show_examine_dialog(context.main_window, label,
                            "".join(parts))

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

            item_list = self._player().get_element("ItemList").value
            for i in range(item_list.element_count()):
                if item_list.get_element_at(i) is item_element:
                    item_list.remove_element_at(i)
                    fields = item_element.value
                    x = fields.get_integer("Repos_PosX")
                    y = fields.get_integer("Repos_PosY")
                    quest_item = fields.get_integer("QuestItem")
                    if quest_item != 0 or x < 0 or x >= 14 \
                            or y < 0 or y >= 6:
                        break
                    self.slots[y][x] = False
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
            quest_item = template_list.get_integer("QuestItem")
            alchemy = template_list.get_integer("AlchIngredient")

            x = 0
            y = 0
            if quest_item == 0:
                found = False
                if alchemy == 0:
                    rows = range(0, 3)
                else:
                    rows = range(3, 6)
                for y in rows:
                    for x in range(0, 14):
                        if not self.slots[y][x]:
                            found = True
                            break
                    if found:
                        break
                if not found:
                    messagebox.showwarning(
                        "Inventory is full",
                        "No inventory slot available", parent=self)
                    return

            # Full Stack checked -> original behavior (MaxStack,
            # often 25); otherwise add a single item.
            if self.full_stack.get():
                stack_size = max(
                    template_list.get_integer("MaxStack"), 1)
            else:
                stack_size = 1
            field_list = template_list.clone()
            field_list.set_integer("Dropable", 1, ElementType.BYTE)
            field_list.set_integer("Identified", 1,
                                   ElementType.BYTE)
            field_list.set_integer("StackSize", stack_size,
                                   ElementType.WORD)
            field_list.set_integer("Repos_PosX", x,
                                   ElementType.WORD)
            field_list.set_integer("Repos_PosY", y,
                                   ElementType.WORD)

            if quest_item == 0:
                self.slots[y][x] = True

            player = self._player()
            element = player.get_element("ItemList")
            if element is None:
                item_list = DBList(10)
                element = DBElement(ElementType.LIST, 0,
                                    "ItemList", item_list)
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
        if self.ingredients is None:
            self._load_ingredients()

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
        element = db_list.get_element("ItemList")
        if element is not None and element.type == ElementType.LIST:
            item_list = element.value
            item_count = item_list.element_count()

        self.items = []
        self.listbox.delete(0, "end")
        for y in range(6):
            for x in range(14):
                self.slots[y][x] = False

        for i in range(item_count):
            item_element = item_list.get_element_at(i)
            item_fields = item_element.value
            item_name = item_fields.get_string("LocalizedName")
            if len(item_name) > 0:
                quest_item = item_fields.get_integer("QuestItem")
                x = item_fields.get_integer("Repos_PosX")
                y = item_fields.get_integer("Repos_PosY")
                self._insert_item(
                    InventoryItem(item_name, item_element))
                if quest_item == 0 and 0 <= x < 14 \
                        and 0 <= y < 6:
                    self.slots[y][x] = True
        self.listbox.selection_clear(0, "end")

    def get_fields(self, db_list):
        pass

    def _load_ingredients(self):
        resource = context.resource_files.get("alchemy_ingre.2da")
        if resource is None:
            raise IOError("alchemy_ingre.2da not found")
        if isinstance(resource, str):
            in_stream = open(resource, "rb")
        else:
            in_stream = resource.get_input_stream()

        text_database = TextDatabase.from_stream(in_stream)
        count = text_database.get_resource_count()
        self.ingredients = []
        self.ingredients_map = {}
        for i in range(count):
            name = text_database.get_string(i, "NameRef")
            if len(name) > 0:
                substances = []
                for substance in _SUBSTANCE_NAMES:
                    if text_database.get_integer(i, substance) == 1:
                        substances.append(substance)
                ingredient = AlchemyIngredient(i, substances)
                self.ingredients.append(ingredient)
                self.ingredients_map[ingredient.id] = ingredient

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
