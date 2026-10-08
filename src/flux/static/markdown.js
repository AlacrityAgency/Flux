/* Small, safe Markdown renderer for model replies (built with DOM nodes only). RTL-first; paths, code and numbers stay LTR. */
(()=>{
'use strict';
const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!=null)n.textContent=text;return n};
const PATHLIKE=/^(?:\/?[A-Za-z]:[\\/]|file:|\.{0,2}[\\/]|\/)/;
const baseName=p=>{const parts=p.replace(/[?#].*$/,'').split(/[\\/]/).filter(Boolean);return parts.length?parts[parts.length-1]:p};
const decode=u=>{try{return decodeURIComponent(u)}catch(_){return u}};

function chip(label,target){
  const full=decode(target).replace(/^file:\/*/,'').replace(/^\/([A-Za-z]:)/,'$1').replace(/\//g,'\\');
  const m=/^(.*?)(?::(\d+))?(?::\d+)?$/.exec(label.trim());
  let text=label.trim();
  // `[file.py:12](/abs/path/file.py:12)`: keep the short label; if the label is itself a long path, show only the file name
  if(PATHLIKE.test(text)||text.includes('\\')||text.split('/').length>2)text=baseName(m?m[1]:text)+(m&&m[2]?':'+m[2]:'');
  const b=el('button','md-path',text);b.type='button';b.dir='ltr';b.title=full+' — برای کپی کلیک کن';
  b.addEventListener('click',()=>{try{navigator.clipboard.writeText(full.replace(/:\d+(?::\d+)?$/,'')).then(()=>window.fluxShell&&window.fluxShell.toast('مسیر کپی شد'))}catch(_){}});
  return b;
}

const INLINE=/(`[^`\n]+`)|(\[([^\]\n]+)\]\(([^)\s]+)\))|(\*\*([^*\n]+?)\*\*|__([^_\n]+?)__)|(?<![\w*])\*([^*\n]+?)\*(?![\w*])|(https?:\/\/[^\s<>()]+[^\s<>().,;:!؟،؛])/g;
function inline(text,parent){
  let last=0,m;const re=new RegExp(INLINE.source,'g');
  while((m=re.exec(text))){
    if(m.index>last)parent.appendChild(document.createTextNode(text.slice(last,m.index)));
    if(m[1]){const c=el('code','md-code',m[1].slice(1,-1));c.dir='ltr';parent.appendChild(c)}
    else if(m[2]){
      const label=m[3],url=m[4];
      if(/^https?:\/\//i.test(url)){const a=el('a','md-link');a.href=url;a.target='_blank';a.rel='noopener noreferrer';inline(label,a);parent.appendChild(a)}
      else if(PATHLIKE.test(decode(url))||/\.[A-Za-z0-9]{1,6}(:\d+)?$/.test(url))parent.appendChild(chip(label,url));
      else parent.appendChild(document.createTextNode(label));
    }
    else if(m[5]){const s=el('strong');inline(m[6]||m[7],s);parent.appendChild(s)}
    else if(m[8]){const s=el('em');inline(m[8],s);parent.appendChild(s)}
    else if(m[9]){const a=el('a','md-link',m[9]);a.href=m[9];a.target='_blank';a.rel='noopener noreferrer';a.dir='ltr';parent.appendChild(a)}
    last=re.lastIndex;
  }
  if(last<text.length)parent.appendChild(document.createTextNode(text.slice(last)));
}

const isTableSep=l=>/^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$/.test(l);
const cells=l=>l.trim().replace(/^\|/,'').replace(/\|$/,'').split(/(?<!\\)\|/).map(c=>c.trim().replace(/\\\|/g,'|'));
const LIST=/^(\s*)([-*•]|\d+[.)])\s+(.*)$/;

function render(source){
  const root=document.createDocumentFragment();
  const lines=String(source||'').replace(/\r\n?/g,'\n').split('\n');
  let i=0;
  while(i<lines.length){
    const line=lines[i];
    if(!line.trim()){i++;continue}
    const fence=/^\s*(```+|~~~+)\s*([\w+-]*)/.exec(line);
    if(fence){
      const body=[];i++;
      while(i<lines.length&&!lines[i].trim().startsWith(fence[1].slice(0,3))){body.push(lines[i]);i++}
      i++;
      const box=el('div','md-pre'),pre=el('pre'),code=el('code',null,body.join('\n'));pre.dir='ltr';pre.appendChild(code);
      if(fence[2])box.appendChild(el('span','md-lang',fence[2]));
      box.appendChild(pre);root.appendChild(box);continue;
    }
    const h=/^(#{1,6})\s+(.*?)\s*#*\s*$/.exec(line);
    if(h){const n=el('h'+Math.min(6,h[1].length+1),'md-h');inline(h[2],n);root.appendChild(n);i++;continue}
    if(/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)){root.appendChild(el('hr','md-hr'));i++;continue}
    if(line.includes('|')&&i+1<lines.length&&isTableSep(lines[i+1])){
      const head=cells(line);i+=2;const rows=[];
      while(i<lines.length&&lines[i].includes('|')&&lines[i].trim()){rows.push(cells(lines[i]));i++}
      const wrap=el('div','md-table'),t=el('table'),thead=el('thead'),tr=el('tr');
      for(const c of head){const th=el('th');inline(c,th);tr.appendChild(th)}
      thead.appendChild(tr);t.appendChild(thead);const tb=el('tbody');
      for(const r of rows){const row=el('tr');for(let k=0;k<head.length;k++){const td=el('td');inline(r[k]||'',td);if((r[k]||'').length<=14&&!/[\u0600-\u06FF]/.test(r[k]||''))td.className='nw';row.appendChild(td)}tb.appendChild(row)}
      t.appendChild(tb);wrap.appendChild(t);root.appendChild(wrap);continue;
    }
    if(/^\s*>/.test(line)){
      const q=[];while(i<lines.length&&/^\s*>/.test(lines[i])){q.push(lines[i].replace(/^\s*>\s?/,''));i++}
      const bq=el('blockquote','md-quote');bq.appendChild(render(q.join('\n')));root.appendChild(bq);continue;
    }
    if(LIST.test(line)){
      const items=[];
      while(i<lines.length){
        const m=LIST.exec(lines[i]);
        if(m){items.push({indent:m[1].replace(/\t/g,'    ').length,ordered:/\d/.test(m[2]),text:m[3],extra:[]});i++}
        else if(lines[i].trim()&&/^\s{2,}\S/.test(lines[i])&&items.length){items[items.length-1].extra.push(lines[i].trim());i++}
        else break;
      }
      const stack=[];let top=null;
      const open=(it,parent)=>{const l=el(it.ordered?'ol':'ul','md-list');parent.appendChild(l);stack.push({indent:it.indent,list:l});return l};
      let lastLi=null;
      for(const it of items){
        while(stack.length&&it.indent<stack[stack.length-1].indent)stack.pop();
        if(!stack.length)top=open(it,root);
        else if(it.indent>stack[stack.length-1].indent&&lastLi)open(it,lastLi);
        const li=el('li');inline(it.text,li);
        for(const x of it.extra){li.appendChild(el('br'));inline(x,li)}
        stack[stack.length-1].list.appendChild(li);lastLi=li;
      }
      continue;
    }
    // paragraph: consecutive plain lines
    const para=[];
    while(i<lines.length&&lines[i].trim()&&!/^\s*(```|~~~|#{1,6}\s|>)/.test(lines[i])&&!LIST.test(lines[i])&&!(lines[i].includes('|')&&i+1<lines.length&&isTableSep(lines[i+1]))){para.push(lines[i]);i++}
    const p=el('p','md-p');
    para.forEach((l,k)=>{if(k)p.appendChild(el('br'));inline(l.trim(),p)});
    root.appendChild(p);
  }
  return root;
}
window.fluxMarkdown={render};
})();
