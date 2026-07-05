"""Core save-database element model: the element type codes, the
DBElement node, and the DBList container.  Port of DBElement and
DBList (the type constants live here as the ElementType enum).

Value representation by element type:
  BYTE/CHAR/WORD/SHORT/DWORD/INT/DWORD64/INT64  ->  int
  FLOAT/DOUBLE                                  ->  float
  STRING/RESOURCE                               ->  str
  LSTRING                                       ->  LocalizedString
  STRUCT/LIST                                   ->  DBList
  VOID                                          ->  bytes
CHAR is stored as its integer code, matching the Java Character.
"""

import copy
import enum

from . import context
from .dbvalue import DBElementValue
from .errors import DBException
from .localized import LocalizedString, LocalizedSubstring


class ElementType(enum.IntEnum):
    BYTE = 0
    CHAR = 1
    WORD = 2
    SHORT = 3
    DWORD = 4
    INT = 5
    DWORD64 = 6
    INT64 = 7
    FLOAT = 8
    DOUBLE = 9
    STRING = 10
    RESOURCE = 11
    LSTRING = 12
    VOID = 13
    STRUCT = 14
    LIST = 15


def _to_int32(value):
    """Truncate to a signed 32-bit int, like Java Number.intValue."""
    value &= 0xFFFFFFFF
    if value > 0x7FFFFFFF:
        value -= 0x100000000
    return value


class DBElement:
    def __init__(self, element_type, element_id, label, value):
        self.type = element_type
        self.id = element_id
        self.value = value
        self.label = label if label is not None else ""

    def clone(self):
        new = copy.copy(self)
        if self.type in (ElementType.LIST, ElementType.STRUCT,
                         ElementType.LSTRING):
            new.value = self.value.clone()
        return new


class DBList(DBElementValue):
    def __init__(self, capacity=0):
        self.element_list = []
        self.label_map = {}

    def add_element(self, element):
        label = element.label
        if label == "":
            self.element_list.append(element)
            return True
        if self.label_map.get(label) is not None:
            return False
        self.element_list.append(element)
        self.label_map[label] = element
        return True

    def insert_element(self, index, element):
        label = element.label
        if label == "":
            self.element_list.insert(index, element)
            return True
        if self.label_map.get(label) is not None:
            return False
        self.element_list.insert(index, element)
        self.label_map[label] = element
        return True

    def remove_element_at(self, index):
        element = self.element_list[index]
        del self.element_list[index]
        if element.label != "":
            self.label_map.pop(element.label, None)
        return element

    def remove_label(self, label):
        if not label:
            raise ValueError("No database element label supplied")
        element = self.label_map.get(label)
        if element is None:
            return False
        try:
            self.element_list.remove(element)
        except ValueError:
            return False
        self.label_map.pop(label, None)
        return True

    def remove_element(self, element):
        try:
            self.element_list.remove(element)
        except ValueError:
            return False
        if element.label != "":
            self.label_map.pop(element.label, None)
        return True

    def get_element(self, label):
        if not label:
            raise ValueError("No database element label supplied")
        return self.label_map.get(label)

    def set_element(self, label, element):
        if not label:
            raise ValueError("No database element label supplied")
        old = self.label_map.get(label)
        if old is not None:
            index = self.element_list.index(old)
            self.element_list[index] = element
        else:
            self.element_list.append(element)
        self.label_map[label] = element

    def element_count(self):
        return len(self.element_list)

    def get_element_at(self, index):
        return self.element_list[index]

    def set_element_at(self, index, element):
        old = self.element_list[index]
        if element.label != old.label:
            raise ValueError("New label is not the same as old label")
        self.element_list[index] = element
        self.label_map[element.label] = element

    def get_string(self, label):
        element = self.get_element(label)
        if element is None:
            return ""
        t = element.type
        if t == ElementType.STRING:
            return element.value
        if t == ElementType.RESOURCE:
            return element.value
        if t == ElementType.LSTRING:
            string = element.value
            if string.substring_count() > 0:
                sub = string.find_substring(context.language_id, 0)
                if sub is not None:
                    return sub.string
                return string.get_substring(0).string
            refid = string.string_reference
            if refid >= 0:
                return context.get_string(refid)
            return ""
        raise DBException("Field " + label + " is not a string")

    def set_string(self, label, value):
        element = self.get_element(label)
        if element is None:
            self.add_element(
                DBElement(ElementType.STRING, 0, label, value))
            return
        t = element.type
        if t in (ElementType.STRING, ElementType.RESOURCE):
            element.value = value
        elif t == ElementType.LSTRING:
            string = element.value
            string.add_substring(
                LocalizedSubstring(value, context.language_id, 0))
        else:
            raise DBException("Field " + label + " is not a string")

    def get_integer(self, label):
        element = self.get_element(label)
        if element is None:
            return 0
        t = element.type
        if t in (ElementType.BYTE, ElementType.WORD,
                 ElementType.SHORT, ElementType.INT):
            return int(element.value)
        if t in (ElementType.DWORD64, ElementType.INT64,
                 ElementType.DWORD):
            return _to_int32(int(element.value))
        if t == ElementType.CHAR:
            return int(element.value)
        if t == ElementType.FLOAT:
            return int(element.value)
        if t == ElementType.DOUBLE:
            return int(element.value)
        raise DBException("Field " + label + " is not numeric")

    def set_integer(self, label, value,
                    default_type=ElementType.INT):
        element = self.get_element(label)
        if element is None:
            self.add_element(
                DBElement(default_type, 0, label, value))
            return
        t = element.type
        if t == ElementType.BYTE:
            element.value = value & 0xFF
        elif t == ElementType.WORD:
            element.value = value & 0xFFFF
        elif t == ElementType.SHORT:
            short_value = value & 0xFFFF
            if short_value > 32767:
                short_value -= 0x10000
            element.value = short_value
        elif t == ElementType.INT:
            element.value = value
        elif t == ElementType.DWORD:
            element.value = value & 0xFFFFFFFF
        elif t in (ElementType.DWORD64, ElementType.INT64):
            element.value = value
        elif t == ElementType.CHAR:
            element.value = value & 0xFFFF
        elif t == ElementType.FLOAT:
            element.value = float(value)
        elif t == ElementType.DOUBLE:
            element.value = float(value)
        else:
            raise DBException("Field " + label + " is not numeric")

    def get_float(self, label):
        element = self.get_element(label)
        if element is None:
            return 0.0
        if element.type == ElementType.FLOAT:
            return float(element.value)
        raise DBException(
            "Field " + label + " is not floating-point")

    def set_float(self, label, value):
        element = self.get_element(label)
        if element is None:
            self.add_element(
                DBElement(ElementType.FLOAT, 0, label, value))
            return
        if element.type == ElementType.FLOAT:
            element.value = float(value)
        else:
            raise DBException(
                "Field " + label + " is not floating-point")

    def clone(self):
        new = DBList()
        for element in self.element_list:
            new.add_element(element.clone())
        return new
