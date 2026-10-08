"""Small inline-SVG chart kit for the v6 article: thin marks, hairline grid, text in ink tokens,
legend for >= 2 series, value labels, per-mark tooltips (data-tip) and a table view beside each chart."""
from html import escape
import re

SERIES = {'normal': ('#2a78d6', '#3987e5'), 'v6': ('#eb6834', '#d95926'), 'sol': ('#1baf7a', '#199e70'),
          'aux': ('#a3a29a', '#6f6e66'), 'good': ('#0ca30c', '#0ca30c'), 'bad': ('#d03b3b', '#d03b3b')}
LABEL = {'normal': 'حالت عادی (Luna مستقیم)', 'v6': 'v6', 'sol': 'Sol مستقیم', 'aux': 'اجزای میانی v6'}
FONT = 'Vazir, Arial, sans-serif'
PERSIAN = re.compile(r'[؀-ۿ]')


def css():
    light = ''.join(f'--s-{k}:{v[0]};' for k, v in SERIES.items())
    dark = ''.join(f'--s-{k}:{v[1]};' for k, v in SERIES.items())
    return (f'.viz{{--surface:#fcfcfb;--ink:#202720;--ink-2:#52514e;--grid:#e4e6e0;{light}}}'
            f'@media (prefers-color-scheme:dark){{:root:where(:not([data-theme="light"])) .viz{{--surface:#1a1a19;--ink:#f3f3ef;--ink-2:#c3c2b7;--grid:#383835;{dark}}}}}'
            f':root[data-theme="dark"] .viz{{--surface:#1a1a19;--ink:#f3f3ef;--ink-2:#c3c2b7;--grid:#383835;{dark}}}'
            '.viz{background:var(--surface);border-radius:6px;padding:8px 6px}.viz svg text{fill:var(--ink);font-family:'+FONT+'}'
            '.viz svg .muted{fill:var(--ink-2)}.viz svg .grid{stroke:var(--grid);stroke-width:1}'
            '.viz [data-tip]{cursor:default;outline:none}.viz [data-tip]:hover .mark,.viz [data-tip]:focus .mark{opacity:.78}'
            '.legend{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:var(--ink-2);margin:2px 8px 6px}'
            '.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-left:6px;vertical-align:-1px}'
            '#tip{position:fixed;pointer-events:none;background:#17221b;color:#fff;padding:6px 10px;border-radius:6px;font-size:12px;'
            'line-height:1.7;display:none;z-index:9;max-width:280px;direction:rtl}#tip b{font-size:14px;display:block}'
            'details.table-view{font-size:12px;margin:6px 8px}details.table-view summary{cursor:pointer;color:var(--ink-2)}'
            '@media print{#tip,details.table-view{display:none}}')


TIP_JS = '''<div id="tip" role="status"></div><script>
(function(){const tip=document.getElementById('tip');
function show(el,x,y){const t=el.getAttribute('data-tip').split('|');tip.textContent='';
 const b=document.createElement('b');b.textContent=t[0];tip.appendChild(b);
 for(const line of t.slice(1)){const s=document.createElement('div');s.textContent=line;tip.appendChild(s);}
 tip.style.display='block';const w=tip.offsetWidth;tip.style.left=Math.max(8,Math.min(innerWidth-w-8,x-w/2))+'px';tip.style.top=(y-tip.offsetHeight-14)+'px';}
document.querySelectorAll('[data-tip]').forEach(el=>{
 el.addEventListener('pointermove',e=>show(el,e.clientX,e.clientY));
 el.addEventListener('pointerleave',()=>tip.style.display='none');
 el.addEventListener('focus',()=>{const r=el.getBoundingClientRect();show(el,r.left+r.width/2,r.top);});
 el.addEventListener('blur',()=>tip.style.display='none');});})();
</script>'''


