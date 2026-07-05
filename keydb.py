"""Key index database (main.key).  Port of KeyDatabase.java.

The KEY file lists the BIF archive names and a key table mapping
each resource name/type/id to the archive that holds it.  The high
bits of the key's resource word select the archive.
"""

import os

from .byteutil import get_int16, get_int32, get_uint32
from .entries import KeyEntry
from .errors import DBException


class KeyDatabase:
    def __init__(self, path):
        self.file = path
        self.key_entries = []
        self.key_entries_map = {}
        self.archive_names = []
        self._read_file()

    def _read_file(self):
        from . import context
        with open(self.file, "rb") as in_stream:
            header = in_stream.read(68)
            if len(header) != 68:
                raise DBException("KEY header length is incorrect")
            signature = header[0:4].decode("latin-1")
            if signature != "KEY ":
                raise DBException(
                    "KEY header signature is incorrect")
            version = header[4:8].decode("latin-1")
            if version != "V1.1":
                raise DBException(
                    "KEY header version " + version
                    + " is not supported")
            file_count = get_int32(header, 8)
            file_offset = get_uint32(header, 20)
            key_count = get_int32(header, 12)
            key_offset = get_uint32(header, 24)

            self.archive_names = []
            for _ in range(file_count):
                in_stream.seek(file_offset)
                file_buffer = in_stream.read(12)
                if len(file_buffer) != 12:
                    raise DBException("File table truncated")
                name_offset = get_uint32(file_buffer, 4)
                name_length = get_int32(file_buffer, 8)
                in_stream.seek(name_offset)
                name_bytes = in_stream.read(name_length)
                file_name = name_bytes.decode("latin-1")
                self.archive_names.append(file_name)
                file_offset += 12

            self.key_entries = []
            self.key_entries_map = {}
            parent = os.path.dirname(self.file)
            for _ in range(key_count):
                in_stream.seek(key_offset)
                key_buffer = in_stream.read(26)
                if len(key_buffer) != 26:
                    raise DBException("Key table truncated")
                name_length = 1
                while name_length < 16 \
                        and key_buffer[name_length] != 0:
                    name_length += 1
                resource_name = key_buffer[
                    0:name_length].decode("latin-1")
                resource_type = get_int16(key_buffer, 16)
                resource_id = get_int32(key_buffer, 18)
                index = get_uint32(key_buffer, 22) >> 20
                if index >= len(self.archive_names):
                    raise DBException(
                        "BIF index for resource " + resource_name
                        + " is too large")
                archive_path = (parent + context.file_separator
                                + self.archive_names[index])
                key_entry = KeyEntry(resource_name, resource_type,
                                     resource_id, archive_path)
                self.key_entries.append(key_entry)
                self.key_entries_map[
                    key_entry.file_name.lower()] = key_entry
                key_offset += 26

    def get_name(self):
        return os.path.basename(self.file)

    def get_entries(self):
        return self.key_entries

    def get_entry(self, file_name):
        return self.key_entries_map.get(file_name.lower())
