// Load a .bbmodel in a locally built Blockbench web app (served on :8765) and
// capture front / 3-quarter renders with Blockbench's own Screencam.
//   git clone https://github.com/JannisX11/blockbench && cd blockbench
//   npm install --ignore-scripts && npm run build-web && npx http-server -p 8765 -s .
//   node tools/blockbench_render.mjs Output/grim_reaper_scythe.bbmodel <out_dir>
import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import fs from 'fs';
const model = fs.readFileSync(process.argv[2], 'utf8');
const outdir = process.argv[3];
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--use-gl=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 1800, height: 1500 } });
const errors = [];
page.on('pageerror', e => errors.push('pageerror: ' + e.message));
page.on('console', m => { if (m.type() === 'error' || m.type()==='warning') errors.push(m.type()+': ' + m.text()); });
await page.goto('http://127.0.0.1:8765/index.html');
await page.waitForFunction(() => window.Codecs && Codecs.project && window.Blockbench, null, { timeout: 60000 });
await page.waitForTimeout(2000);
const info = await page.evaluate((txt) => {
  const json = JSON.parse(txt);
  Codecs.project.load(json, { path: 'grim_reaper_scythe.bbmodel', name: 'grim_reaper_scythe.bbmodel', no_file: true });
  return { version: Blockbench.version, format: Format.id };
}, model);
await page.waitForTimeout(2500);
const state = await page.evaluate(() => {
  const groups = Group.all.map(g => g.name + ' <- ' + (g.parent && g.parent.name ? g.parent.name : 'root') + ' (' + g.children.length + ')');
  const tex = Texture.all.map(t => ({ name: t.name, error: t.error, w: t.width, h: t.height, loaded: t.loaded }));
  const meshes = Mesh.all.length;
  let faces = 0, noTex = 0;
  Mesh.all.forEach(m => { for (const k in m.faces) { faces++; if (!m.faces[k].getTexture()) noTex++; } });
  const box = new THREE.Box3();
  Mesh.all.forEach(m => box.expandByObject(m.mesh));
  return { groups, tex, meshes, faces, noTex, box: [box.min.toArray(), box.max.toArray()], elementsInOutliner: Outliner.elements.length, validator: (Validator.warnings||[]).length + '/' + (Validator.errors||[]).length };
});
console.log(JSON.stringify({ info, state }, null, 1));
// screenshots via Blockbench's own Screencam (gizmos/grid hidden, transparent bg)
async function shot(preset, file, zoom) {
  const url = await page.evaluate(([preset, zoom]) => new Promise(res => {
    const p = Preview.selected;
    p.loadAnglePreset(preset);
    if (zoom) { p.camOrtho.zoom = zoom; p.camOrtho.updateProjectionMatrix(); }
    setTimeout(() => Screencam.screenshotPreview(p, {}, url => res(url)), 600);
  }), [preset, zoom]);
  fs.writeFileSync(outdir + '/' + file, Buffer.from(url.split(',')[1], 'base64'));
}
await shot({ projection: 'orthographic', position: [0, 36, 512], target: [0, 36, 0], zoom: 0.5 }, 'raw_front.png', 0.3);
await shot({ projection: 'perspective', position: [118, 70, 72], target: [0, 35, 0], fov: 45 }, 'raw_3q.png');
await shot({ projection: 'orthographic', position: [-3, 60, 512], target: [-3, 60, 0], zoom: 0.5 }, 'raw_head.png', 1.1);
await page.evaluate(() => { Preview.selected.loadAnglePreset({ projection: 'perspective', position: [95, 70, 110], target: [0, 33, 0], fov: 45 }); Outliner.root[0].children.forEach(g=>g.isOpen=false); });
await page.waitForTimeout(800);
await page.screenshot({ path: outdir + '/bb_full.png' });
console.log(errors.slice(0, 30).join('\n'));
await browser.close();
