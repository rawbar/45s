// Builds perf-test/ from index.html: precompiled JS, pinned CDN, deferred scripts.
const fs=require('fs'),path=require('path'),esbuild=require('esbuild');
const repo=process.argv[2], out=path.join(repo,'perf-test');
let html=fs.readFileSync(path.join(repo,'index.html'),'utf8');
const m=html.match(/<script type="text\/babel">([\s\S]*?)<\/script>/);
if(!m) throw new Error('babel script not found');
// Mirror Babel-standalone's default (react + env -> ES5) so let/const become var exactly as on prod
// (native TDZ would throw on any use-before-define that prod tolerates).
const babel=require('@babel/core');
const b=babel.transformSync(m[1],{presets:['@babel/preset-react',['@babel/preset-env',{modules:false}]],sourceType:'script',compact:false,comments:false,configFile:false,babelrc:false});
const res=esbuild.transformSync(b.code,{loader:'js',target:'es2019',minifyWhitespace:true,legalComments:'none'});
fs.mkdirSync(out,{recursive:true});
fs.writeFileSync(path.join(out,'app.js'),res.code);
let h=html.replace(m[0],'<script defer src="app.js?v='+Date.now().toString(36)+'"></script>');
const swap=(a,b)=>{ if(!h.includes(a)) throw new Error('missing '+a); h=h.replace(a,b); };
swap('<script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>','<script defer src="https://cdnjs.cloudflare.com/ajax/libs/react/18.3.1/umd/react.production.min.js"></script>');
swap('<script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>','<script defer src="https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.3.1/umd/react-dom.production.min.js"></script>');
h=h.replace(/\s*<script src="https:\/\/unpkg\.com\/@babel\/standalone@7\/babel\.min\.js"><\/script>/,'');
// defer every other external script so they stop blocking first paint (order preserved)
h=h.replace(/<script src=("https:[^"]+")><\/script>/g,'<script defer src=$1></script>');
// test-page only: show any uncaught error on screen so a blank page can be diagnosed on a phone
const dbg="<script>window.addEventListener(\"error\",function(e){var d=document.createElement(\"pre\");d.style.cssText=\"position:fixed;z-index:99999;left:0;right:0;bottom:0;max-height:50%;overflow:auto;margin:0;padding:8px;background:#400;color:#fff;font:11px monospace;white-space:pre-wrap\";d.textContent=\"ERR: \"+e.message+\" @\"+(e.filename||\"\").split(\"/\").pop()+\":\"+e.lineno+\":\"+e.colno+\" | \"+(e.error&&e.error.stack||\"\").slice(0,600);document.body.appendChild(d)});</script>";
h=h.replace('<style>',dbg+'<style>');
fs.writeFileSync(path.join(out,'index.html'),h);
console.log('app.js',res.code.length,'index.html',h.length);
