"""Resource entry descriptors and the resource-type tables.

Port of SaveEntry, ResourceEntry and KeyEntry.  The resource-type
to file-extension tables are identical in the two Java classes and
are shared here.  Lookups keep first-match ordering, so duplicate
extensions resolve to the same type the Java code would pick.
"""

import os

from . import context
from .errors import DBException

RESOURCE_TYPES = [
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
    2000, 2001, 2002, 2003, 2005, 2007, 2008, 2009, 2010,
    2012, 2013, 2014, 2015, 2016, 2017, 2018, 2022, 2023, 2024,
    2025, 2026, 2027, 2029, 2030, 2031, 2032, 2033, 2034, 2035,
    2036, 2037, 2038, 2039, 2040, 2041, 2042, 2043, 2044, 2045,
    2046, 2047, 2048, 2049, 2050, 2051, 2052, 2053, 2054, 2055,
    2056, 2057, 2058, 2059, 2060, 2061, 2062, 2063, 2064, 2065,
    2066, 2067, 2068, 2069, 2070, 2071, 2072, 2073, 2074, 2075,
    2076, 2077, 2078, 2079, 2080, 2081, 2082, 2083, 2084, 2085,
    2086, 2087, 2088, 2089, 2090, 2091, 2092, 2093, 2094, 2095,
    2096, 2097, 2099, 2100, 2101, 2103, 2104, 2105, 2106, 2107,
    2108, 2110, 3000, 3001, 3002, 3003, 3004, 3005, 3006, 3007,
    3008, 3009, 3010, 3011, 3012, 3013, 3014, 3015, 3016, 3017,
    3018, 3019, 3020, 3021, 3022, 3033, 3034, 3035, 4000, 4001,
    4002, 4003, 4004, 4005, 4007, 4008, 9996, 9997, 9998, 9999,
]

FILE_EXTENSIONS = [
    "res", "bmp", "mve", "tga", "wav", "wfx", "plt", "ini", "mp3",
    "mpg", "txt", "plh", "tex", "mdl", "thg", "fnt", "lua", "slt",
    "nss", "ncs", "are", "set", "ifo", "bic", "wok", "2da", "tlk",
    "txi", "git", "bti", "uti", "btc", "utc", "dlg", "itp", "btt",
    "utt", "dds", "bts", "uts", "ltr", "gff", "fac", "bte", "ute",
    "btd", "utd", "btp", "utp", "dft", "gic", "gui", "css", "ccs",
    "btm", "utm", "dwk", "pwk", "btg", "utg", "jrl", "sav", "utw",
    "4pc", "ssf", "hak", "nwm", "bik", "ndb", "ptm", "ptt", "ncm",
    "mfx", "mat", "mdb", "say", "ttf", "ttc", "cut", "ka", "jpg",
    "ico", "ogg", "spt", "spw", "wfx", "ugm", "qdb", "qst", "npc",
    "spn", "utx", "mmd", "smm", "uta", "mde", "mdv", "mda", "mba",
    "oct", "bfx", "pdb", "pvs", "cfx", "luc", "prb", "cam", "vds",
    "bin", "wob", "api", "png", "osc", "usc", "trn", "utr", "uen",
    "ult", "sef", "pfx", "cam", "lfx", "bfx", "upe", "ros", "rst",
    "ifx", "pfb", "zip", "wmp", "bbx", "tfx", "wlk", "xml", "scc",
    "ptx", "ltx", "trx", "mdb", "mda", "spt", "gr2", "fxa", "fxe",
    "jpg", "pwc", "isd", "erf", "bif", "key",
]


class SaveEntry:
    def __init__(self, path, file=None, offset=0, length=0):
        self.resource_path = path
        sep = path.rfind(context.file_separator)
        if sep >= 0:
            self.resource_name = path[sep + 1:].lower()
        else:
            self.resource_name = path.lower()

        self.on_disk = file is not None
        if self.on_disk:
            self.resource_file = file
            self.resource_offset = offset
            self.resource_length = length
            self.resource_data = None
        else:
            self.resource_file = None
            self.resource_offset = 0
            self.resource_length = 0
            self.resource_data = bytearray()

        dot = self.resource_name.rfind(".")
        self.compressed = (dot > 0
                           and self.resource_name[dot:] == ".sav")

    def read_from_file(self, path):
        out = self.get_output_stream()
        try:
            with open(path, "rb") as in_file:
                while True:
                    chunk = in_file.read(65536)
                    if not chunk:
                        break
                    out.write(chunk)
        finally:
            out.close()

    def set_on_disk(self, on_disk):
        self.on_disk = on_disk
        self.resource_offset = 0
        self.resource_length = 0
        self.resource_file = None
        if on_disk:
            self.resource_data = None
        else:
            self.resource_data = bytearray()

    def set_resource_file(self, file, offset, length):
        self.resource_file = file
        self.resource_offset = offset
        self.resource_length = length
        self.resource_data = None
        self.on_disk = True

    def get_input_stream(self):
        from .streams import (CompressedSaveInputStream,
                              SaveInputStream)
        if self.compressed:
            return CompressedSaveInputStream(SaveInputStream(self))
        return SaveInputStream(self)

    def get_output_stream(self):
        from .streams import (CompressedSaveOutputStream,
                              SaveOutputStream)
        if self.compressed:
            return CompressedSaveOutputStream(
                SaveOutputStream(self))
        return SaveOutputStream(self)


class ResourceEntry:
    def __init__(self, entry_name, data_file):
        self.entry_name = entry_name.lower()
        self.file = data_file
        self.offset = 0
        self.length = os.path.getsize(data_file)

        dot = entry_name.rfind(".")
        if dot <= 0 or dot == len(entry_name) - 1:
            raise DBException(
                "Resource file name does not have an extension")
        self.resource_name = entry_name[:dot]

        ext = entry_name[dot + 1:]
        self.resource_type = -1
        for i, candidate in enumerate(FILE_EXTENSIONS):
            if candidate == ext:
                self.resource_type = RESOURCE_TYPES[i]
                break
        if self.resource_type < 0:
            raise DBException(
                "Resource file extension '" + ext
                + "' is not supported")

    @classmethod
    def from_file(cls, data_file):
        return cls(os.path.basename(data_file), data_file)

    @classmethod
    def from_type(cls, resource_name, resource_type, data_file,
                  data_offset, data_length):
        self = cls.__new__(cls)
        self.resource_name = resource_name.lower()
        self.resource_type = resource_type
        self.file = data_file
        self.offset = data_offset
        self.length = data_length

        ext = None
        for i, candidate in enumerate(RESOURCE_TYPES):
            if candidate == resource_type:
                ext = FILE_EXTENSIONS[i]
                break
        if ext is None:
            raise DBException(
                "Resource type " + str(resource_type)
                + " is not supported for resource "
                + resource_name)
        self.entry_name = self.resource_name + "." + ext
        return self

    @property
    def name(self):
        return self.entry_name

    def get_input_stream(self):
        from .streams import ResourceInputStream
        return ResourceInputStream(self)


class KeyEntry:
    def __init__(self, resource_name, resource_type, resource_id,
                 archive_path):
        self.resource_name = resource_name
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.archive_path = archive_path

        self.file_name = None
        for i, candidate in enumerate(RESOURCE_TYPES):
            if candidate == resource_type:
                self.file_name = (resource_name + "."
                                  + FILE_EXTENSIONS[i])
                break
        if self.file_name is None:
            raise DBException(
                "Resource type " + str(resource_type)
                + " is not supported")

    def get_input_stream(self):
        from .streams import KeyInputStream
        return KeyInputStream(self)
