"""Byte streams over save resources.

Port of SaveInputStream, SaveOutputStream, CompressedSaveInputStream,
CompressedSaveOutputStream, ResourceInputStream and KeyInputStream.

Each stream exposes a small file-like interface (read(size) for
inputs, write(data) for outputs, plus close()).  The compressed
variants wrap a save stream in a gzip member, matching the Java
GZIPInputStream/GZIPOutputStream wrappers.

The in-memory save data that Java kept as a list of 4096-byte
chunks is held here as a single bytearray on the SaveEntry; the
behavior is identical and the bookkeeping is simpler.
"""

import gzip
import os

from . import context
from .byteutil import get_int32, get_uint32
from .errors import DBException


class SaveInputStream:
    def __init__(self, entry):
        self.entry = entry
        self.residual = entry.resource_length
        if entry.on_disk:
            self.file = open(entry.resource_file, "rb")
            self.file.seek(entry.resource_offset)
            self.data = None
            self.pos = 0
        else:
            self.file = None
            self.data = entry.resource_data
            self.pos = 0

    def read(self, size=-1):
        if self.entry is None:
            raise IOError("Input stream is not open")
        if size is None or size < 0:
            size = self.residual
        count = min(size, self.residual)
        if count <= 0:
            return b""
        if self.file is not None:
            data = self.file.read(count)
        else:
            data = bytes(self.data[self.pos:self.pos + count])
            self.pos += len(data)
        self.residual -= len(data)
        return data

    def close(self):
        if self.file is not None:
            self.file.close()
            self.file = None
        self.entry = None
        self.residual = 0


class SaveOutputStream:
    def __init__(self, entry):
        entry.resource_offset = 0
        entry.resource_length = 0
        self.entry = entry
        self.count = 0
        if entry.on_disk:
            if os.path.exists(entry.resource_file):
                os.remove(entry.resource_file)
            self.file = open(entry.resource_file, "wb")
            self.data = None
        else:
            entry.resource_data = bytearray()
            self.file = None
            self.data = entry.resource_data

    def write(self, data):
        if self.entry is None:
            raise IOError("Output stream is not open")
        if self.file is not None:
            self.file.write(data)
        else:
            self.data.extend(data)
        self.count += len(data)
        return len(data)

    def flush(self):
        if self.file is not None:
            self.file.flush()

    def close(self):
        if self.entry is None:
            return
        if self.file is not None:
            self.file.close()
            self.file = None
        self.entry.resource_length = self.count
        self.entry = None


class CompressedSaveInputStream:
    def __init__(self, save_input_stream):
        self.save_input_stream = save_input_stream
        self.gz = gzip.GzipFile(fileobj=save_input_stream, mode="rb")

    def read(self, size=-1):
        return self.gz.read(size)

    def close(self):
        if self.save_input_stream is not None:
            self.gz.close()
            self.save_input_stream.close()
            self.save_input_stream = None


class CompressedSaveOutputStream:
    def __init__(self, save_output_stream):
        self.save_output_stream = save_output_stream
        self.gz = gzip.GzipFile(fileobj=save_output_stream,
                                mode="wb")

    def write(self, data):
        return self.gz.write(data)

    def flush(self):
        self.gz.flush()

    def close(self):
        if self.save_output_stream is not None:
            self.gz.close()
            self.save_output_stream.close()
            self.save_output_stream = None


class ResourceInputStream:
    def __init__(self, entry):
        self.entry = entry
        self.residual = entry.length
        self.file = open(entry.file, "rb")
        self.file.seek(entry.offset)

    def read(self, size=-1):
        if self.file is None:
            raise IOError("Input stream closed")
        if size is None or size < 0:
            size = self.residual
        count = min(size, self.residual)
        if count <= 0:
            return b""
        data = self.file.read(count)
        self.residual -= len(data)
        return data

    def close(self):
        if self.file is not None:
            self.file.close()
            self.file = None
        self.entry = None
        self.residual = 0


class KeyInputStream:
    """Reads a single resource out of a BIF archive named by a key
    entry.  The BIF resource table is scanned for the matching id.
    """

    def __init__(self, key_entry):
        self.file = open(key_entry.archive_path, "rb")
        self.data_offset = 0
        self.residual = 0

        header = self.file.read(20)
        if len(header) != 20:
            raise DBException("BIF header is too short")
        file_type = header[0:4].decode("latin-1")
        if file_type != "BIFF":
            raise DBException("BIF signature is not correct")
        version = header[4:8].decode("latin-1")
        if version != "V1.1":
            raise DBException(
                "BIF version " + version + " is not supported")
        resource_count = get_int32(header, 8)
        resource_offset = get_uint32(header, 16)

        self.file.seek(resource_offset)
        key_id = key_entry.resource_id
        for _ in range(resource_count):
            buffer = self.file.read(20)
            if len(buffer) != 20:
                raise DBException("Resource table truncated")
            resource_id = get_int32(buffer, 0)
            if resource_id == key_id:
                resource_type = self._get_short(buffer, 16)
                if resource_type != key_entry.resource_type:
                    raise DBException(
                        "KEY/BIF resource type mismatch")
                self.data_offset = get_int32(buffer, 8)
                self.residual = get_int32(buffer, 12)
                break

        if self.data_offset == 0:
            raise DBException(
                "KEY resource '" + key_entry.file_name
                + "' not found in BIF")

    def read(self, size=-1):
        if self.file is None:
            raise IOError("Input stream is not open")
        if size is None or size < 0:
            size = self.residual
        count = min(size, self.residual)
        if count <= 0:
            return b""
        self.file.seek(self.data_offset)
        data = self.file.read(count)
        self.data_offset += len(data)
        self.residual -= len(data)
        return data

    def close(self):
        if self.file is not None:
            self.file.close()
            self.file = None
        self.residual = 0

    @staticmethod
    def _get_short(buffer, offset):
        value = buffer[offset] | (buffer[offset + 1] << 8)
        if value >= 0x8000:
            value -= 0x10000
        return value
