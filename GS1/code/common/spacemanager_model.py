from __future__ import annotations

from dataclasses import dataclass

from .rom import phys, read_u32


@dataclass(frozen=True)
class FreeBlock:
    start: int
    size: int

    @property
    def end(self) -> int:
        return self.start + self.size


def zero_runs(data: bytes, min_size: int = 32) -> list[FreeBlock]:
    blocks: list[FreeBlock] = []
    i = 0
    while i < len(data):
        if data[i] != 0:
            i += 1
            continue
        start = i
        while i < len(data) and data[i] == 0:
            i += 1
        size = i - start
        if size >= min_size:
            blocks.append(FreeBlock(start=start, size=size))
    return blocks


def simple_find_space(blocks: list[FreeBlock], size: int) -> int | None:
    for block in sorted(blocks, key=lambda b: b.size):
        aligned = (block.start + 3) & ~3
        if aligned + size <= block.end:
            return aligned | 0x08000000
    return None

