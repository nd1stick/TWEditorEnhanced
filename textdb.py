"""2DA text table reader.  Port of TextDatabase.java.

A 2DA file is a header line ("2DA V2.0"), a column-label line, then
data rows whose first token is a row index that is skipped.  Tokens
may be bare or double-quoted.  A cell of "****" reads as empty.
"""

from .errors import DBException


class TextDatabase:
    def __init__(self, path):
        with open(path, "rb") as in_stream:
            data = in_stream.read()
        self._parse(data)

    @classmethod
    def from_stream(cls, stream):
        self = cls.__new__(cls)
        chunks = []
        while True:
            chunk = stream.read(65536)
            if not chunk:
                break
            chunks.append(chunk)
        self._parse(b"".join(chunks))
        return self

    def _parse(self, data):
        text = data.decode("latin-1")
        lines = text.splitlines()
        self.columns = []
        self.column_map = {}
        self.resources = []
        header_done = False
        columns_done = False

        for line in lines:
            line_length = len(line)
            if line_length == 0 or line[0] == "#":
                continue

            skip_index = True
            index = 0
            value = 0
            values = None
            if columns_done:
                values = [None] * len(self.columns)

            while index < line_length:
                if line[index].isspace():
                    index += 1
                    continue

                if line[index] == '"':
                    quoted = True
                    index += 1
                else:
                    quoted = False

                start = index
                if start >= line_length:
                    break
                while index < line_length and (
                        line[index] != '"' if quoted
                        else not line[index].isspace()):
                    index += 1
                if start == index:
                    token = ""
                else:
                    token = line[start:index]
                if index < line_length and line[index] == '"':
                    index += 1

                if not header_done:
                    if value == 0:
                        if token != "2DA":
                            raise DBException(
                                "File format '" + token
                                + "' is not supported")
                    elif value == 1 and token != "V2.0":
                        raise DBException(
                            "File version '" + token
                            + "' is not supported")
                elif not columns_done:
                    self.column_map[token.lower()] = value
                    self.columns.append(token)
                elif skip_index:
                    skip_index = False
                    value -= 1
                elif value < len(values):
                    values[value] = token

                value += 1

            if value > 0:
                if columns_done:
                    self.resources.append(values)
                elif header_done:
                    columns_done = True
                else:
                    header_done = True

    def get_column_labels(self):
        return self.columns

    def get_resource_count(self):
        return len(self.resources)

    def get_string_at(self, resource_index, value_index):
        if resource_index >= len(self.resources):
            raise ValueError("Resource index is not valid")
        if value_index >= len(self.columns):
            raise ValueError("Value index is not valid")
        return self.resources[resource_index][value_index]

    def get_string(self, resource_index, value_label):
        if resource_index >= len(self.resources):
            raise ValueError("Resource index is not valid")
        value_index = self.column_map.get(value_label.lower())
        if value_index is None:
            return ""
        string = self.resources[resource_index][value_index]
        if string is None:
            return ""
        if len(string) >= 4 and string[0:4] == "****":
            string = ""
        return string

    def get_integer(self, resource_index, value_label):
        if resource_index >= len(self.resources):
            raise ValueError("Resource index is not valid")
        value_index = self.column_map.get(value_label.lower())
        if value_index is None:
            return 0
        string = self.resources[resource_index][value_index]
        if string is None:
            return 0
        if len(string) >= 4 and string[0:4] == "****":
            return 0
        return int(string)