def text(x, y, s, side, size=13, weight=None, cls=''):
    """side: which edge of the text sits at x ('right', 'left' or 'center'), independent of script direction."""
    rtl = bool(PERSIAN.search(s))
    anchor = {'right': 'start' if rtl else 'end', 'left': 'end' if rtl else 'start', 'center': 'middle'}[side]
    style = ' style="direction:rtl;unicode-bidi:embed"' if rtl else ''
    w = f' font-weight="{weight}"' if weight else ''
    c = f' class="{cls}"' if cls else ''
    return f'<text{c} x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}"{w}{style}>{escape(s)}</text>'


def legend(keys, labels=None):
    labels = labels or LABEL
    return '<div class="legend">'+''.join(f'<span><i style="background:var(--s-{k})"></i>{escape(labels[k])}</span>' for k in keys)+'</div>'


def table(headers, rows):
    head = ''.join(f'<th>{escape(h)}</th>' for h in headers)
    body = ''.join('<tr>'+''.join(f'<td>{escape(str(c))}</td>' for c in r)+'</tr>' for r in rows)
    return (f'<details class="table-view"><summary>نمایش جدول داده</summary><div class="table-wrap"><table><thead><tr>{head}</tr></thead>'
            f'<tbody>{body}</tbody></table></div></details>')


def rbar(x, y, w, h, color, r=4):
    """Bar from baseline x with a 4px rounded data-end on the right, square at the baseline."""
    w = max(w, 0.5)
    r = min(r, w, h/2)
    return (f'<path class="mark" fill="{color}" d="M{x:.1f},{y:.1f} H{x+w-r:.1f} Q{x+w:.1f},{y:.1f} {x+w:.1f},{y+r:.1f} '
            f'V{y+h-r:.1f} Q{x+w:.1f},{y+h:.1f} {x+w-r:.1f},{y+h:.1f} H{x:.1f} Z"/>')


def hbars(rows, vmax, fmt, width=760, label_w=210, bar_h=20, gap=14, ticks=(0, .25, .5, .75, 1), tick_fmt=None, title=''):
    """rows: (label, value, series_key, tip). One measure across categories."""
    plot_w = width-label_w-90
    h = 26+len(rows)*(bar_h+gap)
    out = [f'<svg viewBox="0 0 {width} {h}" role="img" aria-label="{escape(title)}">']
    for t in ticks:
        x = label_w+plot_w*t/vmax
        out.append(f'<line class="grid" x1="{x:.1f}" y1="6" x2="{x:.1f}" y2="{h-18}"/>')
        out.append(text(x, h-4, tick_fmt(t) if tick_fmt else fmt(t), 'center', 11, cls='muted'))
    for i, (label, value, key, tip) in enumerate(rows):
        y = 8+i*(bar_h+gap)
        w = plot_w*value/vmax
        out.append(text(label_w-10, y+bar_h/2+5, label, 'right'))
        out.append(f'<g tabindex="0" data-tip="{escape(tip)}"><rect x="{label_w}" y="{y-gap/2}" width="{plot_w+80}" height="{bar_h+gap}" fill="transparent"/>'
                   f'{rbar(label_w, y, w, bar_h, f"var(--s-{key})")}</g>')
        out.append(text(label_w+w+8, y+bar_h/2+5, fmt(value), 'left', 13, 650))
    out.append('</svg>')
    return '\n'.join(out)


