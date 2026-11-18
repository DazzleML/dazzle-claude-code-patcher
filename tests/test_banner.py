"""The two banner patches, on the layouts Claude Code has shipped (scenario-led).

Flicker-free: the header and the status line beside it share one module, and from
Claude Code 2.1.323 a second module (the fullscreen tips) says almost the same words.
The patch must name the header's module alone on both layouts, and must not touch
the tips module.

Classic: through 2.1.326 the banner was written twice (a truncating form and a normal
one); 2.1.327 writes it once with the wrap chosen inline. The patch must label every
copy there is, one or two, and refuse any other count.

Synthetic executables are built in memory and never run."""
from pathlib import Path

import pytest

from dcc_patcher import engine, spec
from dcc_patcher.containers import open_container
from tests.bunfixture import make_exe

ROOT = Path(__file__).resolve().parents[1]
FLICKER_FREE = ROOT / 'dcc_patcher' / 'patches' / 'B2-banner-label-flicker-free' / 'patch.toml'

# The header's component and the status line it prints after `/tui fullscreen`.
HEADER = (b'function Hd(){return r(s,{children:[e(n,{bold:!0,children:"Claude Code"})," ",'
          b'e(n,{dimColor:!0,children:["v",Vz]})]})}'
          b'function de(){return r(n,{children:[e(n,{color:"success",children:"Using flicker-free rendering"}),'
          b'e(n,{dimColor:!0,children:" \xb7 if you want to go back, use /tui default"})]})}')
# The fullscreen tips: the same words after a leading space, and no header.
TIPS = (b'function ld(){return r(s,{children:[e(Pa,{}),'
        b'e(n,{color:"autoAccept",children:" Using flicker-free rendering"})]})}')

# Where the two components live, as each build lays them out (module sources in order).
LAYOUTS = {
    'through-2.1.322': [b'other();', HEADER + TIPS],          # one module holds both
    '2.1.323': [b'other();', HEADER, TIPS],                    # the tips moved out
}


@pytest.mark.parametrize('layout', LAYOUTS)
def test_the_flicker_free_banner_is_found_in_the_header_module_alone(layout):
    # CONSEQUENCE: 6 -- an ambiguous marker fails the whole build closed, so every
    # patch is lost and the launcher runs stock (seen live on 2.1.323)
    sources = LAYOUTS[layout]
    image, results = engine.apply(open_container(make_exe(sources)), [spec.load(FLICKER_FREE)])
    assert [(r.status, r.module) for r in results] == [('applies', 1)]
    out = open_container(image)
    assert b'children:"Dazzle Claude Code"' in out.source(1)
    assert f'" dcc {engine.DISPLAY_VERSION}"'.encode() in out.source(1)
    for k in range(2, len(sources)):
        assert out.source(k) == sources[k]                     # the tips module is as it was


CLASSIC = ROOT / 'dcc_patcher' / 'patches' / 'B-banner-label' / 'patch.toml'
ONE = b'[e(n,{bold:!0,children:"Claude Code"})," ",r(n,{dimColor:!0,children:["v",Z]})]'

# The classic banner as each build writes it, and how many copies it holds.
CLASSIC_BANNERS = {
    'through-2.1.326': (b'zt=!W&&r(oe,{children:[R?r(n,{wrap:"truncate",children:' + ONE
                        + b'}):r(n,{children:' + ONE + b'}),x]});', 2),
    '2.1.327': (b'Xt=!J&&r(ie,{children:[r(n,{wrap:v?"truncate":"wrap",children:' + ONE + b'}),x]});', 1),
}


@pytest.mark.parametrize('shape', CLASSIC_BANNERS)
def test_the_classic_banner_is_labelled_wherever_it_is_written(shape):
    # CONSEQUENCE: 6 -- a count the patch does not expect fails the whole build
    # closed, and the launcher runs stock (seen live on 2.1.327)
    source, copies = CLASSIC_BANNERS[shape]
    res = engine.locate(spec.load(CLASSIC), source)
    assert res.status == 'applies', res.detail
    assert res.edits[0].count == copies
    assert res.source.count(b'children:"Dazzle Claude Code"') == copies
    assert b'children:"Claude Code"' not in res.source


def test_the_classic_banner_written_three_times_is_refused():
    # A third copy is a layout nobody has looked at: label none of them.
    res = engine.locate(spec.load(CLASSIC), (b'a=' + ONE + b';') * 3)
    assert res.status == 'needs-human' and res.source is None
    assert (res.edits[0].status, res.edits[0].count) == ('AMBIGUOUS', 3)
