import { cpSync, mkdirSync } from 'node:fs';
const source = new URL('../node_modules/cesium/Build/Cesium/', import.meta.url);
const destination = new URL('../public/cesium/', import.meta.url);
mkdirSync(destination, { recursive: true });
for (const directory of ['Assets', 'Workers', 'ThirdParty']) {
  cpSync(new URL(directory, source), new URL(directory, destination), { recursive: true });
}
