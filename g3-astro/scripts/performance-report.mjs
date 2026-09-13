import { readdir, readFile, stat } from 'node:fs/promises';
import { gzipSync } from 'node:zlib';

// Run after a production build. Gzip values estimate transfer; they are not FPS.
const root = new URL('../dist/', import.meta.url);
async function walk(directory, prefix = '') {
  const files = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const url = new URL(entry.name + (entry.isDirectory() ? '/' : ''), directory);
    if (entry.isDirectory()) files.push(...(await walk(url, `${prefix}${entry.name}/`)));
    else files.push({ file: `${prefix}${entry.name}`, url, bytes: (await stat(url)).size });
  }
  return files;
}
const files = await walk(root);
const assets = [];
for (const file of files.filter(
  (f) => f.file.startsWith('_astro/') && /\.(js|css)$/.test(f.file),
)) {
  assets.push({
    file: file.file,
    bytes: file.bytes,
    gzip: gzipSync(await readFile(file.url)).length,
  });
}
assets.sort((a, b) => b.bytes - a.bytes);
console.log(
  JSON.stringify(
    {
      generatedAt: new Date().toISOString(),
      totalFiles: files.length,
      totalBytes: files.reduce((sum, f) => sum + f.bytes, 0),
      bundledBytes: assets.reduce((sum, f) => sum + f.bytes, 0),
      bundledGzipBytes: assets.reduce((sum, f) => sum + f.gzip, 0),
      assets,
    },
    null,
    2,
  ),
);
