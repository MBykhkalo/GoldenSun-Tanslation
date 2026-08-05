from __future__ import annotations

from dataclasses import dataclass

GBA_BASE = 0x08000000


@dataclass(frozen=True)
class RomInfo:
    title: str
    game_code: str
    version: int
    file_table: int
    size: int


def phys(addr: int) -> int:
    return addr & 0x01FFFFFF


def read_u8(data: bytes, addr: int) -> int:
    off = phys(addr)
    if off >= len(data):
        return 0
    return data[off]


def read_u16(data: bytes, addr: int) -> int:
    off = phys(addr)
    if off + 2 > len(data):
        return 0
    return int.from_bytes(data[off : off + 2], "little")


def read_u32(data: bytes, addr: int) -> int:
    off = phys(addr)
    if off + 4 > len(data):
        return 0
    return int.from_bytes(data[off : off + 4], "little")


def is_rom_ptr(value: int, rom_size: int) -> bool:
    off = phys(value)
    return GBA_BASE <= value < 0x0A000000 and 0 <= off < rom_size


def detect_rom(data: bytes) -> RomInfo:
    title = data[0xA0:0xAC].rstrip(b"\x00 ").decode("ascii", "replace")
    game_code = data[0xAC:0xB0].decode("ascii", "replace")
    sig = read_u32(data, 0x080000AB)

    if sig == 0x53474141:  # "AAGS" == Golden Sun 1, see dllmain.cpp::loadFile
        version = 0
        region_byte = read_u8(data, 0x080000AF)
        file_table = {
            ord("E"): 0x08320000,
            ord("I"): 0x08320000,
            ord("J"): 0x08317000,
            ord("D"): 0x0831FE00,
            ord("F"): 0x08321800,
            ord("S"): 0x08321800,
        }.get(region_byte)
        if file_table is None:
            raise ValueError(f"unsupported GS1 region byte 0x{region_byte:02x}")
    elif sig == 0x474D4241:
        version = 10
        file_table = 0x08800000
    elif sig == 0x4D544241:
        version = 11
        file_table = 0x08C28000
    else:
        version = 1
        file_table = 0x08680000

    return RomInfo(title=title, game_code=game_code, version=version, file_table=file_table, size=len(data))


def font_table_offset(data: bytes, info: RomInfo) -> int:
    if info.version == 0:
        ptr = read_u32(data, info.file_table + 0x4C)
    elif info.version == 1:
        ptr = read_u32(data, 0x0868004C)
    elif info.version == 10:
        ptr = read_u32(data, 0x08800048)
    elif info.version == 11:
        ptr = read_u32(data, 0x08C28078)
    else:
        raise ValueError(f"unsupported version {info.version}")
    return phys(ptr + 0x420)


def root_table(data: bytes, info: RomInfo) -> int:
    return read_u32(data, info.file_table + 0x10)


def string_length_table(data: bytes, info: RomInfo) -> int:
    root = root_table(data, info)
    offsets = {0: 0x5CC, 1: 0x5DC, 10: 0x694, 11: 0x52C}
    return read_u32(data, root + offsets[info.version])


def string_model_table(data: bytes, info: RomInfo) -> int:
    root = root_table(data, info)
    offsets = {0: 0x56C, 1: 0x578, 10: 0x628, 11: 0x4A4}
    return read_u32(data, root + offsets[info.version])


def scan_string_groups(data: bytes, info: RomInfo, max_groups: int = 4096) -> list[tuple[int, int, int]]:
    table = string_length_table(data, info)
    groups: list[tuple[int, int, int]] = []
    for group in range(max_groups):
        data_ptr = read_u32(data, table + group * 8)
        len_ptr = read_u32(data, table + group * 8 + 4)
        if not (is_rom_ptr(data_ptr, info.size) and is_rom_ptr(len_ptr, info.size)):
            break
        groups.append((group, data_ptr, len_ptr))
    return groups


def range_overlaps(start: int, end: int, other_start: int, other_end: int) -> bool:
    return start < other_end and other_start < end

