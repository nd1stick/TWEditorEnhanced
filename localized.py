"""Localized strings: a string reference plus per language/gender
substrings.  Port of LocalizedString and LocalizedSubstring.
"""

import copy

from .dbvalue import DBElementValue


class LocalizedSubstring:
    def __init__(self, string, language, gender):
        self.string = string
        self.language = language
        self.gender = gender

    def clone(self):
        return copy.copy(self)


class LocalizedString(DBElementValue):
    def __init__(self, reference):
        self.string_reference = reference
        self.substring_list = []

    def add_substring(self, substring):
        lang = substring.language
        gender = substring.gender
        for i, old in enumerate(self.substring_list):
            if old.language == lang and old.gender == gender:
                self.substring_list[i] = substring
                return
        self.substring_list.append(substring)

    def substring_count(self):
        return len(self.substring_list)

    def get_substring(self, index):
        return self.substring_list[index]

    def set_substring(self, index, substring):
        self.substring_list[index] = substring

    def find_substring(self, language, gender):
        for sub in self.substring_list:
            if sub.language == language and sub.gender == gender:
                return sub
        return None

    def clone(self):
        new = LocalizedString(self.string_reference)
        new.substring_list = [s.clone() for s in self.substring_list]
        return new
