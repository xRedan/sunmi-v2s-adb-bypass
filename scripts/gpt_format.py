"""Offline GPT validation with CRC-checked trailing zero reconstruction."""
import struct
import zlib
def complete_gpt_export(data):
    if data[512:520] != b'EFI PART':
        raise ValueError('Unrecognized GPT; expected 512-byte sectors')
    header_size = struct.unpack_from('<I', data, 524)[0]
    if not 92 <= header_size <= 512:
        raise ValueError('Invalid GPT header size')
    header = bytearray(data[512:512 + header_size])
    expected_crc = struct.unpack_from('<I', header, 16)[0]
    header[16:20] = b'\0' * 4
    if zlib.crc32(header) != expected_crc:
        raise ValueError('GPT header CRC mismatch')
    start, count, entry_size, entries_crc = struct.unpack_from('<QIII', data, 584)
    if not 1 <= count <= 4096 or not 128 <= entry_size <= 4096:
        raise ValueError('Invalid GPT entry format')
    table = data[start * 512:start * 512 + count * entry_size]
    missing = count * entry_size - len(table)
    # This MTKClient export omits one trailing sector. Accept reconstruction
    # only when zero-padding reproduces the CRC in the verified GPT header.
    if 0 < missing <= 512:
        candidate = table + b'\0' * missing
        if zlib.crc32(candidate) == entries_crc:
            data += b'\0' * missing
            table = candidate
    if len(table) != count * entry_size or zlib.crc32(table) != entries_crc:
        raise ValueError('Incomplete GPT table or CRC mismatch')
    return data

def partition_sizes(data):
    data = complete_gpt_export(data)
    start, count, entry_size, _ = struct.unpack_from('<QIII', data, 584)
    table = data[start * 512:start * 512 + count * entry_size]
    sizes = {}
    for index in range(count):
        entry = table[index * entry_size:(index + 1) * entry_size]
        if entry[:16] == b'\0' * 16:
            continue
        first, last = struct.unpack_from('<QQ', entry, 32)
        name = entry[56:128].decode('utf-16-le').split('\0', 1)[0]
        if last < first or name in sizes:
            raise ValueError('Invalid or duplicate GPT partition entry')
        sizes[name] = (last - first + 1) * 512
    return sizes
