(function(){
var f=document.getElementById('sf'),q=document.getElementById('q'),box=document.getElementById('sres'),D=null,P=null;
function norm(s){return String(s||'').toLowerCase().replace(/\s+/g,'')}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function load(){if(!P)P=fetch('/search.json').then(function(r){return r.json()}).then(function(d){D=d.map(function(x){x.h=norm([x.n,x.a,x.r,x.b,x.k].join(' '));return x});return D});return P}
function find(v){var t=String(v||'').trim().toLowerCase().split(/\s+/).filter(Boolean).map(norm);if(!t.length)return[];
var o=D.filter(function(x){return t.every(function(w){return x.h.indexOf(w)>=0})});
o.sort(function(a,b){var an=norm(a.n).indexOf(t[0])>=0?0:1,bn=norm(b.n).indexOf(t[0])>=0?0:1;return an-bn||a.o-b.o});return o}
function row(x){return '<a href="/apt/'+x.u+'.html"><span class="b b-'+x.c+'">'+esc(x.s)+'</span> <b>'+esc(x.n)+'</b><span class="small muted"> '+esc(x.k)+(x.d?' · '+esc(x.d):'')+'</span></a>'}
window.cySearch={load:load,find:find,row:row,esc:esc};
if(!q)return;
q.addEventListener('focus',load);
q.addEventListener('input',function(){var v=q.value;if(!v.trim()){box.hidden=true;return}
load().then(function(){var o=find(v);box.innerHTML=o.length?o.slice(0,8).map(row).join('')+(o.length>8?'<a class="all" href="/search.html?q='+encodeURIComponent(v)+'">검색 결과 '+o.length+'건 모두 보기</a>':''):'<div class="none">"'+esc(v)+'"에 맞는 단지가 없습니다</div>';box.hidden=false})});
document.addEventListener('click',function(e){if(!f.contains(e.target))box.hidden=true});
q.addEventListener('keydown',function(e){if(e.key==='Escape')box.hidden=true});
})();