from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class IpsRecord:
    offset: int
    data: bytes
    is_rle: bool = False

    @property
    def end(self) -> int:
        return self.offset + len(self.data)


@dataclass(frozen=True)
class IpsPatch:
    records: list[IpsRecord]
    truncate_size: int | None = None


def parse_ips(path: str | Path) -> IpsPatch:
    data = Path(path).read_bytes()
    if data[:5] != b"PATCH":
        raise ValueError(f"{path} is not an IPS patch (missing PATCH header)")

    pos = 5
    records: list[IpsRecord] = []
    truncate_size: int | None = None

    while pos < len(data):
        if data[pos : pos + 3] == b"EOF":
            pos += 3
            if pos + 3 <= len(data):
                truncate_size = int.from_bytes(data[pos : pos + 3], "big")
            break

        if pos + 5 > len(data):
            raise ValueError(f"truncated IPS record header at 0x{pos:x}")

        offset = int.from_bytes(data[pos : pos + 3], "big")
        pos += 3
        size = int.from_bytes(data[pos : pos + 2], "big")
        pos += 2

        if size == 0:
            if pos + 3 > len(data):
                raise ValueError(f"truncated IPS RLE record at 0x{pos:x}")
            rle_len = int.from_bytes(data[pos : pos + 2], "big")
            pos += 2
            value = data[pos]
            pos += 1
            records.append(IpsRecord(offset, bytes([value]) * rle_len, True))
        else:
            if pos + size > len(data):
                raise ValueError(f"truncated IPS literal record at 0x{pos:x}")
            records.append(IpsRecord(offset, data[pos : pos + size], False))
            pos += size

    return IpsPatch(records=records, truncate_size=truncate_size)


def apply_ips(source: bytes, patch: IpsPatch) -> bytes:
    out_len = max(len(source), *(record.end for record in patch.records), patch.truncate_size or 0)
    out = bytearray(source)
    if len(out) < out_len:
        out.extend(b"\x00" * (out_len - len(out)))

    for record in patch.records:
        out[record.offset : record.end] = record.data

    if patch.truncate_size is not None:
        del out[patch.truncate_size :]

    return bytes(out)


def changed_ranges(records: list[IpsRecord]) -> list[tuple[int, int]]:
    ranges = sorted((record.offset, record.end) for record in records)
    if not ranges:
        return []

    merged: list[tuple[int, int]] = [ranges[0]]
    for start, end in ranges[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def clustered_changed_ranges(records: list[IpsRecord], max_gap: int = 64) -> list[tuple[int, int]]:
    """Merge changed ranges that are close but not byte-contiguous.

    IPS patches often encode many tiny edits inside one logical table/asset.
    A gap-tolerant cluster view is much better for reverse-engineering than
    the exact byte-level range list.
    """
    ranges = sorted((record.offset, record.end) for record in records)
    if not ranges:
        return []

    clusters: list[tuple[int, int]] = [ranges[0]]
    for start, end in ranges[1:]:
        prev_start, prev_end = clusters[-1]
        if start <= prev_end + max_gap:
            clusters[-1] = (prev_start, max(prev_end, end))
        else:
            clusters.append((start, end))
    return clusters
