"""Dialogs.  Port of ProgressDialog and ExamineDialog.

ProgressDialog is modal and driven by a background task.  The task
runs on a worker thread and only touches plain values guarded by a
lock; a periodic poll on the main thread moves those values into
the widgets and closes the dialog when the task signals done.  This
keeps every Tk call on the main thread.

ExamineDialog renders the witcher item/quest description markup.
It performs the same control-code rewriting the Java dialog did
(<cBold>../</c> to bold, <cItalic>../</c> to italic, <strref:N> to
the looked-up string, other tags dropped, newlines to breaks) and
displays the result with bold/italic runs in a Text widget.
"""

import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from . import context


class ProgressDialog(tk.Toplevel):
    def __init__(self, parent, message):
        super().__init__(parent)
        self.parent = parent
        self.title("The Witcher Save Editor")
        self.resizable(False, False)

        self._lock = threading.Lock()
        self._progress = 0
        self._done = False
        self.success = False

        frame = ttk.Frame(self, padding=15)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=message,
                  font=("TkDefaultFont", 10, "bold")).pack(pady=5)
        self._bar = ttk.Progressbar(frame, length=300,
                                    maximum=100)
        self._bar.pack(pady=5)

    def show_dialog(self):
        self.update_idletasks()
        self.transient(self.parent)
        self._center()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.after(50, self._poll)
        self.wait_window(self)
        return self.success

    def update_progress(self, progress):
        with self._lock:
            self._progress = progress

    def close_dialog(self, success):
        with self._lock:
            self.success = success
            self._done = True

    def _poll(self):
        with self._lock:
            progress = self._progress
            done = self._done
        self._bar["value"] = progress
        if done:
            self.grab_release()
            self.destroy()
        else:
            self.after(50, self._poll)

    def _center(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = self.parent.winfo_rootx()
        y = self.parent.winfo_rooty()
        pw = self.parent.winfo_width()
        ph = self.parent.winfo_height()
        self.geometry("+%d+%d" % (x + (pw - width) // 2,
                                  y + (ph - height) // 2))


class ExamineDialog(tk.Toplevel):
    def __init__(self, parent, label, description):
        super().__init__(parent)
        self.title(label)

        html = self._rewrite(description)

        frame = ttk.Frame(self, padding=15)
        frame.pack(fill="both", expand=True)

        text = tk.Text(frame, width=60, height=28, wrap="word",
                       relief="flat")
        scroll = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self._configure_tags(text)
        self._render(text, html)
        text.configure(state="disabled")

        button = ttk.Button(self, text="OK", command=self.destroy)
        button.pack(pady=10)

    @staticmethod
    def _rewrite(description):
        text = "<html>" + description + "</html>"
        start = 6
        while True:
            start = text.find("<", start)
            if start < 0:
                break
            stop = text.find(">", start)
            if stop < 0:
                break
            control = text[start + 1:stop].lower()
            if control == "/html":
                break
            html = None
            strref = None
            if control == "cbold":
                html = "b"
            elif control == "citalic":
                html = "i"
            elif len(control) >= 7 and control[0:7] == "strref:":
                try:
                    refid = int(control[7:])
                    strref = context.strings_database.get_string(
                        refid)
                except ValueError:
                    strref = ""
            if html is not None:
                text = text[:start + 1] + html + text[stop:]
                close = text.find("</c>", stop)
                if close < 0:
                    text = text + "</" + html + ">"
                    break
                text = (text[:close + 2] + html
                        + text[close + 3:])
                start = close + 4
            elif strref is not None:
                text = text[:start] + strref + text[stop + 1:]
            else:
                text = text[:start] + text[stop + 1:]

        text = text.replace("\n", "<br>")
        return text

    @staticmethod
    def _configure_tags(text):
        base = tkfont.nametofont("TkDefaultFont")
        bold = base.copy()
        bold.configure(weight="bold")
        italic = base.copy()
        italic.configure(slant="italic")
        bold_italic = base.copy()
        bold_italic.configure(weight="bold", slant="italic")
        text.tag_configure("b", font=bold)
        text.tag_configure("i", font=italic)
        text.tag_configure("bi", font=bold_italic)

    @staticmethod
    def _render(text, html):
        if html.startswith("<html>"):
            html = html[6:]
        if html.endswith("</html>"):
            html = html[:-7]

        bold = False
        italic = False
        index = 0
        length = len(html)
        while index < length:
            start = html.find("<", index)
            if start < 0:
                ExamineDialog._insert(text, html[index:],
                                      bold, italic)
                break
            if start > index:
                ExamineDialog._insert(text, html[index:start],
                                      bold, italic)
            stop = html.find(">", start)
            if stop < 0:
                break
            tag = html[start + 1:stop].lower()
            if tag == "b":
                bold = True
            elif tag == "/b":
                bold = False
            elif tag == "i":
                italic = True
            elif tag == "/i":
                italic = False
            elif tag == "br":
                text.insert("end", "\n")
            elif tag in ("ul", "/ul"):
                text.insert("end", "\n")
            elif tag == "li":
                text.insert("end", "\n  - ")
            index = stop + 1

    @staticmethod
    def _insert(text, content, bold, italic):
        if content == "":
            return
        if bold and italic:
            tag = "bi"
        elif bold:
            tag = "b"
        elif italic:
            tag = "i"
        else:
            tag = ""
        text.insert("end", content, tag)


def show_examine_dialog(parent, label, description):
    dialog = ExamineDialog(parent, label, description)
    dialog.transient(parent)
    dialog.update_idletasks()
    dialog.grab_set()
    dialog.wait_window(dialog)
