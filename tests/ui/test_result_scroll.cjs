const fs = require('node:fs');
const assert = require('node:assert/strict');
const css = fs.readFileSync('setlist/ui/studio.css', 'utf8');
const base = fs.readFileSync('setlist/ui/style.css', 'utf8');
const html = fs.readFileSync('setlist/ui/index.html', 'utf8');
const app = fs.readFileSync('setlist/ui/app.js', 'utf8');
assert.match(css, /#reviewView\s+\.songs\s*\{\s*overscroll-behavior:\s*auto\s*\}/);
assert.match(base, /\.songs\{[^}]*max-height:480px;overflow:auto/);
assert.match(base, /\.folder-list\{[^}]*overscroll-behavior:contain/);
assert(html.indexOf('style.css') < html.indexOf('studio.css'));
assert.match(app, /classList.toggle\('home-view',which==='create'\)/);
for (const file of fs.readdirSync('setlist/ui').filter(f => f.endsWith('.js'))) {
  const js = fs.readFileSync('setlist/ui/' + file, 'utf8');
  assert(!/addEventListener\(\s*['"](?:wheel|mousewheel|touchmove)['"]|onwheel\s*=|onmousewheel\s*=/.test(js), file + ': unexpected scroll interception');
}
console.log('Results scroll chaining CSS and handler regression checks passed. Physical input requires UI verification.');
