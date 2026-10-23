// Builds the deployable index.html + app.js from app.src.html (the file you edit).
// Usage: node build/build.cjs [outDir]   (default outDir = repo root; use "perf-test" to stage)
// Setup once: cd build && npm install
const fs = require('fs'), path = require('path'), crypto = require('crypto');
const babel = require('@babel/core'), esbuild = require('esbuild');
const repo = path.join(__dirname, '..');
const out = path.resolve(repo, process.argv[2] || '.');
const src = fs.readFileSync(path.join(repo, 'app.src.html'), 'utf8');
const m = src.match(/<script type="text\/babel">([\s\S]*?)<\/script>/);
if (!m) throw new Error('babel script block not found in app.src.html');
// Same transform Babel-standalone applies in the browser (react + env -> ES5), so let/const become
// var exactly as before. Native let/const would hit TDZ errors the old setup tolerated.
const b = babel.transformSync(m[1], {
  presets: [require.resolve('@babel/preset-react'), [require.resolve('@babel/preset-env'), { modules: false }]],
  sourceType: 'script', compact: false, comments: false, configFile: false, babelrc: false
});
const res = esbuild.transformSync(b.code, { loader: 'js', target: 'es2019', minifyWhitespace: true, legalComments: 'none' });
const hash = crypto.createHash('sha1').update(res.code).digest('hex').slice(0, 8);
let h = src.replace(m[0], () => '<script defer src="app.js?v=' + hash + '"></script>');
const swap = (a, c) => { if (!h.includes(a)) throw new Error('missing ' + a); h = h.replace(a, c); };
swap('<script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>',
     '<script defer src="https://cdnjs.cloudflare.com/ajax/libs/react/18.3.1/umd/react.production.min.js"></script>');
swap('<script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>',
     '<script defer src="https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.3.1/umd/react-dom.production.min.js"></script>');
h = h.replace(/\s*<script src="https:\/\/unpkg\.com\/@babel\/standalone@7\/babel\.min\.js"><\/script>/, '');
h = h.replace(/<script src=("https:[^"]+")><\/script>/g, '<script defer src=$1></script>');
// Show uncaught startup errors on screen instead of a silent blank page
const dbg = '<script>window.addEventListener("error",function(e){if(document.getElementById("root")&&document.getElementById("root").children.length)return;var d=document.createElement("pre");d.style.cssText="position:fixed;z-index:99999;left:0;right:0;bottom:0;max-height:50%;overflow:auto;margin:0;padding:8px;background:#400;color:#fff;font:11px monospace;white-space:pre-wrap";d.textContent="ERR: "+e.message+" @"+(e.filename||"").split("/").pop()+":"+e.lineno;document.body.appendChild(d)});</script>';
h = h.replace('<style>', () => dbg + '<style>');
fs.mkdirSync(out, { recursive: true });
fs.writeFileSync(path.join(out, 'app.js'), res.code);
fs.writeFileSync(path.join(out, 'index.html'), h);
console.log('built', out, 'app.js', res.code.length, 'index.html', h.length, 'v=' + hash);