def dotplot(rows, keys, width=760, label_w=200, row_h=34, title=''):
    """rows: (label, {key: value 0..1}, {key: tip}). Series sit on small vertical offsets so equal values stay visible."""
    plot_w = width-label_w-30
    h = 30+len(rows)*row_h
    offsets = {k: (i-(len(keys)-1)/2)*7 for i, k in enumerate(keys)}
    out = [f'<svg viewBox="0 0 {width} {h}" role="img" aria-label="{escape(title)}">']
    for t in (0, .25, .5, .75, 1):
        x = label_w+plot_w*t
        out.append(f'<line class="grid" x1="{x:.1f}" y1="4" x2="{x:.1f}" y2="{h-20}"/>')
        out.append(text(x, h-5, f'{int(t*100)}%'.translate(str.maketrans('0123456789%', '۰۱۲۳۴۵۶۷۸۹٪')), 'center', 11, cls='muted'))
    for i, (label, vals, tips) in enumerate(rows):
        y = 18+i*row_h
        out.append(text(label_w-10, y+5, label, 'right'))
        xs = [label_w+plot_w*vals[k] for k in keys]
        out.append(f'<line class="grid" x1="{min(xs):.1f}" y1="{y}" x2="{max(xs):.1f}" y2="{y}" style="stroke-width:2"/>')
        for k in keys:
            x, yy = label_w+plot_w*vals[k], y+offsets[k]
            out.append(f'<g tabindex="0" data-tip="{escape(tips[k])}"><circle cx="{x:.1f}" cy="{yy:.1f}" r="12" fill="transparent"/>'
                       f'<circle class="mark" cx="{x:.1f}" cy="{yy:.1f}" r="5" fill="var(--s-{k})" stroke="var(--surface)" stroke-width="2"/></g>')
    out.append('</svg>')
    return '\n'.join(out)


def ranges(rows, vmax, width=760, label_w=210, row_h=40, title='', unit='s', num=str):
    """rows: (label, p50, p95, key, tip): dot at median, thin line to p95."""
    plot_w = width-label_w-120
    h = 30+len(rows)*row_h
    out = [f'<svg viewBox="0 0 {width} {h}" role="img" aria-label="{escape(title)}">']
    t = 0
    while t <= vmax:
        x = label_w+plot_w*t/vmax
        out.append(f'<line class="grid" x1="{x:.1f}" y1="4" x2="{x:.1f}" y2="{h-20}"/>')
        out.append(text(x, h-5, num(t)+unit, 'center', 11, cls='muted'))
        t += 5
    for i, (label, p50, p95, key, tip) in enumerate(rows):
        y = 18+i*row_h
        x50, x95 = label_w+plot_w*p50/vmax, label_w+plot_w*p95/vmax
        out.append(text(label_w-10, y+5, label, 'right'))
        out.append(f'<g tabindex="0" data-tip="{escape(tip)}"><rect x="{label_w}" y="{y-14}" width="{plot_w+110}" height="28" fill="transparent"/>'
                   f'<line class="mark" x1="{x50:.1f}" y1="{y}" x2="{x95:.1f}" y2="{y}" stroke="var(--s-{key})" stroke-width="2" stroke-linecap="round"/>'
                   f'<circle class="mark" cx="{x50:.1f}" cy="{y}" r="6" fill="var(--s-{key})" stroke="var(--surface)" stroke-width="2"/>'
                   f'<line class="mark" x1="{x95:.1f}" y1="{y-6}" x2="{x95:.1f}" y2="{y+6}" stroke="var(--s-{key})" stroke-width="2"/></g>')
        out.append(text(x95+10, y+5, f'{num(round(p50, 1))}{unit} / {num(round(p95, 1))}{unit}', 'left', 12, 650))
    out.append('</svg>')
    return '\n'.join(out)


def stacked(parts, width=760, height=64, title='', num=str):
    """parts: (label, count, color_css, tip). One horizontal 100% bar with 2px surface gaps."""
    total = sum(p[1] for p in parts) or 1
    out = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">']
    x = 10
    usable = width-20-2*(len(parts)-1)
    for label, n, color, tip in parts:
        w = usable*n/total
        out.append(f'<g tabindex="0" data-tip="{escape(tip)}"><rect x="{x:.1f}" y="2" width="{max(w, .5):.1f}" height="36" fill="transparent"/>'
                   f'<rect class="mark" x="{x:.1f}" y="8" width="{max(w, .5):.1f}" height="24" rx="3" fill="{color}"/></g>')
        if w > 110:
            out.append(text(x+w/2, 54, f'{label}: {num(n)}', 'center', 12))
        x += w+2
    out.append('</svg>')
    return '\n'.join(out)
