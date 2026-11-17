"""把 docs/COMMANDS.md 轉成互動式網頁 docs/commands.html。

用法（在 ha2-lab 資料夾）：
    python tools/build_commands_html.py
    python tools/build_commands_html.py --fragment out.html   # 只輸出 <body> 內容（給不需要 <html> 外框的平台）

需要：pip install markdown
"""
import html
import json
import re
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "COMMANDS.md"
OUT = ROOT / "docs" / "commands.html"

MD_EXT = ["tables", "fenced_code", "sane_lists"]


def md(text):
    return markdown.markdown(text, extensions=MD_EXT)


def places(where):
    """從「在哪裡執行」的文字判斷要顯示哪些位置標籤。"""
    tags = []
    rules = [
        ("windows", r"Windows|檔案總管|PowerShell|cmd"),
        ("ctl", r"ctl|視窗 [AB]"),
        ("vmware", r"VMware"),
        ("vm", r"app-tpl"),
        ("browser", r"瀏覽器|Discord"),
    ]
    for key, pat in rules:
        if re.search(pat, where):
            tags.append(key)
    return tags


PLACE_NAME = {"windows": "Windows", "ctl": "ctl", "vmware": "VMware", "vm": "範本機", "browser": "瀏覽器"}


def split_segments(body):
    """把一個小步驟切成：說明、在哪裡執行、正確結果、不一樣時。"""
    segs, cur_kind, cur = [], "text", []
    where = ""
    for line in body.split("\n"):
        m = re.match(r"\*\*在哪裡執行：\*\*\s*(.*)", line)
        if m:
            where = m.group(1).strip()
            continue
        if line.startswith("**✅"):
            segs.append((cur_kind, "\n".join(cur)))
            cur_kind, cur = "ok", [line]
            continue
        if line.startswith("**❌"):
            segs.append((cur_kind, "\n".join(cur)))
            cur_kind, cur = "bad", [line]
            continue
        # 正確結果之後若出現新的指令說明（例如「復原：」），回到一般區塊
        if cur_kind == "ok" and re.match(r"^[^\s|>`*-].*：$", line) and not line.startswith("**"):
            segs.append((cur_kind, "\n".join(cur)))
            cur_kind, cur = "text", [line]
            continue
        cur.append(line)
    segs.append((cur_kind, "\n".join(cur)))
    return where, [(k, t) for k, t in segs if t.strip()]


def strip_label(kind, text):
    if kind == "ok":
        text = re.sub(r"^\*\*✅ 正確結果[^*]*\*\*[:：]?\s*", "", text)
    if kind == "bad":
        text = re.sub(r"^\*\*❌ 不一樣時[^*]*\*\*[:：]?\s*", "", text)
    return text


def render_segment(kind, text):
    text = strip_label(kind, text)
    inner = md(text)
    if kind in ("ok", "bad"):
        # 有標語言（bash、powershell）的是可執行的指令，其餘是「應該看到的畫面」
        inner = re.sub(r'<pre>(?=<code class="language-)', '<pre class="cmd">', inner)
        inner = inner.replace("<pre>", '<pre class="out">')
    if kind == "ok":
        return f'<div class="seg ok"><p class="seg-label">正確結果：看到這個才進下一步</p>{inner}</div>'
    if kind == "bad":
        return f'<div class="seg bad"><p class="seg-label">不一樣時</p>{inner}</div>'
    inner = inner.replace("<pre>", '<pre class="cmd">')
    return f'<div class="seg text">{inner}</div>'


def slug_step(n):
    return f"s{n}"


def parse():
    src = SRC.read_text(encoding="utf-8")
    title = re.search(r"^# (.+)$", src, re.M).group(1).strip()
    parts = re.split(r"^## ", src, flags=re.M)
    intro_md = parts[0].split("\n", 1)[1] if "\n" in parts[0] else ""
    prelude, steps, appendix = [], [], []
    for part in parts[1:]:
        head, _, rest = part.partition("\n")
        head = head.strip()
        rest = rest.strip().rstrip("-").strip()
        m = re.match(r"步驟 (\d+)：(.+)", head)
        if m:
            n = int(m.group(1))
            subs = []
            chunks = re.split(r"^### ", rest, flags=re.M)
            lead = chunks[0].strip()
            for ch in chunks[1:]:
                sh, _, sb = ch.partition("\n")
                sm = re.match(r"(\d+-\d+)\s+(.+)", sh.strip())
                sid, stitle = (sm.group(1), sm.group(2)) if sm else (sh.strip(), sh.strip())
                where, segs = split_segments(sb.strip().rstrip("-").strip())
                subs.append({
                    "id": "s" + sid, "num": sid, "title": stitle,
                    "where": md(where).removeprefix("<p>").removesuffix("</p>") if where else "",
                    "places": places(where),
                    "html": "".join(render_segment(k, t) for k, t in segs),
                })
            steps.append({"n": n, "id": slug_step(n), "title": m.group(2).strip(),
                          "lead": md(lead) if lead else "", "subs": subs})
        elif head.startswith("附錄"):
            appendix.append({"title": head, "html": md(rest).replace("<pre>", '<pre class="cmd">')})
        elif head == "目錄":
            continue
        else:
            prelude.append({"title": head, "html": md(rest)})
    return title, md(intro_md.split("---")[0]), prelude, steps, appendix


