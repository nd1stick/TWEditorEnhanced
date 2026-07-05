"""The save-game container database.  Port of SaveDatabase.java.

The container is a small header, the packed resource data, a
resource table (name plus offset/length per entry) and an 8-byte
trailer pointing at the table.  Saving streams the header through
unchanged, then each entry's bytes (from disk or memory), then a
freshly built table and trailer.
"""

import os

from . import context
from .byteutil import get_int32, put_int32
from .entries import SaveEntry
from .errors import DBException


class SaveDatabase:
    def __init__(self, path):
        self.file = path
        self.data_offset = 0
        self.entries = []
        self.entry_map = {}

        name = os.path.basename(path)
        dot = name.rfind(".")
        if dot > 0:
            name = name[:dot]
        self.save_name = name

    def load(self):
        with open(self.file, "rb") as in_stream:
            header = self._read(in_stream, 12)
            if header[0:4].decode("latin-1") != "RGMH":
                raise DBException("Save signature is not valid")
            version = get_int32(header, 4)
            if version != 1:
                raise DBException(
                    "Save version " + str(version)
                    + " is not supported")
            self.data_offset = get_int32(header, 8)

            in_stream.seek(0, os.SEEK_END)
            file_length = in_stream.tell()
            in_stream.seek(file_length - 8)
            trailer = self._read(in_stream, 8)
            resource_offset = get_int32(trailer, 0)
            resource_count = get_int32(trailer, 4)
            in_stream.seek(resource_offset)

            for _ in range(resource_count):
                size_bytes = self._read(in_stream, 4)
                length = get_int32(size_bytes, 0)
                name = self._read(
                    in_stream, length).decode("utf-8", "replace")
                info = self._read(in_stream, 8)
                data_length = get_int32(info, 0)
                offset = get_int32(info, 4)
                entry = SaveEntry(
                    name, self.file, offset, data_length)
                self.entries.append(entry)
                self.entry_map[entry.resource_name] = entry

    def save(self):
        output_file = self.file + ".tmp"
        if os.path.exists(output_file):
            os.remove(output_file)
        out = open(output_file, "wb")
        buffer = bytearray(4096)
        list_offset = self.data_offset
        try:
            with open(self.file, "rb") as in_stream:
                residual = self.data_offset
                while residual > 0:
                    length = min(residual, len(buffer))
                    chunk = in_stream.read(length)
                    if len(chunk) != length:
                        raise IOError(
                            "Save game header truncated")
                    out.write(chunk)
                    residual -= len(chunk)

            for entry in self.entries:
                if entry.on_disk:
                    with open(entry.resource_file, "rb") as src:
                        src.seek(entry.resource_offset)
                        residual = entry.resource_length
                        list_offset += residual
                        while residual > 0:
                            length = min(residual, len(buffer))
                            chunk = src.read(length)
                            if len(chunk) != length:
                                raise IOError(
                                    "Resource data truncated for "
                                    + entry.resource_name)
                            out.write(chunk)
                            residual -= len(chunk)
                else:
                    data = entry.resource_data
                    residual = entry.resource_length
                    list_offset += residual
                    out.write(bytes(data[:residual]))

            offset = self.data_offset
            for entry in self.entries:
                name_bytes = entry.resource_path.encode("utf-8")
                put_int32(buffer, 0, len(name_bytes))
                out.write(bytes(buffer[0:4]))
                out.write(name_bytes)
                length = entry.resource_length
                put_int32(buffer, 0, length)
                put_int32(buffer, 4, offset)
                out.write(bytes(buffer[0:8]))
                offset += length

            put_int32(buffer, 0, list_offset)
            put_int32(buffer, 4, len(self.entries))
            out.write(bytes(buffer[0:8]))

            out.close()
            out = None

            os.replace(output_file, self.file)
        finally:
            if out is not None:
                out.close()
                if os.path.exists(output_file):
                    os.remove(output_file)

    def get_name(self):
        return self.save_name

    def get_path(self):
        return self.file

    def get_entries(self):
        return self.entries

    def get_entry(self, resource_name):
        entry = self.entry_map.get(resource_name.lower())
        if entry is None:
            resource_path = (self.save_name + "\\" + resource_name)
            entry = self.entry_map.get(resource_path.lower())
        return entry

    def add_entry_file(self, path_name, file):
        entry = SaveEntry(context.save_prefix + path_name)
        entry.read_from_file(file)
        self.add_entry(entry)

    def add_entry(self, entry):
        name = entry.resource_name
        old_entry = self.entry_map.get(name)
        if old_entry is not None:
            index = self.entries.index(old_entry)
            self.entries[index] = entry
        else:
            self.entries.append(entry)
        self.entry_map[name] = entry

    @staticmethod
    def _read(in_stream, count):
        from .byteutil import read_fully
        data = read_fully(in_stream, count)
        if len(data) != count:
            raise DBException("Save data truncated")
        return data
