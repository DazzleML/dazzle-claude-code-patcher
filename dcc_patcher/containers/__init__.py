"""Container formats: getting Claude Code's JavaScript in and out of its executable.

Claude Code's native CLI is a Bun-compiled executable. Each operating system packs
the Bun module graph into a different executable format (PE on Windows, ELF on
Linux, Mach-O on macOS). Everything above this package -- patch specs, the engine,
the check report -- talks only to the `Container` interface, so supporting a new
platform means adding one module here, nothing else.

Supported: PE (Windows). ELF and Mach-O are detected and rejected with a clear
message (design document 2026-10-05, ojura addendum: AC11).
"""
from __future__ import annotations

from typing import Protocol


class ContainerError(Exception):
    """The file is a supported format but not a usable Bun executable, or a
    rewrite failed its own verification."""


class UnsupportedFormat(ContainerError):
    """The file is not in a format dcc-patcher can patch yet."""

    def __init__(self, kind: str):
        self.kind = kind
        super().__init__(f'unsupported format: {kind}')


class Container(Protocol):
    """One Bun executable, read into memory. Module indices are positions in the
    Bun module table; they change from build to build, so callers find modules by
    a marker string (`find_module`) rather than by index or chunk name."""

    format: str
    count: int

    def module(self, k: int) -> dict:
        """Name, source span and bytecode span of module k."""

    def source(self, k: int) -> bytes:
        """Module k's embedded JavaScript source."""

    def find_module(self, marker: bytes) -> list[int]:
        """Indices of every module whose source contains marker."""

    def replace_module_source(self, k: int, new_source: bytes) -> bytes:
        """A new executable image in which module k runs new_source."""

    def verify(self, new_image: bytes, k: int, new_source: bytes) -> None:
        """Raise ContainerError unless new_image holds new_source for module k
        and every other module unchanged."""


MACHO_MAGICS = {
    b'\xfe\xed\xfa\xce', b'\xce\xfa\xed\xfe',  # 32-bit
    b'\xfe\xed\xfa\xcf', b'\xcf\xfa\xed\xfe',  # 64-bit
    b'\xca\xfe\xba\xbe',                        # universal (fat)
}


def detect(data: bytes) -> str:
    """The executable format of data: 'pe', 'elf', 'macho' or 'unknown'."""
    if data[:2] == b'MZ' and len(data) >= 0x40:
        pe = int.from_bytes(data[0x3c:0x40], 'little')
        if data[pe:pe + 4] == b'PE\0\0':
            return 'pe'
    if data[:4] == b'\x7fELF':
        return 'elf'
    if data[:4] in MACHO_MAGICS:
        return 'macho'
    return 'unknown'


def open_container(data: bytes) -> Container:
    """The container for data, or UnsupportedFormat naming what it is."""
    kind = detect(data)
    if kind == 'pe':
        from .pe import PeBunExe
        return PeBunExe(data)
    if kind == 'elf':
        raise UnsupportedFormat('ELF (Linux) -- not yet implemented')
    if kind == 'macho':
        raise UnsupportedFormat('Mach-O (macOS) -- not yet implemented')
    raise UnsupportedFormat('unknown (not an executable dcc-patcher recognises)')
