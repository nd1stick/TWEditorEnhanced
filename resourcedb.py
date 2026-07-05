"""ERF-family resource database (ERF/HAK/MOD/NWM/SAV).  Port of
ResourceDatabase.java.

Layout: a 160-byte header, a localized description string list, a
key table (resource name plus type per entry), a resource table
(offset/length per entry) and the packed resource data.  Saving
writes a placeholder header, streams the sections, then seeks back
and rewrites the first 44 header bytes.
"""

import os
import time

from .byteutil import (get_int32, get_uint16, put_int16, put_int32,
                       read_fully)
from .entries import ResourceEntry
from .errors import DBException
from .localized import LocalizedString, LocalizedSubstring

DATABASE_TYPES = ["ERF ", "HAK ", "MOD ", "NWM ", "SAV "]
DATABASE_VERSIONS = ["V1.0", "V1.1"]

_HEADER_SIZE = 160


class ResourceDatabase:
    def __init__(self, path):
        self.file = path
        self.database_type = "ERF "
        self.database_version = "V1.0"
        self.description = LocalizedString(-1)
        self.entries = []
        self.entry_map = {}

    def load(self):
        with open(self.file, "rb") as in_stream:
            header = self._read(in_stream, _HEADER_SIZE,
                                "Database header is too short")
            self.database_type = header[0:4].decode("latin-1")
            if self.database_type not in DATABASE_TYPES:
                raise DBException(
                    "Database type '" + self.database_type
                    + "' is not supported")
            self.database_version = header[4:8].decode("latin-1")
            if self.database_version not in DATABASE_VERSIONS:
                raise DBException(
                    "Database version '" + self.database_version
                    + "' is not supported")

            string_count = get_int32(header, 8)
            entry_count = get_int32(header, 16)
            string_offset = get_int32(header, 20)
            key_offset = get_int32(header, 24)
            resource_offset = get_int32(header, 28)
            string_reference = get_int32(header, 40)

            self.description = LocalizedString(string_reference)
            self.entries = []
            self.entry_map = {}

            if string_count > 0:
                in_stream.seek(string_offset)
                for _ in range(string_count):
                    info = self._read(in_stream, 8,
                                      "String list truncated")
                    language = get_int32(info, 0)
                    string_length = get_int32(info, 4)
                    gender = language & 0x1
                    language >>= 1
                    if string_length > 0:
                        data = self._read(
                            in_stream, string_length,
                            "String list truncated")
                        string = data.decode("utf-8", "replace")
                        if string and string[-1] == "\x00":
                            string = string[:-1]
                    else:
                        string = ""
                    self.description.add_substring(
                        LocalizedSubstring(string, language, gender))

            resource_names = []
            resource_types = []
            if entry_count > 0:
                in_stream.seek(key_offset)
                if self.database_version == "V1.0":
                    key_length = 24
                    name_length = 16
                else:
                    key_length = 40
                    name_length = 32
                for _ in range(entry_count):
                    key = self._read(in_stream, key_length,
                                     "Key list truncated")
                    count = 0
                    while count < name_length and key[count] != 0:
                        count += 1
                    resource_names.append(
                        key[0:count].decode("latin-1"))
                    resource_types.append(
                        get_uint16(key, name_length + 4))

            if entry_count > 0:
                in_stream.seek(resource_offset)
                for i in range(entry_count):
                    element = self._read(in_stream, 8,
                                         "Resource list truncated")
                    offset = get_int32(element, 0)
                    length = get_int32(element, 4)
                    resource_name = resource_names[i]
                    resource_type = resource_types[i]
                    if len(resource_name) > 0 \
                            and resource_type != 65535:
                        entry = ResourceEntry.from_type(
                            resource_name, resource_type,
                            self.file, offset, length)
                        self.entries.append(entry)
                        self.entry_map[entry.entry_name] = entry

    def save(self):
        output_file = self.file + ".tmp"
        if os.path.exists(output_file):
            os.remove(output_file)
        out = open(output_file, "w+b")
        try:
            header = bytearray(_HEADER_SIZE)
            out.write(bytes(header))

            string_offset = out.tell()
            string_size = 0
            string_count = self.description.substring_count()
            for i in range(string_count):
                substring = self.description.get_substring(i)
                string_bytes = substring.string.encode("latin-1")
                length = len(string_bytes)
                buffer = bytearray(8 + length)
                put_int32(buffer, 0,
                          substring.language * 2 + substring.gender)
                put_int32(buffer, 4, length)
                buffer[8:] = string_bytes
                out.write(bytes(buffer))
                string_size += length + 8

            entry_count = len(self.entries)
            key_offset = out.tell()
            if self.database_version == "V1.1":
                name_length = 32
                entry_length = 40
            else:
                name_length = 16
                entry_length = 24

            resource_id = 0
            for entry in self.entries:
                name_bytes = entry.resource_name.encode("latin-1")
                if len(name_bytes) > name_length:
                    raise DBException(
                        "Resource name '" + entry.resource_name
                        + "' is too long")
                key_buffer = bytearray(entry_length)
                key_buffer[0:len(name_bytes)] = name_bytes
                put_int32(key_buffer, name_length, resource_id)
                put_int16(key_buffer, name_length + 4,
                          entry.resource_type)
                put_int16(key_buffer, name_length + 6, 0)
                out.write(bytes(key_buffer))
                resource_id += 1

            resource_offset = out.tell()
            data_offset = resource_offset + entry_count * 8
            for entry in self.entries:
                length = entry.length
                buffer = bytearray(8)
                put_int32(buffer, 0, data_offset)
                put_int32(buffer, 4, length)
                out.write(bytes(buffer))
                data_offset += length

            chunk_buffer = bytearray(4096)
            for entry in self.entries:
                with open(entry.file, "rb") as src:
                    src.seek(entry.offset)
                    residual = entry.length
                    while residual > 0:
                        length = min(residual, len(chunk_buffer))
                        chunk = src.read(length)
                        if len(chunk) != length:
                            raise DBException(
                                "Data truncated for resource "
                                + entry.entry_name)
                        out.write(chunk)
                        residual -= len(chunk)

            now = time.localtime()
            type_bytes = self.database_type.encode("latin-1")
            header[0:4] = type_bytes[0:4]
            version_bytes = self.database_version.encode("latin-1")
            header[4:8] = version_bytes[0:4]
            put_int32(header, 8, string_count)
            put_int32(header, 12, string_size)
            put_int32(header, 16, entry_count)
            put_int32(header, 20, string_offset)
            put_int32(header, 24, key_offset)
            put_int32(header, 28, resource_offset)
            put_int32(header, 32, now.tm_year - 1970)
            put_int32(header, 36, now.tm_yday - 1)
            put_int32(header, 40, self.description.string_reference)

            out.seek(0)
            out.write(bytes(header[0:44]))
            out.close()
            out = None

            os.replace(output_file, self.file)
        finally:
            if out is not None:
                out.close()
                if os.path.exists(output_file):
                    os.remove(output_file)

    def get_name(self):
        return os.path.basename(self.file)

    def get_path(self):
        return self.file

    def get_type(self):
        return self.database_type

    def set_type(self, database_type):
        if database_type not in DATABASE_TYPES:
            raise ValueError(
                "Database type '" + database_type
                + "' is not supported")
        self.database_type = database_type

    def get_version(self):
        return self.database_version

    def set_version(self, version):
        if version not in DATABASE_VERSIONS:
            raise ValueError(
                "Database version '" + version
                + "' is not supported")
        self.database_version = version

    def get_description(self):
        return self.description

    def get_entry_count(self):
        return len(self.entries)

    def get_entries(self):
        return self.entries

    def get_entry_at(self, index):
        if index < len(self.entries):
            return self.entries[index]
        return None

    def get_entry(self, entry_name):
        return self.entry_map.get(entry_name.lower())

    def add_entry(self, entry):
        old_entry = self.entry_map.get(entry.entry_name)
        if old_entry is not None:
            index = self.entries.index(old_entry)
            self.entries[index] = entry
        else:
            index = len(self.entries)
            self.entries.append(entry)
        self.entry_map[entry.entry_name] = entry
        return index

    def remove_entry(self, entry):
        old_entry = self.entry_map.get(entry.entry_name)
        if old_entry is None:
            return -1
        index = self.entries.index(old_entry)
        del self.entries[index]
        del self.entry_map[entry.entry_name]
        return index

    def remove_entry_at(self, index):
        entry = self.entries.pop(index)
        del self.entry_map[entry.entry_name]

    def __str__(self):
        return self.file

    @staticmethod
    def _read(in_stream, count, message):
        data = read_fully(in_stream, count)
        if len(data) != count:
            raise DBException(message)
        return data