CSS = r"""
:root{
  /* 版面：左側步驟導覽 + 右側小步驟卡片；終端機風格的指令區塊 */
  --bg:#F2F5F7; --panel:#FFFFFF; --ink:#13202B; --muted:#56677A; --line:#D7DFE6;
  --accent:#0B7A8F; --accent-soft:#DDF1F4; --term:#0F1A24; --term-ink:#DCE8EF; --term-dim:#7F95A6;
  --ok:#1D7A4C; --ok-soft:#E3F3EA; --bad:#B4531C; --bad-soft:#FBEDE3;
  --c-win:#2F6FD1; --c-ctl:#0B7A8F; --c-vmw:#7A4FC4; --c-vm:#B07A12; --c-web:#C2410C;
  --f-text:'Noto Sans TC','PingFang TC','Microsoft JhengHei',system-ui,sans-serif;
  --f-mono:'JetBrains Mono','Cascadia Mono',Consolas,ui-monospace,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#0E151C; --panel:#151F29; --ink:#E4ECF2; --muted:#93A6B6; --line:#26343F;
  --accent:#3CC2D8; --accent-soft:#12323A; --term:#0A1016; --term-ink:#DCE8EF; --term-dim:#6F8597;
  --ok:#55C98C; --ok-soft:#12291D; --bad:#F09A62; --bad-soft:#2E1C12;
  --c-win:#6EA4F5; --c-ctl:#3CC2D8; --c-vmw:#B59AF0; --c-vm:#E2B24C; --c-web:#F59A6A; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0E151C; --panel:#151F29; --ink:#E4ECF2; --muted:#93A6B6; --line:#26343F;
  --accent:#3CC2D8; --accent-soft:#12323A; --term:#0A1016; --term-ink:#DCE8EF; --term-dim:#6F8597;
  --ok:#55C98C; --ok-soft:#12291D; --bad:#F09A62; --bad-soft:#2E1C12;
  --c-win:#6EA4F5; --c-ctl:#3CC2D8; --c-vmw:#B59AF0; --c-vm:#E2B24C; --c-web:#F59A6A; color-scheme:dark}
*{box-sizing:border-box}
html{scroll-padding-top:150px}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.7 var(--f-text);
  padding-left:max(0px,env(safe-area-inset-left,0px));padding-right:max(0px,env(safe-area-inset-right,0px))}
body::before{content:"";position:fixed;inset:0 0 auto;height:env(safe-area-inset-top,0px);z-index:30;background:var(--panel)}
a{color:var(--accent)}
code{font-family:var(--f-mono);font-size:.88em;background:var(--accent-soft);padding:.1em .35em;border-radius:4px;overflow-wrap:anywhere}
.top{position:sticky;top:env(safe-area-inset-top,0px);z-index:20;background:var(--panel);border-bottom:1px solid var(--line)}
.top-in{max-width:1280px;margin:0 auto;padding:12px max(16px,env(safe-area-inset-right,0px)) 12px max(16px,env(safe-area-inset-left,0px));display:flex;flex-wrap:wrap;gap:10px 20px;align-items:center}
.brand{display:flex;flex-direction:column;min-width:0;flex:1 1 300px}
.brand b{font-size:17px;letter-spacing:.02em}
.brand span{font-size:12.5px;color:var(--muted)}
.prog{flex:1 1 220px;display:flex;align-items:center;gap:10px;font-variant-numeric:tabular-nums;font-size:13px;color:var(--muted)}
.bar{flex:1;height:8px;background:var(--line);border-radius:99px;overflow:hidden}
.bar i{display:block;height:100%;width:0;background:var(--accent);transition:width .3s}
.tools{display:flex;gap:8px;flex-wrap:wrap;flex:1 1 100%}
.tools input{font:inherit;font-size:13px;color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:6px 10px;min-width:0}
#q{flex:1 1 200px}
#dir{flex:0 1 230px;font-family:var(--f-mono)}
.tools label{font-size:12.5px;color:var(--muted);display:flex;align-items:center;gap:6px;flex:0 1 auto}
.btn{font:inherit;font-size:13px;border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:8px;padding:6px 12px;cursor:pointer}
.btn:hover{border-color:var(--accent);color:var(--accent)}
.btn:focus-visible,.tools input:focus-visible,summary:focus-visible,.done input:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.wrap{max-width:1280px;margin:0 auto;display:grid;grid-template-columns:270px minmax(0,1fr);gap:28px;padding:24px max(16px,env(safe-area-inset-right,0px)) 80px max(16px,env(safe-area-inset-left,0px))}
nav.side{position:sticky;top:calc(env(safe-area-inset-top,0px) + 130px);align-self:start;max-height:calc(100vh - 150px);overflow:auto;font-size:13.5px}
nav.side a{display:grid;grid-template-columns:26px 1fr auto;gap:6px;align-items:baseline;padding:6px 8px;border-radius:8px;color:var(--ink);text-decoration:none}
nav.side a:hover{background:var(--accent-soft)}
nav.side a.cur{background:var(--accent-soft);color:var(--accent);font-weight:700}
nav.side .n{font-family:var(--f-mono);color:var(--muted);font-size:12px}
nav.side .cnt{font-family:var(--f-mono);font-size:11.5px;color:var(--muted);font-variant-numeric:tabular-nums}
nav.side a.all .cnt{color:var(--ok);font-weight:700}
nav.side .sep{margin:10px 8px 4px;font-size:11.5px;letter-spacing:.08em;color:var(--muted)}
.jump{display:none}
main{min-width:0}
.intro{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:6px 22px 14px}
.intro details{border-top:1px solid var(--line);padding:8px 0}
.intro summary{cursor:pointer;font-weight:700;padding:4px 0}
.legend{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}
.step{margin-top:40px}
.step-h{display:flex;align-items:baseline;gap:14px;border-bottom:2px solid var(--ink);padding-bottom:8px}
.step-h .num{font-family:var(--f-mono);font-size:13px;color:var(--panel);background:var(--ink);border-radius:6px;padding:2px 8px;flex:none}
.step-h h2{margin:0;font-size:22px;line-height:1.35;text-wrap:balance}
.step-h .sc{margin-left:auto;font-family:var(--f-mono);font-size:12.5px;color:var(--muted);white-space:nowrap}
.lead{color:var(--muted)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;margin-top:16px;overflow:hidden}
.card.is-done{border-color:color-mix(in srgb,var(--ok) 45%,var(--line))}
.card-h{display:flex;gap:12px;align-items:flex-start;padding:14px 18px 10px}
.card-h .id{font-family:var(--f-mono);font-weight:700;color:var(--accent);font-size:14px;padding-top:2px;flex:none;min-width:42px}
.card-h h3{margin:0;font-size:17px;line-height:1.45;flex:1;min-width:0}
.card.is-done .card-h h3{color:var(--muted)}
.done{display:flex;align-items:center;gap:6px;font-size:13px;color:var(--muted);white-space:nowrap;cursor:pointer;flex:none}
.done input{width:18px;height:18px;accent-color:var(--ok);cursor:pointer}
.where{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:0 18px 10px 72px;font-size:13.5px;color:var(--muted)}
.where .w-text{min-width:0}
.tag{display:inline-flex;align-items:center;gap:5px;font-size:12px;font-weight:700;border-radius:99px;padding:1px 9px;border:1.5px solid currentColor;white-space:nowrap}
.tag::before{content:"";width:7px;height:7px;border-radius:50%;background:currentColor}
.t-windows{color:var(--c-win)} .t-ctl{color:var(--c-ctl)} .t-vmware{color:var(--c-vmw)} .t-vm{color:var(--c-vm)} .t-browser{color:var(--c-web)}
.body{padding:0 18px 16px 72px;display:flex;flex-direction:column;gap:12px}
.body p,.body ul,.body ol{margin:0}
.body ol,.body ul{padding-left:1.4em}
.seg.text>*+*{margin-top:10px}
.seg.ok,.seg.bad{border-radius:10px;padding:10px 14px;display:flex;flex-direction:column;gap:8px}
.seg.ok{background:var(--ok-soft);border-left:4px solid var(--ok)}
.seg.bad{background:var(--bad-soft);border-left:4px solid var(--bad)}
.seg-label{font-size:12px;font-weight:700;letter-spacing:.06em}
.seg.ok .seg-label{color:var(--ok)} .seg.bad .seg-label{color:var(--bad)}
blockquote{margin:0;padding:8px 14px;border-left:3px solid var(--line);color:var(--muted);background:var(--bg);border-radius:0 8px 8px 0}
blockquote p{margin:0}
.tbl{overflow-x:auto;max-width:100%}
table{border-collapse:collapse;font-size:13.5px;min-width:100%}
th,td{border-bottom:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}
th{font-size:12.5px;color:var(--muted);font-weight:700}
.seg.ok table,.seg.bad table{background:transparent}
.code{position:relative;border-radius:10px;overflow:hidden;background:var(--term)}
.code .bar2{display:flex;align-items:center;gap:10px;padding:6px 10px 6px 14px;background:color-mix(in srgb,var(--term) 80%,#ffffff 6%);font-size:11.5px;color:var(--term-dim);font-family:var(--f-mono)}
.code .bar2 .k{flex:1;letter-spacing:.06em}
.code pre{margin:0;padding:12px 14px;overflow-x:auto;color:var(--term-ink);font:13.5px/1.6 var(--f-mono);tab-size:4}
.code pre code{background:none;padding:0;font-size:inherit;color:inherit;overflow-wrap:normal;white-space:pre}
.code.out{background:transparent;border:1px dashed color-mix(in srgb,var(--ok) 55%,var(--line))}
.seg.bad .code.out{border-color:color-mix(in srgb,var(--bad) 55%,var(--line))}
.code.out .bar2{background:transparent}
.code.out pre{color:var(--ink)}
.copy{font:600 12px var(--f-text);background:var(--accent);color:#fff;border:0;border-radius:6px;padding:4px 12px;cursor:pointer}
.copy:hover{filter:brightness(1.1)}
.copy:focus-visible{outline:2px solid var(--term-ink);outline-offset:2px}
.copy.ok{background:var(--ok)}
.code.out .copy{background:transparent;color:var(--muted);border:1px solid var(--line)}
.next{align-self:flex-start;margin-top:4px}
.app{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:6px 22px 14px;margin-top:16px}
.app h2{font-size:19px}
.hide{display:none!important}
.empty{padding:40px;text-align:center;color:var(--muted)}
@media (max-width:900px){
  .wrap{grid-template-columns:minmax(0,1fr);gap:0}
  nav.side{display:none}
  .jump{display:block;font:inherit;font-size:13px;color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:6px 8px;flex:1 1 100%;width:100%;max-width:100%;min-width:0}
  .top{position:relative;top:auto}
  html{scroll-padding-top:16px}
  #q,#dir{flex:1 1 100%;width:100%}
  .tools label{flex:1 1 100%}
  .where,.body{padding-left:18px}
}
@media (prefers-reduced-motion:reduce){.bar i{transition:none}}
"""

