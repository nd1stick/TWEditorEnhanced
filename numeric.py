"""A numeric text field.  Port of NumericField and NumericDocument.

The entry accepts only an optional leading minus sign followed by
digits, matching the original document filter.  A change listener
may be attached to flag the database modified.
"""

import re
import tkinter as tk
from tkinter import ttk

_PATTERN = re.compile(r"-?\d*")


class NumericField(ttk.Entry):
    def __init__(self, master, columns=5):
        self._var = tk.StringVar()
        validate = (master.register(self._validate), "%P")
        super().__init__(master, textvariable=self._var,
                         width=columns, validate="key",
                         validatecommand=validate)

    @staticmethod
    def _validate(proposed):
        return _PATTERN.fullmatch(proposed) is not None

    def add_change_listener(self, listener):
        self._var.trace_add("write", lambda *a: listener())

    def get_value(self):
        text = self._var.get()
        if text == "" or text == "-":
            return 0
        return int(text)

    def set_value(self, value):
        self._var.set(str(value))
