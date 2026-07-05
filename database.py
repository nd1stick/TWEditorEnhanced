"""GFF database reader and writer.  Port of Database.java.

A GFF file is a header followed by six sections: struct array,
field array, label array, field data, field indices and list
indices.  Each struct points at its fields; container values
(struct, list, localized string, void, strings) live in the field
data or index sections.  Decoding walks the struct tree from the
top level struct; encoding rebuilds the six sections by a matching
recursive walk so the output layout matches the original.

Integers in the file are little endian.  Float and double values
are IEEE bit patterns, handled through the struct module.
"""

import os
import struct

from .byteutil import get_int32, put_int32
from .dbmodel import DBElement, DBList, ElementType
from .errors import DBException
from .localized import LocalizedString, LocalizedSubstring

_SUPPORTED_VERSIONS = ("V3.2", "V3.3")


def _int_bits_to_float(bits):
    return struct.unpack("<f", struct.pack("<I", bits & 0xFFFFFFFF))[0]


def _float_to_int_bits(value):
    return struct.unpack("<I", struct.pack("<f", value))[0]


class Database:
    def __init__(self, path=None):
        self.file = path
        self.name = os.path.basename(path) if path else ""
        self.file_type = None
        self.file_version = None
        self.top_level_struct = None

    # -- public API ----------------------------------------------

    def get_type(self):
        return self.file_type

    def set_type(self, file_type):
        if len(file_type) != 4:
            raise ValueError("The file type is not 4 characters")
        self.file_type = file_type

    def get_version(self):
        return self.file_version

    def set_version(self, version):
        if version not in _SUPPORTED_VERSIONS:
            raise ValueError(
                "File version " + version + " is not supported")
        self.file_version = version

    def set_top_level_struct(self, struct_element):
        if struct_element.type != ElementType.STRUCT:
            raise ValueError(
                "Database element is not a structure")
        self.top_level_struct = struct_element

    def load(self):
        if self.file is None:
            raise RuntimeError("No database file is available")
        with open(self.file, "rb") as in_stream:
            self.load_stream(in_stream)

    def load_stream(self, in_stream):
        from .byteutil import read_fully
        try:
            header = read_fully(in_stream, 56)
            if len(header) != 56:
                raise DBException(
                    self.name + ": GFF header is too short")

            self.file_type = header[0:4].decode("latin-1")
            self.file_version = header[4:8].decode("latin-1")
            if self.file_version not in _SUPPORTED_VERSIONS:
                raise DBException(
                    self.name + ": GFF version "
                    + self.file_version + " is not supported")

            get_int32(header, 8)
            self._struct_count = get_int32(header, 12)
            get_int32(header, 16)
            self._field_count = get_int32(header, 20)
            get_int32(header, 24)
            self._label_count = get_int32(header, 28)
            get_int32(header, 32)
            self._field_data_length = get_int32(header, 36)
            get_int32(header, 40)
            self._field_indices_length = get_int32(header, 44)
            get_int32(header, 48)
            self._list_indices_length = get_int32(header, 52)

            if self._struct_count < 1:
                raise DBException(
                    self.name + ": GFF file contains no structures")

            self._struct_buffer = self._read_section(
                in_stream, 12 * self._struct_count,
                "Structure array data")
            self._field_buffer = b""
            if self._field_count > 0:
                self._field_buffer = self._read_section(
                    in_stream, 12 * self._field_count,
                    "Field array data")
            self._label_buffer = b""
            if self._label_count > 0:
                self._label_buffer = self._read_section(
                    in_stream, 16 * self._label_count,
                    "Label array data")
            self._field_data_buffer = b""
            if self._field_data_length > 0:
                self._field_data_buffer = self._read_section(
                    in_stream, self._field_data_length,
                    "Field data")
            self._field_indices_buffer = b""
            if self._field_indices_length > 0:
                self._field_indices_buffer = self._read_section(
                    in_stream, self._field_indices_length,
                    "Field indices")
            self._list_indices_buffer = b""
            if self._list_indices_length > 0:
                self._list_indices_buffer = self._read_section(
                    in_stream, self._list_indices_length,
                    "List indices")

            self.top_level_struct = self._decode_struct("", 0)
        finally:
            self._struct_buffer = None
            self._field_buffer = None
            self._label_buffer = None
            self._field_data_buffer = None
            self._field_indices_buffer = None
            self._list_indices_buffer = None

    def save(self):
        if self.file is None:
            raise RuntimeError("No database file is available")
        tmp = self.file + ".new"
        try:
            with open(tmp, "wb") as out_stream:
                self.save_stream(out_stream)
            os.replace(tmp, self.file)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    # -- decoding ------------------------------------------------

    def _read_section(self, in_stream, size, label):
        from .byteutil import read_fully
        data = read_fully(in_stream, size)
        if len(data) != size:
            raise DBException(self.name + ": " + label + " truncated")
        return data

    def _decode_field(self, index):
        if index >= self._field_count:
            raise DBException(
                self.name + ": Field index " + str(index)
                + " exceeds array size")

        offset = 12 * index
        field_type = get_int32(self._field_buffer, offset)
        label_index = get_int32(self._field_buffer, offset + 4)
        data_offset = get_int32(self._field_buffer, offset + 8)
        if label_index >= self._label_count:
            raise DBException(
                self.name + ": Label index " + str(label_index)
                + " exceeds array size")

        label_offset = 16 * label_index
        raw = self._label_buffer[label_offset:label_offset + 16]
        length = 16
        while length > 0 and raw[length - 1] == 0:
            length -= 1
        label = raw[:length].decode("latin-1")

        data = self._field_data_buffer
        data_length = self._field_data_length

        if field_type == ElementType.LIST:
            return self._decode_list(label, data_offset)
        if field_type == ElementType.STRUCT:
            return self._decode_struct(label, data_offset)
        if field_type == ElementType.BYTE:
            return DBElement(field_type, 0, label,
                             data_offset & 0xFF)
        if field_type == ElementType.CHAR:
            return DBElement(field_type, 0, label,
                             data_offset & 0xFFFF)
        if field_type == ElementType.WORD:
            return DBElement(field_type, 0, label,
                             data_offset & 0xFFFF)
        if field_type == ElementType.SHORT:
            value = data_offset & 0xFFFF
            if value > 32767:
                value -= 0x10000
            return DBElement(field_type, 0, label, value)
        if field_type == ElementType.DWORD:
            return DBElement(field_type, 0, label,
                             data_offset & 0xFFFFFFFF)
        if field_type == ElementType.INT:
            return DBElement(field_type, 0, label, data_offset)
        if field_type in (ElementType.DWORD64, ElementType.INT64):
            if data_offset + 8 > data_length:
                raise DBException(
                    self.name + ": Field data offset "
                    + str(data_offset) + " exceeds field data")
            value = struct.unpack(
                "<q", data[data_offset:data_offset + 8])[0]
            if field_type == ElementType.DWORD64 and value < 0:
                raise DBException(
                    "DWORD64 value is too large for "
                    "Java representation")
            return DBElement(field_type, 0, label, value)
        if field_type == ElementType.FLOAT:
            return DBElement(field_type, 0, label,
                             _int_bits_to_float(data_offset))
        if field_type == ElementType.DOUBLE:
            if data_offset + 8 > data_length:
                raise DBException(
                    self.name + ": Field data offset "
                    + str(data_offset) + " exceeds field data")
            value = struct.unpack(
                "<d", data[data_offset:data_offset + 8])[0]
            return DBElement(field_type, 0, label, value)
        if field_type == ElementType.VOID:
            if data_offset + 4 > data_length:
                raise DBException(
                    "Field data offset " + str(data_offset)
                    + " exceeds field data")
            byte_length = get_int32(data, data_offset)
            data_offset += 4
            if data_offset + byte_length > data_length:
                raise DBException(
                    "Void data length " + str(byte_length)
                    + " exceeds field data")
            value = bytes(data[data_offset:data_offset + byte_length])
            return DBElement(field_type, 0, label, value)
        if field_type == ElementType.RESOURCE:
            if data_offset + 1 > data_length:
                raise DBException(
                    self.name + ": Field data offset "
                    + str(data_offset) + " exceeds field data")
            resource_length = data[data_offset]
            data_offset += 1
            if data_offset + resource_length > data_length:
                raise DBException(
                    self.name + ": Resource length "
                    + str(resource_length) + " exceeds field data")
            value = data[
                data_offset:data_offset + resource_length
            ].decode("utf-8", "replace")
            return DBElement(field_type, 0, label, value)
        if field_type == ElementType.STRING:
            if data_offset + 4 > data_length:
                raise DBException(
                    self.name + ": Field data offset "
                    + str(data_offset) + " exceeds field data")
            string_length = get_int32(data, data_offset)
            data_offset += 4
            if data_offset + string_length > data_length:
                raise DBException(
                    self.name + ": String length "
                    + str(string_length) + " exceeds field data")
            value = data[
                data_offset:data_offset + string_length
            ].decode("utf-8", "replace")
            return DBElement(field_type, 0, label, value)
        if field_type == ElementType.LSTRING:
            return self._decode_lstring(label, data_offset)
        raise DBException(
            self.name + ": Unrecognized field type "
            + str(field_type))

    def _decode_lstring(self, label, data_offset):
        data = self._field_data_buffer
        data_length = self._field_data_length
        if data_offset + 12 > data_length:
            raise DBException(
                self.name + ": Field data offset "
                + str(data_offset) + " exceeds field data")
        localized_length = get_int32(data, data_offset)
        string_reference = get_int32(data, data_offset + 4)
        substring_count = get_int32(data, data_offset + 8)
        data_offset += 12
        localized_length -= 8
        localized = LocalizedString(string_reference)

        for i in range(substring_count):
            if data_offset + 8 > data_length:
                raise DBException(
                    self.name + ": Localized substring " + str(i)
                    + " exceeds field data")
            if localized_length < 8:
                raise DBException(
                    self.name + ": Localized substring " + str(i)
                    + " exceeds localized string")
            string_id = get_int32(data, data_offset)
            substring_length = get_int32(data, data_offset + 4)
            data_offset += 8
            localized_length -= 8
            if data_offset + substring_length > data_length:
                raise DBException(
                    self.name + ": Localized substring " + str(i)
                    + " exceeds field data")
            if substring_length > localized_length:
                raise DBException(
                    self.name + ": Localized substring " + str(i)
                    + " exceeds localized string")
            substring = data[
                data_offset:data_offset + substring_length
            ].decode("utf-8", "replace")
            localized.add_substring(LocalizedSubstring(
                substring, string_id // 2, string_id & 0x1))
            data_offset += substring_length
            localized_length -= substring_length

        return DBElement(ElementType.LSTRING, 0, label, localized)

    def _decode_struct(self, label, index):
        if index >= self._struct_count:
            raise DBException(
                self.name + ": Structure index " + str(index)
                + " exceeds array size")

        offset = 12 * index
        struct_id = get_int32(self._struct_buffer, offset)
        field_index = get_int32(self._struct_buffer, offset + 4)
        field_count = get_int32(self._struct_buffer, offset + 8)
        result = DBList(field_count)
        if field_count == 1:
            result.add_element(self._decode_field(field_index))
        elif field_count > 1:
            offset = field_index
            for _ in range(field_count):
                if offset + 4 > self._field_indices_length:
                    raise DBException(
                        "Field indices offset " + str(offset)
                        + " exceeds indices size")
                field_index = get_int32(
                    self._field_indices_buffer, offset)
                offset += 4
                result.add_element(
                    self._decode_field(field_index))

        return DBElement(ElementType.STRUCT, struct_id, label,
                         result)

    def _decode_list(self, label, offset):
        if offset + 4 > self._list_indices_length:
            raise DBException(
                self.name + ": List indices offset " + str(offset)
                + " exceeds indices size")

        struct_count = get_int32(self._list_indices_buffer, offset)
        result = DBList(struct_count)
        list_offset = offset + 4
        for _ in range(struct_count):
            if list_offset + 4 > self._list_indices_length:
                raise DBException(
                    self.name + ": List indices offset "
                    + str(list_offset) + " exceeds indices size")
            struct_index = get_int32(
                self._list_indices_buffer, list_offset)
            list_offset += 4
            result.add_element(
                self._decode_struct("", struct_index))

        return DBElement(ElementType.LIST, 0, label, result)

    # -- encoding ------------------------------------------------

    def save_stream(self, out_stream):
        self._struct_slots = []
        self._field_slots = []
        self._label_slots = []
        self._enc_field_data = bytearray()
        self._enc_field_indices = bytearray()
        self._enc_list_indices = bytearray()

        if self.top_level_struct is None:
            raise DBException(
                self.name + ": No top-level structure")
        if self.file_type is None or len(self.file_type) != 4:
            raise DBException(self.name + ": File type is not set")
        if self.file_version is None or len(self.file_version) != 4:
            raise DBException(
                self.name + ": File version is not set")

        self._encode_struct(self.top_level_struct)

        struct_count = len(self._struct_slots)
        field_count = len(self._field_slots)
        label_count = len(self._label_slots)
        struct_bytes = b"".join(self._struct_slots)
        field_bytes = b"".join(self._field_slots)
        label_bytes = b"".join(self._label_slots)
        field_data = bytes(self._enc_field_data)
        field_indices = bytes(self._enc_field_indices)
        list_indices = bytes(self._enc_list_indices)

        header = bytearray(56)
        header[0:4] = self.file_type.encode("latin-1")
        header[4:8] = self.file_version.encode("latin-1")
        offset = 56
        struct_length = 12 * struct_count
        put_int32(header, 8, offset)
        put_int32(header, 12, struct_count)
        offset += struct_length
        field_length = 12 * field_count
        put_int32(header, 16, offset)
        put_int32(header, 20, field_count)
        offset += field_length
        label_length = 16 * label_count
        put_int32(header, 24, offset)
        put_int32(header, 28, label_count)
        offset += label_length
        put_int32(header, 32, offset)
        put_int32(header, 36, len(field_data))
        offset += len(field_data)
        put_int32(header, 40, offset)
        put_int32(header, 44, len(field_indices))
        offset += len(field_indices)
        put_int32(header, 48, offset)
        put_int32(header, 52, len(list_indices))

        out_stream.write(bytes(header))
        out_stream.write(struct_bytes)
        if field_length:
            out_stream.write(field_bytes)
        if label_length:
            out_stream.write(label_bytes)
        if field_data:
            out_stream.write(field_data)
        if field_indices:
            out_stream.write(field_indices)
        if list_indices:
            out_stream.write(list_indices)

        self._struct_slots = None
        self._field_slots = None
        self._label_slots = None
        self._enc_field_data = None
        self._enc_field_indices = None
        self._enc_list_indices = None

    def _set_field_data(self, data):
        offset = len(self._enc_field_data)
        self._enc_field_data += data
        return offset

    def _set_field_data_long(self, value):
        offset = len(self._enc_field_data)
        self._enc_field_data += struct.pack(
            "<Q", value & 0xFFFFFFFFFFFFFFFF)
        return offset

    def _encode_field(self, element):
        field_type = element.type
        field_label = element.label
        if field_label == "":
            raise DBException("Field does not have a label")

        label = bytearray(16)
        label_bytes = field_label.encode("latin-1")
        count = min(len(label_bytes), 16)
        label[0:count] = label_bytes[0:count]
        label = bytes(label)

        label_index = -1
        for i, existing in enumerate(self._label_slots):
            if existing == label:
                label_index = i
                break
        if label_index < 0:
            label_index = len(self._label_slots)
            self._label_slots.append(label)

        value = element.value
        data_offset = self._encode_value(field_type, element, value)

        slot = bytearray(12)
        put_int32(slot, 0, int(field_type))
        put_int32(slot, 4, label_index)
        put_int32(slot, 8, data_offset)
        field_index = len(self._field_slots)
        self._field_slots.append(bytes(slot))
        return field_index

    def _encode_value(self, field_type, element, value):
        if field_type == ElementType.LIST:
            return self._encode_list(element)
        if field_type == ElementType.STRUCT:
            return self._encode_struct(element)
        if field_type == ElementType.BYTE:
            return value & 0xFF
        if field_type == ElementType.CHAR:
            return value & 0xFFFF
        if field_type in (ElementType.WORD, ElementType.SHORT):
            return value & 0xFFFF
        if field_type == ElementType.DWORD:
            return value & 0xFFFFFFFF
        if field_type == ElementType.INT:
            return value
        if field_type in (ElementType.DWORD64, ElementType.INT64):
            return self._set_field_data_long(value)
        if field_type == ElementType.FLOAT:
            return _float_to_int_bits(value)
        if field_type == ElementType.DOUBLE:
            return self._set_field_data_long(
                struct.unpack("<Q", struct.pack("<d", value))[0])
        if field_type == ElementType.VOID:
            void_length = len(value)
            buffer = bytearray(4 + void_length)
            put_int32(buffer, 0, void_length)
            buffer[4:] = value
            return self._set_field_data(bytes(buffer))
        if field_type == ElementType.RESOURCE:
            data = value.encode("utf-8")
            if len(data) > 255:
                raise DBException(
                    "Resource length is greater than 255")
            buffer = bytearray(1 + len(data))
            buffer[0] = len(data)
            buffer[1:] = data
            return self._set_field_data(bytes(buffer))
        if field_type == ElementType.STRING:
            if len(value) > 0:
                data = value.encode("utf-8")
                buffer = bytearray(4 + len(data))
                put_int32(buffer, 0, len(data))
                buffer[4:] = data
            else:
                buffer = bytearray(4)
            return self._set_field_data(bytes(buffer))
        if field_type == ElementType.LSTRING:
            return self._encode_lstring(value)
        raise DBException(
            self.name + ": Unrecognized field type "
            + str(field_type))

    def _encode_lstring(self, localized):
        substring_count = localized.substring_count()
        localized_length = 8
        substring_datas = []
        for i in range(substring_count):
            text = localized.get_substring(i).string
            data = text.encode("utf-8") if len(text) > 0 else b""
            substring_datas.append(data)
            localized_length += 8 + len(data)

        buffer = bytearray(4 + localized_length)
        put_int32(buffer, 0, localized_length)
        put_int32(buffer, 4, localized.string_reference)
        put_int32(buffer, 8, substring_count)
        offset = 12
        for i in range(substring_count):
            substring = localized.get_substring(i)
            data = substring_datas[i]
            length = len(data)
            put_int32(buffer, offset,
                      substring.language * 2 + substring.gender)
            put_int32(buffer, offset + 4, length)
            if length > 0:
                buffer[offset + 8:offset + 8 + length] = data
            offset += 8 + length

        return self._set_field_data(bytes(buffer))

    def _encode_struct(self, element):
        field_list = element.value
        field_count = field_list.element_count()
        struct_index = len(self._struct_slots)
        self._struct_slots.append(None)

        field_offset = 0
        if field_count == 1:
            field_offset = self._encode_field(
                field_list.get_element_at(0))
        elif field_count > 1:
            field_offset = len(self._enc_field_indices)
            self._enc_field_indices += b"\x00" * (4 * field_count)
            for i in range(field_count):
                field_index = self._encode_field(
                    field_list.get_element_at(i))
                put_int32(self._enc_field_indices,
                          field_offset + 4 * i, field_index)

        slot = bytearray(12)
        put_int32(slot, 0, element.id)
        put_int32(slot, 4, field_offset)
        put_int32(slot, 8, field_count)
        self._struct_slots[struct_index] = bytes(slot)
        return struct_index

    def _encode_list(self, element):
        field_list = element.value
        list_count = field_list.element_count()
        list_length = (list_count + 1) * 4
        list_offset = len(self._enc_list_indices)
        self._enc_list_indices += b"\x00" * list_length
        put_int32(self._enc_list_indices, list_offset, list_count)
        for i in range(list_count):
            struct_index = self._encode_struct(
                field_list.get_element_at(i))
            put_int32(self._enc_list_indices,
                      list_offset + 4 * (i + 1), struct_index)
        return list_offset
