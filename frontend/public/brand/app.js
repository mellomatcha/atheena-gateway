const escapeShell = (value) => value.replaceAll("'", "'\\''");
let apiBase = `${location.origin}/v1`;
const model = 'deepseek-v4.1-flash';
const keyInput = document.querySelector('#integration-key');
const pastedKey = () => /^sk-ath-[A-Za-z0-9]{40}$/.test(keyInput.value.trim()) ? keyInput.value.trim() : 'sk-ath-ISI-KEY-ANDA';
const examples = () => ({
  opencode: {name:'opencode.json',help:'Simpan sebagai opencode.json di folder proyek, lalu jalankan opencode.',code:JSON.stringify({provider:{atheena:{npm:'@ai-sdk/openai-compatible',name:'ATHEENA',options:{baseURL:apiBase,apiKey:pastedKey()},models:{[model]:{name:'DeepSeek V4.1 Flash'}}}},model:`atheena/${model}`},null,2)},
  curl: {name:'terminal.sh',help:'Paste key di kolom di atas, lalu salin perintah ini.',code:`curl '${escapeShell(apiBase)}/chat/completions' \\\n  -H "Authorization: Bearer ${pastedKey()}" \\\n  -H 'Content-Type: application/json' \\\n  -d '{\n    "model": "${model}",\n    "messages": [{\n      "role": "user",\n      "content": "Halo, ATHEENA."\n    }]\n  }'`},
  python: {name:'hello.py',help:'Pasang paket openai, paste key di atas, lalu salin contoh ini.',code:`from openai import OpenAI\n\nclient = OpenAI(\n    base_url=${JSON.stringify(apiBase)},\n    api_key=${JSON.stringify(pastedKey())},\n)\n\nresponse = client.chat.completions.create(\n    model="${model}",\n    messages=[{\n        "role": "user",\n        "content": "Halo, ATHEENA.",\n    }],\n)\nprint(response.choices[0].message.content)`}
});
let selected = 'opencode';
const tabs = [...document.querySelectorAll('[data-client]')];
function selectTab(name,focus=false){selected=name;const example=examples()[name];document.querySelector('#code-content').textContent=example.code;document.querySelector('#code-filename').textContent=example.name;document.querySelector('#code-help').textContent=example.help;document.querySelector('#code-panel').setAttribute('aria-labelledby',`tab-${name}`);for(const tab of tabs){const active=tab.dataset.client===name;tab.setAttribute('aria-selected',String(active));tab.tabIndex=active?0:-1;if(active&&focus)tab.focus();}}
for(const [i,tab] of tabs.entries()){tab.addEventListener('click',()=>selectTab(tab.dataset.client));tab.addEventListener('keydown',(event)=>{let index;if(event.key==='ArrowRight')index=(i+1)%tabs.length;else if(event.key==='ArrowLeft')index=(i+tabs.length-1)%tabs.length;else if(event.key==='Home')index=0;else if(event.key==='End')index=tabs.length-1;else return;event.preventDefault();selectTab(tabs[index].dataset.client,true);});}
selectTab(selected);
document.querySelector('#copy-code').addEventListener('click',async()=>{const status=document.querySelector('#copy-status');const button=document.querySelector('#copy-code');const text=examples()[selected].code;let copied=false;try{await navigator.clipboard.writeText(text);copied=true;}catch{const area=document.createElement('textarea');area.value=text;area.style.cssText='position:fixed;left:-9999px';document.body.append(area);area.select();try{copied=document.execCommand('copy');}catch{}area.remove();button.focus();}status.textContent=copied?'Contoh berhasil disalin.':'Salin otomatis tidak tersedia. Pilih teks contoh dan salin secara manual.';button.textContent=copied?'Tersalin ✓':'Pilih & salin';setTimeout(()=>{button.textContent='Salin ⧉';},2500);});

keyInput.addEventListener('input', () => selectTab(selected));
