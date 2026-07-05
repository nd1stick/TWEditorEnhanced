"""Localized string database (the dialog .tlk file).  Port of
StringsDatabase.java.

The file stays open so strings can be read on demand by reference.
get_label strips a trailing period or colon and removes angle- and
brace-delimited control codes; get_heading pulls the text between a
header/bold control code and its closing tag.
"""

from .byteutil import get_int32
from .errors import DBException


class StringsDatabase:
    def __init__(self, path):
        self.file = path
        self._stream = open(path, "rb")
        self.string_count = 0
        self.entry_offset = 0
        self.string_offset = 0
        self.language_id = 0
        self._read_header()

    def _read_header(self):
        buffer = self._stream.read(20)
        if len(buffer) != 20:
            raise DBException("TLK header truncated")
        file_type = buffer[0:4].decode("latin-1")
        version = buffer[4:8].decode("latin-1")
        if file_type != "TLK ":
            raise DBException(
                "File type '" + file_type + "' is not supported")
        if version != "V3.0":
            raise DBException(
                "File version '" + version + "' is not supported")
        self.language_id = get_int32(buffer, 8)
        self.string_count = get_int32(buffer, 12)
        self.entry_offset = 20
        self.string_offset = get_int32(buffer, 16)

    def get_name(self):
        import os
        return os.path.basename(self.file)

    def get_language_id(self):
        return self.language_id

    def get_string(self, string_ref):
        string = None
        try:
            refid = string_ref & 0xFFFFFF
            if refid < self.string_count:
                self._stream.seek(self.entry_offset + refid * 40)
                buffer = self._stream.read(40)
                if len(buffer) != 40:
                    raise DBException(
                        "String entry truncated for reference "
                        + str(refid))
                if buffer[0] & 0x1:
                    offset = get_int32(buffer, 28)
                    length = get_int32(buffer, 32)
                    self._stream.seek(self.string_offset + offset)
                    data = self._stream.read(length)
                    if len(data) != length:
                        raise DBException(
                            "String data truncated for reference "
                            + str(refid))
                    string = data.decode("utf-8", "replace")
        except DBException as exc:
            from . import context
            context.log_exception("String database format error",
                                  exc)
        except OSError as exc:
            from . import context
            context.log_exception(
                "Unable to read string database", exc)
        return string if string is not None else ""

    def get_label(self, string_ref):
        string = self.get_string(string_ref).strip()

        if len(string) > 0:
            last = string[-1]
            if last == "." or last == ":":
                string = string[:-1]

        string = self._strip_pairs(string, "<", ">")
        string = self._strip_pairs(string, "{", "}")
        return string

    def get_heading(self, string_ref):
        heading = None
        string = self.get_string(string_ref).strip()
        start = string.find("<cHEADER>")
        if start < 0:
            start = string.find("<cHeader>")
        if start < 0:
            start = string.find("<cBOLD>")
        if start < 0:
            start = string.find("<cBold>")
        if start >= 0:
            start = string.find(">", start) + 1
            stop = string.find("</c>", start)
            if stop > start:
                heading = string[start:stop]
        return heading if heading is not None else string

    def close(self):
        if self._stream is not None:
            self._stream.close()
            self._stream = None

    @staticmethod
    def _strip_pairs(string, open_char, close_char):
        index = 0
        while True:
            start = string.find(open_char, index)
            if start < 0:
                break
            stop = string.find(close_char, start)
            if stop < 0:
                break
            string = string[:start] + string[stop + 1:]
            index = start
        return string
