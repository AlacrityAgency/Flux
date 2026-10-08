"""Apply provider choices and local-key controls to the existing native workspace."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'src/flux/static'
html=root/'local.html';text=html.read_text(encoding='utf-8')
text=text.replace('<option value="antigravity">Antigravity</option>','<option value="gemini-api">Gemini API</option><option value="gemini">Gemini CLI</option><option value="gapcode">GapCode</option><option value="antigravity">Antigravity</option>')
marker='<button type="button" role="option" data-provider="antigravity"'
if 'data-provider="gapcode"' not in text:
    buttons=''.join('<button type="button" role="option" data-provider="'+id+'" aria-selected="false"><span><strong>'+label+'</strong><small>'+detail+'</small></span></button>' for id,label,detail in [('gemini-api','Gemini API','کلید API خودتان'),('gemini','Gemini CLI','حساب Google'),('gapcode','GapCode','کیف پول GapCode')])
    text=text.replace(marker,buttons+marker)
text=text.replace('مصرف از سهمیهٔ حساب شماست.','مصرف مطابق سرویس انتخاب‌شده است: سهمیهٔ حساب، کیف پول GapCode یا Gemini API.')
html.write_text(text,encoding='utf-8')
js=root/'local.js';text=js.read_text(encoding='utf-8').replace("claude:'Claude Code',antigravity:","claude:'Claude Code','gemini-api':'Gemini API',gemini:'Gemini CLI',gapcode:'GapCode',antigravity:")
text=text.replace("else if(p.id==='notebooklm')command=", "else if(p.id==='gemini')command='python tools/connect_account_clis.py gemini';else if(p.id==='gapcode')command='gapcode login';else if(p.id==='gemini-api')command=null;else if(p.id==='notebooklm')command=")
text=text.replace("if(p.error_code!=='region_restricted')card.append", "if(command&&p.error_code!=='region_restricted')card.append")
marker="const quota=textNode('div','','quota-card');"
if "type='password'" not in text:
    text=text.replace(marker,"""if(p.id==='gemini-api'){const form=document.createElement('form');const input=document.createElement('input');input.type='password';input.autocomplete='off';input.placeholder='کلید Gemini API';input.setAttribute('aria-label','کلید Gemini API');input.maxLength=250;const save=textNode('button','ذخیرهٔ کلید');save.type='submit';form.append(input,save);form.onsubmit=async e=>{e.preventDefault();try{await api('/api/local/connections/gemini-api',{method:'PUT',body:JSON.stringify({api_key:input.value})});input.value='';await connections(true);}catch(err){input.value='';showError(err);}};card.append(form,textNode('small','کلید محلی رمز می‌شود. ذخیره، اعتبار یا هزینهٔ مدل را تأیید نمی‌کند.'));}const quota=textNode('div','','quota-card');""")
text=text.replace("||selected==='antigravity';", "||selected==='antigravity'||selected==='gemini-api';")
text=text.replace("notebook?'پرسش از منابع':", "notebook?'پرسش از منابع':")
text=text.replace("$('provider').value==='antigravity'?'مجوزهای Antigravity':", "$('provider').value==='gemini-api'?'تحلیل متن؛ بدون اجرای ابزار':$('provider').value==='antigravity'?'مجوزهای Antigravity':")
js.write_text(text,encoding='utf-8')
head=root/'head.html';text=head.read_text(encoding='utf-8').replace('<option value="claude">Claude</option>','<option value="claude">Claude</option><option value="gemini">Gemini CLI</option><option value="gapcode">GapCode</option>');head.write_text(text,encoding='utf-8')
print('Provider UI updated.')
