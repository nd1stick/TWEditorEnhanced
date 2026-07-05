"""Higher-level game-data holders built on the element model:
AlchemyIngredient, InventoryItem, ItemTemplate and Quest.
"""

from .dbmodel import ElementType
from .errors import DBException


class AlchemyIngredient:
    def __init__(self, ingredient_id, substances):
        self.id = ingredient_id
        self.substances = substances


class InventoryItem:
    def __init__(self, name, element):
        self.name = name
        self.element = element
        field_list = element.value
        self.count = field_list.get_integer("StackSize")

    def __eq__(self, other):
        return (isinstance(other, InventoryItem)
                and other.name == self.name
                and other.count == self.count)

    def __hash__(self):
        return hash((self.name, self.count))

    def __lt__(self, other):
        if self.name != other.name:
            return self.name < other.name
        return self.count < other.count

    def __str__(self):
        return "%s (%d)" % (self.name, self.count)


class ItemTemplate:
    def __init__(self, field_list):
        self.field_list = field_list
        self.base_item = field_list.get_integer("BaseItem")
        self.item_name = field_list.get_string("LocalizedName")
        self.resource_name = field_list.get_string("TemplateResRef")

    def __eq__(self, other):
        return (isinstance(other, ItemTemplate)
                and other.item_name == self.item_name)

    def __hash__(self):
        return hash(self.item_name)

    def __lt__(self, other):
        return self.item_name < other.item_name

    def __str__(self):
        return self.item_name + " (" + self.resource_name + ")"


class Quest:
    QUEST_NOT_STARTED = 0
    QUEST_STARTED = 1
    QUEST_COMPLETED = 2
    QUEST_FAILED = 3

    def __init__(self, resource, database):
        self.resource_name = resource
        self.database = database
        self.quest_element = database.top_level_struct
        self.quest_modified = False
        if self.quest_element.type != ElementType.STRUCT:
            raise DBException(
                "Top-level quest element is not a structure")
        field_list = self.quest_element.value
        self.quest_name = field_list.get_string(
            "QuestLocName").strip()
        main_phase = field_list.get_element("MainPhase")
        if main_phase is None or main_phase.type != ElementType.LIST:
            raise DBException(
                "MainPhase not found for quest " + self.resource_name)
        quest_list = main_phase.value
        if quest_list.element_count() == 0:
            raise DBException(
                "No quest list for quest " + self.resource_name)
        field_list = quest_list.get_element_at(0).value
        if field_list.get_integer("QuestBegan") == 0:
            self.quest_state = self.QUEST_NOT_STARTED
        elif field_list.get_integer("Completed") == 1:
            self.quest_state = self.QUEST_COMPLETED
        elif field_list.get_integer("Failed") == 1:
            self.quest_state = self.QUEST_FAILED
        elif field_list.get_integer("NewQuestInfoSent") == 1:
            self.quest_state = self.QUEST_STARTED
        else:
            self.quest_state = self.QUEST_NOT_STARTED

    def reset(self):
        """Return this quest to the Not Started state.

        Progress in a Witcher quest is tracked on every phase (and
        every nested subquest phase) by several BYTE flags plus an
        INT CurrPhase, and additionally by MarkedAsTrue on any
        Conditions parameters that gate NPC dialog transitions.
        Just zeroing the outer flags leaves the game thinking the
        inner state is still resolved, which lets the monsters
        respawn but keeps NPC dialog options unavailable.

        Reset does the full walk:
          - Every phase (root and nested): QuestBegan, Completed,
            Failed, NewQuestInfoSent and QISDFTP -> 0.
          - Root main phase CurrPhase -> 0 (phase 0 active).
          - Nested phase CurrPhase -> -1 (the "never entered"
            sentinel the game itself uses; see the un-traversed
            branches in any completed quest for the pattern).
          - Every Conditions[].Parameters[].MarkedAsTrue -> 0 so
            cached dialog-condition results are re-evaluated.

        Only fields that already exist are touched, so we do not
        graft new INT fields onto quests that never used those
        flags in the first place.
        """
        top = self.quest_element.value
        main_phase = top.get_element("MainPhase")
        if main_phase is None or main_phase.type != ElementType.LIST:
            raise DBException(
                "MainPhase not found for quest " + self.resource_name)
        quest_list = main_phase.value
        if quest_list.element_count() == 0:
            raise DBException(
                "No quest list for quest " + self.resource_name)

        for i in range(quest_list.element_count()):
            self._reset_phase(
                quest_list.get_element_at(i).value, is_root=True)

        self.quest_state = self.QUEST_NOT_STARTED
        self.quest_modified = True

    _PHASE_FLAGS = ("QuestBegan", "Completed", "Failed",
                    "NewQuestInfoSent", "QISDFTP")

    @classmethod
    def _reset_phase(cls, fields, is_root=False):
        for label in cls._PHASE_FLAGS:
            cls._zero_if_present(fields, label)
        if fields.get_element("CurrPhase") is not None:
            fields.set_integer("CurrPhase", 0 if is_root else -1)
        cls._reset_conditions(fields)
        element = fields.get_element("Phases")
        if element is not None and element.type == ElementType.LIST:
            phase_list = element.value
            for i in range(phase_list.element_count()):
                cls._reset_phase(
                    phase_list.get_element_at(i).value)

    @classmethod
    def _reset_conditions(cls, fields):
        element = fields.get_element("Conditions")
        if element is None or element.type != ElementType.LIST:
            return
        cond_list = element.value
        for i in range(cond_list.element_count()):
            cond_fields = cond_list.get_element_at(i).value
            params_element = cond_fields.get_element("Parameters")
            if params_element is None \
                    or params_element.type != ElementType.LIST:
                continue
            params_list = params_element.value
            for j in range(params_list.element_count()):
                param_fields = params_list.get_element_at(j).value
                cls._zero_if_present(param_fields, "MarkedAsTrue")

    @staticmethod
    def _zero_if_present(fields, label):
        if fields.get_element(label) is not None:
            fields.set_integer(label, 0)

    def __str__(self):
        return self.quest_name
