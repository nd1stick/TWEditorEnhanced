"""Small GUI helpers shared by the panels and windows.

mark_modified reproduces DatabaseUpdateListener: when a field
changes and a database is open and we are not loading, the data is
flagged modified and the window title refreshed.

flush_errors shows any errors recorded by context.log_exception
(including those raised on worker threads) on the main thread.
"""

from tkinter import messagebox

from . import context


def mark_modified():
    if context.database is not None and not context.data_changing:
        context.data_modified = True
        if context.main_window is not None:
            context.main_window.update_title(None)


def flush_errors(parent):
    for text, detail in context.take_pending_errors():
        message = text
        if detail:
            message = text + "\n\n" + detail
        messagebox.showerror("Error", message, parent=parent)
