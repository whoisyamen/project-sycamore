/** HTTP smoke check for the running dev server; complements production-build tests. */
import assert from 'node:assert/strict';
import ts from 'typescript';
const base = new URL(process.argv[2] ?? 'http://127.0.0.1:4321');
const checked = new Set();
const required = new Set([
  '/@vite/client',
  '/src/data/generated-validator.js',
  '/src/client/globe.ts',
]);

async function read(url) {
  const response = await fetch(url, { signal: AbortSignal.timeout(15000) });
  assert.equal(response.status, 200, `${url}: HTTP ${response.status}`);
  return { body: await response.text(), type: response.headers.get('content-type') ?? '' };
}

async function checkModule(url) {
  if (checked.has(url.href)) return;
  checked.add(url.href);
  const { body, type } = await read(url);
  assert.match(type, /(?:text|application)\/javascript/, `${url}: invalid module MIME ${type}`);
  assert.doesNotMatch(
    body,
    /__SERVER_FORWARD_CONSOLE__|__HMR_PROTOCOL__|__WS_TOKEN__/,
    `${url}: untransformed Vite client`,
  );
  // Parse actual imports: Cesium JSDoc includes import() examples that are not
  // browser requests and must not be mistaken for missing runtime modules.
  const imports = [];
  const source = ts.createSourceFile(
    url.pathname,
    body,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.JS,
  );
  function visit(node) {
    const specifier =
      ts.isImportDeclaration(node) || ts.isExportDeclaration(node)
        ? node.moduleSpecifier
        : ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword
          ? node.arguments[0]
          : undefined;
    if (specifier && ts.isStringLiteral(specifier)) imports.push(specifier.text);
    ts.forEachChild(node, visit);
  }
  visit(source);
  for (const specifier of imports) {
    if (!specifier.startsWith('/') && !specifier.startsWith('.')) continue;
    const child = new URL(specifier, url);
    if (child.origin === base.origin) await checkModule(child);
  }
}

for (const route of ['/', '/boards']) {
  const { body, type } = await read(new URL(route, base));
  assert.match(type, /text\/html/);
  const scripts = [...body.matchAll(/<script\b[^>]*\bsrc=["']([^"']+)["'][^>]*>/g)];
  assert.ok(scripts.length, `${route}: no client scripts`);
  for (const [, src] of scripts) await checkModule(new URL(src.replaceAll('&amp;', '&'), base));
}
for (const path of required) await checkModule(new URL(path, base));
const snapshot = JSON.parse((await read(new URL('/data/snapshot.json', base))).body);
assert.ok(Array.isArray(snapshot.events));
console.log(
  `Dev HTTP check passed: ${checked.size} JavaScript modules, map and Boards, ${snapshot.events.length} events at ${base.origin}.`,
);
