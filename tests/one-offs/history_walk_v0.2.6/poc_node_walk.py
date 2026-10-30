"""POC: run patch H's real JavaScript (prelude + walker replacement from patch.toml) under
Node over real session files, shipped vs proposed prelude, and compare each result with
the Python simulation (sim_v026.walk, modes h4 and h7). Read-only on the session files.

Usage: python poc_node_walk.py [<session.jsonl> ...]   (no args: every file with a boundary)
"""
import json, os, re, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, 'C:/code/claude-projects/dazzle-claude-code-patcher')
import sim_v026                                   # noqa: E402
from dcc_patcher import spec                      # noqa: E402

H = Path('C:/code/claude-projects/dazzle-claude-code-patcher/dcc_patcher/patches/H-history-past-compaction/patch.toml')
NAMES = {'g': 'g', 'h': 'h', 's': 's', 'w': 'w', 'Dw': 'D', 'em': 'e', 'fb': 'fb', 'fbargs': 'e,h,g', 'tel': 'tel'}
RULE2_OLD = 'how="preserved";for(let k=U.length-1;k>=0;k--)if(!g.has(U[k])&&e.has(U[k])){w=U[k];break}'
RULE2_NEW = ('how="preserved";let Us=new Set(U),br=u=>{for(let n=0;n<=U.length&&e.has(u);n++){let p=e.get(u).parentUuid;'
             'if(!p)return!1;if(g.has(p))return!0;if(!Us.has(p))return!1;u=p}return!1};'
             'for(let k=U.length-1;k>=0;k--)if(!g.has(U[k])&&e.has(U[k])&&!br(U[k])){w=U[k];break}')
LOG_OLD = 'globalThis.__dzLog?.(`walk: boundary'
LAST_RESORT = ('if((!w||!e.has(w)||g.has(w))&&L){how="preserved-branch";w=void 0;'
               'for(let k=U.length-1;k>=0;k--)if(!g.has(U[k])&&e.has(U[k])){w=U[k];break}}')


def preludes():
    patch = spec.load(H)
    shipped = patch.prelude
    assert shipped.count(RULE2_OLD) == 1 and shipped.count(LOG_OLD) == 1
    proposed = shipped.replace(RULE2_OLD, RULE2_NEW).replace(LOG_OLD, LAST_RESORT + LOG_OLD)
    walker = next(e for e in patch.edits if e.name.startswith('walker'))
    fragment = re.sub(r'@@(\w+)@@', lambda m: NAMES[m.group(1)], walker.replace)
    assert '@@' not in fragment
    return shipped, proposed, fragment


def program(shipped, proposed, fragment):
    return r'''
const fs=require("fs"),rl=require("readline");
const logs=[];globalThis.__dzLog=(m)=>logs.push(m);
function tel(){}
const ts=r=>{const t=Date.parse(r.timestamp);return Number.isNaN(t)?null:t/1000};
// stock's Tso (2.1.302), verbatim in shape: strict isSidechain comparison, 5000 ms window
function fb(e,n,r){let s=new Date(n.timestamp).getTime();if(Number.isNaN(s))return;let h,y=1/0;for(let S of e.values()){if(r.has(S.uuid))continue;if(S.isSidechain!==n.isSidechain)continue;let w=new Date(S.timestamp).getTime();if(Number.isNaN(w))continue;let D=s-w;if(D>=0&&D<=5000&&D<y)y=D,h=S}return h}
function walk(e,start){let s=[],g=new Set,h=start;while(h){if(g.has(h.uuid))break;''' + fragment + r'''h=D}return s}
const isB=r=>r.type==="system"&&r.subtype==="compact_boundary";
async function main(){
  const path=process.argv[2];const e0=new Map(),line=new Map();let n=0;
  for await(const l of rl.createInterface({input:fs.createReadStream(path)})){n++;const t=l.trim();if(!t)continue;let d;try{d=JSON.parse(t)}catch{continue}if(d.uuid&&!e0.has(d.uuid)){e0.set(d.uuid,d);line.set(d.uuid,n)}}
  const out={};
  for(const [mode,src] of [["shipped",SHIPPED],["proposed",PROPOSED]]){
    const e=new Map(e0);globalThis.__dzOrigParent={};
    // the prune's in-memory relink for the last boundary, as sim_v026 does it
    let meta=null,ri=-1,si=-1,i=0;for(const r of e.values()){if(isB(r)){si=i;const m=r.compactMetadata||{};if(m.preservedMessages||m.preservedSegment){meta=m;ri=i}}i++}
    if(meta&&ri===si){const D=meta.preservedMessages;if(D&&D.uuids&&D.uuids.every(u=>e.has(u))){const G=D.uuids,anchor=D.anchorUuid,tail=G[G.length-1];globalThis.__dzOrigParent[G[0]]=e.get(G[0]).parentUuid;let prev=anchor;for(const u of G){e.set(u,{...e.get(u),parentUuid:prev});prev=u}for(const [u,r] of [...e]){if(r.parentUuid===anchor&&u!==G[0])e.set(u,{...r,parentUuid:tail})}}}
    (0,eval)(src);
    const main=[...e.values()].filter(r=>(r.type==="user"||r.type==="assistant")&&!r.isSidechain);
    logs.length=0;const chain=walk(e,main[main.length-1]);const first=chain[chain.length-1];
    out[mode]={crossed:logs.filter(l=>l.startsWith("walk: boundary")&&!/-> undefined$/.test(l)).length,n:chain.length,first:first.uuid,firstLine:line.get(first.uuid),via:logs.filter(l=>l.startsWith("walk: boundary")).map(l=>l.replace(/.*via=(\S+) -> (\S+).*/,"$1 -> $2").replace(/-> (\S{8})\S*/,"-> $1"))};
  }
  process.stdout.write(JSON.stringify(out));
}
const SHIPPED=''' + json.dumps(shipped) + ''',PROPOSED=''' + json.dumps(proposed) + ''';
main();
'''


if __name__ == '__main__':
    node = shutil.which('node')
    shipped, proposed, fragment = preludes()
    js = HERE / 'walk_file.js'
    js.write_text(program(shipped, proposed, fragment), encoding='utf-8')
    (HERE / 'prelude_proposed.js').write_text(proposed, encoding='utf-8')
    files = [Path(a) for a in sys.argv[1:]] or [p for p in sorted(sim_v026.root.glob('*/*.jsonl')) if b'"compact_boundary"' in p.read_bytes()]
    mism = 0
    for p in files:
        r = subprocess.run([node, '--max-old-space-size=4096', str(js), str(p)], capture_output=True, text=True, timeout=600)
        if r.returncode:
            print(p.name[:8], 'NODE ERROR', r.stderr[-300:]); continue
        out = json.loads(r.stdout)
        e, line_of = sim_v026.load(p)
        for mode, sim_mode in (('shipped', 'h4'), ('proposed', 'h7')):
            c, n, reached, first = sim_v026.walk(e, sim_mode, None, line_of)
            js_r = out[mode]
            same = (c, n, first[0]) == (js_r['crossed'], js_r['n'], js_r['first'])
            mism += 0 if same else 1
            flag = 'ok ' if same else 'MISMATCH'
            print(f"{flag} {p.name[:8]} {mode:<8} node: crossed={js_r['crossed']} rows={js_r['n']} first=line {js_r['firstLine']} | sim {sim_mode}: crossed={c} rows={n} first=line {first[1]} reached={reached}")
            if len(files) <= 3:
                print('      via:', '; '.join(js_r['via']))
    print(f'\n{len(files)} files, {mism} mismatches between Node and the simulation')
