// Usage: node scripts/render.mjs stills 38,100,165   |   node scripts/render.mjs video
import { bundle } from '@remotion/bundler';
import { selectComposition, renderStill, renderMedia } from '@remotion/renderer';
import path from 'node:path';
import fs from 'node:fs';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const work = path.resolve(root, '..', 'work');
fs.mkdirSync(path.join(work, 'stills'), { recursive: true });
const browserExecutable = process.env.CHROME || '/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell';
const chromiumOptions = { gl: process.env.GL || 'angle' };
const serveUrl = await bundle({ entryPoint: path.join(root, 'src/index.ts'), publicDir: path.join(root, 'public') });
const composition = await selectComposition({ serveUrl, id: process.env.COMP || 'AthloReel', browserExecutable, chromiumOptions });
const mode = process.argv[2];
if (mode === 'stills') {
  for (const fr of process.argv[3].split(',').map(Number)) {
    const t0 = Date.now();
    const output = path.join(work, 'stills', `f${String(fr).padStart(3, '0')}.png`);
    await renderStill({ serveUrl, composition, frame: fr, output, browserExecutable, chromiumOptions, timeoutInMilliseconds: 240000, onBrowserLog: (l) => { if (!/memory/i.test(l.text)) console.log('[browser]', l.type, l.text.slice(0, 300)); } });
    console.log('still', fr, ((Date.now() - t0) / 1000).toFixed(1) + 's');
  }
} else if (mode === 'chunks') {
  // Render in short chunks, each in a fresh browser, so a long software-GL run can't lose its context.
  const size = Number(process.env.CHUNK || 75);
  const dir = path.join(work, 'chunks');
  fs.mkdirSync(dir, { recursive: true });
  const list = [];
  for (let a = 0; a < composition.durationInFrames; a += size) {
    const b = Math.min(composition.durationInFrames - 1, a + size - 1);
    const out = path.join(dir, `c_${String(a).padStart(3, '0')}.mkv`);
    list.push(out);
    if (fs.existsSync(out)) continue;
    for (let attempt = 1; ; attempt++) {
      try {
        const tmp = out.replace('.mkv', '.tmp.mkv');
        await renderMedia({
          serveUrl, composition, codec: 'h264-mkv', crf: 12, muted: true, browserExecutable, chromiumOptions,
          concurrency: Number(process.env.CONC || 3), timeoutInMilliseconds: 240000, frameRange: [a, b], outputLocation: tmp,
        });
        fs.renameSync(tmp, out);
        console.log(`chunk ${a}-${b} done`);
        break;
      } catch (e) {
        console.log(`chunk ${a}-${b} attempt ${attempt} failed: ${String(e.message).slice(0, 160)}`);
        if (attempt >= 4) throw e;
      }
    }
  }
  fs.writeFileSync(path.join(dir, 'list.txt'), list.map((f) => `file '${f}'`).join('\n'));
  console.log('all chunks rendered');
} else {
  await renderMedia({
    serveUrl, composition, codec: 'h264', crf: 12, muted: true, browserExecutable, chromiumOptions,
    concurrency: Number(process.env.CONC || 2), timeoutInMilliseconds: 240000,
    outputLocation: path.join(work, 'reel_picture.mp4'),
    onProgress: ({ progress }) => process.stdout.write(`\r${(progress * 100).toFixed(1)}%`),
  });
  console.log('\nwrote work/reel_picture.mp4');
}
