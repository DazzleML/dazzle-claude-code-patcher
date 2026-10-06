"""Format detection and the unsupported-format refusal (AC11)."""
import pytest

from dcc_patcher.containers import UnsupportedFormat, detect, open_container


def pe_stub():
    data = bytearray(0x100)
    data[:2] = b'MZ'
    data[0x3c:0x40] = (0x80).to_bytes(4, 'little')
    data[0x80:0x84] = b'PE\0\0'
    return bytes(data)


@pytest.mark.parametrize('data, kind', [
    (pe_stub(), 'pe'),
    (b'\x7fELF' + b'\0' * 60, 'elf'),
    (b'\xcf\xfa\xed\xfe' + b'\0' * 60, 'macho'),
    (b'\xca\xfe\xba\xbe' + b'\0' * 60, 'macho'),
    (b'MZ' + b'\0' * 62, 'unknown'),        # DOS stub without a PE header
    (b'#!/bin/sh\n', 'unknown'),
    (b'', 'unknown'),
])
def test_detect(data, kind):
    assert detect(data) == kind


@pytest.mark.parametrize('data, words', [
    (b'\x7fELF' + b'\0' * 60, 'ELF'),
    (b'\xcf\xfa\xed\xfe' + b'\0' * 60, 'Mach-O'),
    (b'hello', 'unknown'),
])
def test_unsupported_formats_are_refused_by_name(data, words):
    with pytest.raises(UnsupportedFormat) as err:
        open_container(data)
    assert words in str(err.value)
    assert str(err.value).startswith('unsupported format:')
