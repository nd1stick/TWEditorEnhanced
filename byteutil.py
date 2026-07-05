"""Little-endian byte helpers shared by the binary readers and
writers.  These mirror the getInteger/setInteger/getShort/setShort
helpers duplicated across the Java database classes.

A bytes or bytearray is indexed directly; in Python 3 indexing
yields an int, so no masking with 0xFF is needed on reads.
"""


def get_uint32(buffer, offset):
    return (buffer[offset]
            | (buffer[offset + 1] << 8)
            | (buffer[offset + 2] << 16)
            | (buffer[offset + 3] << 24))


def get_int32(buffer, offset):
    value = get_uint32(buffer, offset)
    if value >= 0x80000000:
        value -= 0x100000000
    return value


def put_int32(buffer, offset, value):
    value &= 0xFFFFFFFF
    buffer[offset] = value & 0xFF
    buffer[offset + 1] = (value >> 8) & 0xFF
    buffer[offset + 2] = (value >> 16) & 0xFF
    buffer[offset + 3] = (value >> 24) & 0xFF


def get_uint16(buffer, offset):
    return buffer[offset] | (buffer[offset + 1] << 8)


def get_int16(buffer, offset):
    value = get_uint16(buffer, offset)
    if value >= 0x8000:
        value -= 0x10000
    return value


def put_int16(buffer, offset, value):
    value &= 0xFFFF
    buffer[offset] = value & 0xFF
    buffer[offset + 1] = (value >> 8) & 0xFF


def read_fully(stream, count):
    """Read exactly count bytes, or fewer at end of stream.

    Java read(buffer) may underfill; the callers check the return
    length and raise on a short read.  Looping here means a single
    short read from a gzip stream is not mistaken for truncation.
    """
    chunks = []
    remaining = count
    while remaining > 0:
        data = stream.read(remaining)
        if not data:
            break
        chunks.append(data)
        remaining -= len(data)
    if len(chunks) == 1:
        return chunks[0]
    return b"".join(chunks)
