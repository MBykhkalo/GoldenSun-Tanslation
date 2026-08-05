from __future__ import annotations

from dataclasses import dataclass

from .rom import RomInfo, read_u8, read_u16, read_u32, string_length_table, string_model_table


class DecodeError(RuntimeError):
    pass


def u32(value: int) -> int:
    return value & 0xFFFFFFFF


@dataclass
class DecodedString:
    index: int
    raw_codes: list[int]
    terminated: bool


class StringCodec:
    """Python port of GSdatahandler/src/strings.cpp decode path.

    Stage 1 only needs the decoder to classify/read existing strings.
    The encoder (`CompressStr`) is intentionally left for Stage 3.
    """

    def __init__(self, rom: bytes, info: RomInfo):
        self.rom = rom
        self.info = info
        self.length_table = string_length_table(rom, info)
        self.model_table = string_model_table(rom, info)

    def initialize(self, index: int) -> list[int]:
        r = [0] * 15
        r[1] = index
        group = r[1] >> 8
        entry = self.length_table + (group << 3)
        r[2] = read_u32(self.rom, entry)
        r[4] = read_u32(self.rom, entry + 4)
        r[1] &= 0xFF

        while r[1] != 0:
            n = read_u8(self.rom, r[4])
            r[4] += 1
            r[2] += n
            if n == 0xFF:
                continue
            r[1] -= 1

        r[3] = 1
        rem = r[2] & 3
        if rem != 0:
            shift = (rem << 3) - r[3]
            r[2] = (r[2] | 3) ^ 3
            r[3] = read_u32(self.rom, r[2])
            r[2] += 4
            r[3] = u32((r[3] >> 1) | (1 << 31))
            r[3] >>= shift
        return r

    def next_char(self, r: list[int]) -> int:
        entry = self.model_table + ((r[1] >> 8) << 3)
        r[4] = read_u32(self.rom, entry)
        r[5] = read_u32(self.rom, entry + 4)
        lo = (r[1] & 0xFF) << 1
        r[5] = read_u16(self.rom, r[5] + lo)
        r[4] += r[5]
        r[5] = r[4]
        r[12] = 1
        r[6] = r[4] & 3
        if r[6] != 0:
            shift = (r[6] << 3) - r[12]
            r[4] = (r[4] | 3) ^ 3
            r[12] = read_u32(self.rom, r[4])
            r[4] += 4
            r[12] = u32((r[12] >> 1) | (1 << 31))
            r[12] >>= shift
            r[6] = 0

        while True:
            c = (r[12] & 1) == 1
            r[12] >>= 1
            if r[12] == 0:
                r[12] = read_u32(self.rom, r[4])
                r[4] += 4
                c = (r[12] & 1) == 1
                r[12] = u32((r[12] >> 1) | (1 << 31))
            if c:
                break

            c = (r[3] & 1) == 1
            r[3] >>= 1
            if not c:
                continue
            if r[3] == 0:
                r[3] = read_u32(self.rom, r[2])
                r[2] += 4
                c = (r[3] & 1) == 1
                r[3] = u32((r[3] >> 1) | (1 << 31))
            if not c:
                continue

            r[1] = 0
            while True:
                c = (r[12] & 1) == 1
                r[12] >>= 1
                if c:
                    if r[12] == 0:
                        r[12] = read_u32(self.rom, r[4])
                        r[4] += 4
                        c = (r[12] & 1) == 1
                        r[12] = u32((r[12] >> 1) | (1 << 31))
                        if not c:
                            r[1] += 1
                            continue
                    r[6] += 1
                    r[1] -= 1
                    if r[1] >= 0:
                        continue
                    break

                c = (r[12] & 1) == 1
                r[12] >>= 1
                if c:
                    if r[12] != 0:
                        r[6] += 1
                        continue
                    r[12] = read_u32(self.rom, r[4])
                    r[4] += 4
                    c = (r[12] & 1) == 1
                    r[12] = u32((r[12] >> 1) | (1 << 31))
                    if not c:
                        r[1] += 2
                    if c:
                        r[6] += 1
                    continue

                c = (r[12] & 1) == 1
                r[12] >>= 1
                if c:
                    r[1] += 1
                    if r[12] != 0:
                        r[6] += 1
                        continue
                    r[12] = read_u32(self.rom, r[4])
                    r[4] += 4
                    c = (r[12] & 1) == 1
                    r[12] = u32((r[12] >> 1) | (1 << 31))
                    if not c:
                        r[1] += 2
                    if c:
                        r[6] += 1
                    continue

                c = (r[12] & 1) == 1
                r[12] >>= 1
                if c:
                    r[1] += 2
                    if r[12] != 0:
                        r[6] += 1
                        continue
                    r[12] = read_u32(self.rom, r[4])
                    r[4] += 4
                    c = (r[12] & 1) == 1
                    r[12] = u32((r[12] >> 1) | (1 << 31))
                    if not c:
                        r[1] += 2
                    if c:
                        r[6] += 1
                    continue

                r[1] += 4

        odd = (r[6] & 1) == 1
        r[1] = r[6] >> 1
        r[6] += r[1]
        r[6] = r[5] - r[6]
        b1 = read_u8(self.rom, r[6] - 1)
        b0 = read_u8(self.rom, r[6] - 2)
        if odd:
            value = b0 | ((b1 & 0x0F) << 8)
        else:
            value = (b1 << 4) | (b0 >> 4)
        r[0] = value
        r[1] = value
        return value

    def decode_codes(self, index: int, max_chars: int = 519) -> DecodedString:
        r = self.initialize(index)
        out: list[int] = []
        for _ in range(max_chars):
            c = self.next_char(r)
            out.append(c)
            if c == 0:
                return DecodedString(index=index, raw_codes=out, terminated=True)
        return DecodedString(index=index, raw_codes=out, terminated=False)

    def decode_bytes(self, index: int, max_chars: int = 519) -> bytes:
        codes = self.decode_codes(index, max_chars=max_chars)
        if any(c > 0xFF for c in codes.raw_codes):
            raise DecodeError(f"string {index} emitted non-byte code")
        return bytes(codes.raw_codes)