JS = r"""
(function(){
  const KEY='ha2-commands-done', DIRKEY='ha2-commands-dir', DEF='~/ha2-lab/ansible';
  const load=(k,d)=>{try{const v=localStorage.getItem(k);return v===null?d:JSON.parse(v)}catch(e){return d}};
  const save=(k,v)=>{try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}};
  let done=new Set(load(KEY,[]));
  const cards=[...document.querySelectorAll('.card')];
  const total=cards.length;

  // 指令區塊：加上標題列與複製按鈕
  document.querySelectorAll('pre.cmd,pre.out').forEach(pre=>{
    const out=pre.classList.contains('out');
    const box=document.createElement('div'); box.className='code'+(out?' out':'');
    const bar=document.createElement('div'); bar.className='bar2';
    const k=document.createElement('span'); k.className='k';
    const cls=(pre.querySelector('code')||{}).className||'';
    const lang=(cls.match(/language-(\w+)/)||[])[1];
    k.textContent=out?'應該看到的畫面':(lang==='powershell'?'PowerShell':lang==='bash'?'bash':'指令');
    const b=document.createElement('button'); b.className='copy'; b.type='button'; b.textContent='複製';
    b.addEventListener('click',()=>copy(pre,b));
    bar.append(k,b); pre.replaceWith(box); box.append(bar,pre);
  });
  function copy(pre,b){
    const text=pre.innerText.replace(/\n$/,'');
    const ok=()=>{b.textContent='已複製';b.classList.add('ok');setTimeout(()=>{b.textContent='複製';b.classList.remove('ok')},1400)};
    const fallback=()=>{const r=document.createRange();r.selectNodeContents(pre);const s=getSelection();s.removeAllRanges();s.addRange(r);b.textContent='已選取，請按 Ctrl+C'};
    try{navigator.clipboard.writeText(text).then(ok,fallback)}catch(e){fallback()}
  }
  // 表格外包一層，窄螢幕可左右捲動
  document.querySelectorAll('main table').forEach(t=>{const d=document.createElement('div');d.className='tbl';t.replaceWith(d);d.append(t)});

  // Ansible 資料夾替換
  const codes=[...document.querySelectorAll('main code')].filter(c=>c.textContent.includes(DEF));
  codes.forEach(c=>c.dataset.o=c.textContent);
  const dir=document.getElementById('dir');
  function applyDir(v){v=(v||'').trim()||DEF;codes.forEach(c=>c.textContent=c.dataset.o.split(DEF).join(v))}
  dir.value=load(DIRKEY,DEF); applyDir(dir.value);
  dir.addEventListener('input',()=>{applyDir(dir.value);save(DIRKEY,dir.value.trim()||DEF)});

  // 完成勾選與進度
  function refresh(){
    let n=0;
    cards.forEach(c=>{const on=done.has(c.id);c.classList.toggle('is-done',on);c.querySelector('.done input').checked=on;if(on)n++});
    document.querySelector('.bar i').style.width=(n/total*100)+'%';
    document.getElementById('pc').textContent=n+' / '+total;
    document.querySelectorAll('.step').forEach(s=>{
      const cs=[...s.querySelectorAll('.card')], d=cs.filter(c=>done.has(c.id)).length;
      const t=d+'/'+cs.length;
      s.querySelector('.sc').textContent='完成 '+t;
      const a=document.querySelector('nav.side a[href="#'+s.id+'"]');
      if(a){a.querySelector('.cnt').textContent=t;a.classList.toggle('all',d===cs.length)}
    });
  }
  cards.forEach((c,i)=>{
    c.querySelector('.done input').addEventListener('change',e=>{e.target.checked?done.add(c.id):done.delete(c.id);save(KEY,[...done]);refresh()});
    const nx=c.querySelector('.next');
    if(nx){nx.addEventListener('click',()=>{done.add(c.id);save(KEY,[...done]);refresh();const t=cards[i+1];if(t){t.scrollIntoView({block:'start'});history.replaceState(null,'','#'+t.id)}})}
  });
  document.getElementById('reset').addEventListener('click',e=>{
    const b=e.currentTarget;
    if(b.dataset.arm){done=new Set();save(KEY,[]);refresh();b.textContent='清除進度';delete b.dataset.arm}
    else{b.dataset.arm='1';b.textContent='再按一次確認清除';setTimeout(()=>{b.textContent='清除進度';delete b.dataset.arm},3000)}
  });
  refresh();

  // 搜尋
  const q=document.getElementById('q'), empty=document.getElementById('empty');
  q.addEventListener('input',()=>{
    const v=q.value.trim().toLowerCase(); let any=false;
    document.querySelectorAll('.step').forEach(s=>{
      let show=false;
      s.querySelectorAll('.card').forEach(c=>{const m=!v||c.textContent.toLowerCase().includes(v);c.classList.toggle('hide',!m);if(m)show=true});
      s.classList.toggle('hide',!show); if(show)any=true;
    });
    document.querySelectorAll('.intro,.app').forEach(x=>x.classList.toggle('hide',!!v));
    empty.classList.toggle('hide',any);
  });

  // 目前所在步驟
  const links=[...document.querySelectorAll('nav.side a')], steps=[...document.querySelectorAll('.step')];
  const jump=document.getElementById('jump');
  jump.addEventListener('change',()=>{const t=document.getElementById(jump.value);if(t)t.scrollIntoView({block:'start'})});
  function onScroll(){
    let cur=steps[0]; steps.forEach(s=>{if(s.getBoundingClientRect().top<180)cur=s});
    links.forEach(a=>a.classList.toggle('cur',a.getAttribute('href')==='#'+cur.id));
    if(jump.value!==cur.id)jump.value=cur.id;
  }
  addEventListener('scroll',onScroll,{passive:true}); onScroll();
  if(location.hash){const t=document.getElementById(location.hash.slice(1));if(t)t.scrollIntoView({block:'start'})}
})();
"""


