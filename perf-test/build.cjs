// Builds perf-test/ from index.html: precompiled JS, pinned CDN, deferred scripts.
const fs=require('fs'),path=require('path'),esbuild=require('esbuild');
const repo=process.argv[2], out=path.join(repo,'perf-test');
let html=fs.readFileSync(path.join(repo,'index.html'),'utf8');
const m=html.match(/<script type="text\/babel">([\s\S]*?)<\/script>/);
if(!m) throw new Error('babel script not found');
const res=esbuild.transformSync(m[1],{loader:'jsx',target:'es2019',minifyWhitespace:true,minifySyntax:true,legalComments:'none'});
fs.mkdirSync(out,{recursive:true});
fs.writeFileSync(path.join(out,'app.js'),res.code);
let h=html.replace(m[0],'<script defer src="app.js?v='+Date.now().toString(36)+'"></script>');
const swap=(a,b)=>{ if(!h.includes(a)) throw new Error('missing '+a); h=h.replace(a,b); };
swap('<script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>','<script defer src="https://cdnjs.cloudflare.com/ajax/libs/react/18.3.1/umd/react.production.min.js"></script>');
swap('<script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>','<script defer src="https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.3.1/umd/react-dom.production.min.js"></script>');
h=h.replace(/\s*<script src="https:\/\/unpkg\.com\/@babel\/standalone@7\/babel\.min\.js"><\/script>/,'');
// defer every other external script so they stop blocking first paint (order preserved)
h=h.replace(/<script src=("https:[^"]+")><\/script>/g,'<script defer src=$1></script>');
fs.writeFileSync(path.join(out,'index.html'),h);
console.log('app.js',res.code.length,'index.html',h.length);