def build(fragment=False):
    title, intro, prelude, steps, appendix = parse()
    total = sum(len(s["subs"]) for s in steps)
    e = html.escape
    side = ['<nav class="side" aria-label="步驟">']
    jump = ['<select class="jump" id="jump" aria-label="跳到步驟">']
    for s in steps:
        side.append(f'<a href="#{s["id"]}"><span class="n">{s["n"]:02d}</span><span>{e(s["title"])}</span><span class="cnt"></span></a>')
        jump.append(f'<option value="{s["id"]}">步驟 {s["n"]}：{e(s["title"])}</option>')
    side.append('<p class="sep">附錄</p>')
    for i, a in enumerate(appendix):
        side.append(f'<a href="#app{i}"><span class="n">{"ABC"[i] if i < 3 else i}</span><span>{e(a["title"].split("：", 1)[-1])}</span><span></span></a>')
    side.append("</nav>")
    jump.append("</select>")

    legend = "".join(f'<span class="tag t-{k}">{v}</span>' for k, v in PLACE_NAME.items())
    body = [f'''<header class="top"><div class="top-in">
<div class="brand"><b>{e(title.split("：")[0])}</b><span>{e(title.split("：", 1)[-1])}</span></div>
<div class="prog"><div class="bar" aria-hidden="true"><i></i></div><span id="pc">0 / {total}</span></div>
<div class="tools">
{"".join(jump)}
<input id="q" type="search" placeholder="搜尋指令或關鍵字，例如 haproxy、9093" aria-label="搜尋">
<label for="dir">Ansible 資料夾</label><input id="dir" type="text" spellcheck="false" aria-label="ctl 上的 Ansible 資料夾">
<button class="btn" id="reset" type="button">清除進度</button>
</div></div></header>
<div class="wrap">{"".join(side)}<main>
<section class="intro">{intro}
<p>位置標籤：</p><div class="legend">{legend}</div>
<p>每個小步驟做完勾選「完成」，或按「完成，下一步」。進度只存在這個瀏覽器。手冊預設 Ansible 資料夾是 <code>~/ha2-lab/ansible</code>，你的資料夾不同時改上方欄位，所有指令會跟著換。</p>''']
    for p in prelude:
        body.append(f'<details><summary>{e(p["title"])}</summary>{p["html"].replace("<h3>", "<h4>").replace("</h3>", "</h4>")}</details>')
    body.append("</section>")
    for s in steps:
        body.append(f'<section class="step" id="{s["id"]}"><div class="step-h"><span class="num">步驟 {s["n"]}</span><h2>{e(s["title"])}</h2><span class="sc"></span></div>{s["lead"] and "<div class=lead>" + s["lead"] + "</div>"}')
        for sub in s["subs"]:
            tags = "".join(f'<span class="tag t-{k}">{PLACE_NAME[k]}</span>' for k in sub["places"])
            where = f'<div class="where">{tags}<span class="w-text">{sub["where"]}</span></div>' if sub["where"] else ""
            body.append(f'''<article class="card" id="{sub["id"]}">
<div class="card-h"><span class="id">{sub["num"]}</span><h3>{e(sub["title"])}</h3><label class="done"><input type="checkbox" aria-label="{sub["num"]} 完成">完成</label></div>
{where}<div class="body">{sub["html"]}<button class="btn next" type="button">完成，下一步 ↓</button></div></article>''')
        body.append("</section>")
    for i, a in enumerate(appendix):
        body.append(f'<section class="app" id="app{i}"><h2>{e(a["title"])}</h2>{a["html"]}</section>')
    body.append('<p class="empty hide" id="empty">找不到符合的步驟，換個關鍵字試試。</p></main></div>')

    head = f'''<title>HA2 指令手冊</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Noto+Sans+TC:wght@400;700&display=swap">
<style>{CSS}</style>'''
    content = head + "\n" + "\n".join(body) + f"\n<script>{JS}</script>\n"
    if fragment:
        return content
    return ('<!doctype html>\n<html lang="zh-Hant"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            + content.replace("<style>", "<style>", 1).replace("</style>", "</style>\n</head><body>", 1)
            + "</body></html>\n")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--fragment":
        Path(sys.argv[2]).write_text(build(fragment=True), encoding="utf-8")
        print("寫入", sys.argv[2])
    else:
        OUT.write_text(build(), encoding="utf-8")
        print("寫入", OUT)
