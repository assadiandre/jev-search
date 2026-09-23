const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { packager } = require('@electron/packager');
const root = path.resolve(__dirname, '..');
process.chdir(root);

async function build() {
  const python = path.join(root, '.venv/bin/python');
  const result = spawnSync(python, ['-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--name', 'jev-core', '--exclude-module', 'PIL', '--exclude-module', 'pytest', '--exclude-module', 'pygments', '--distpath', 'dist/python', '--workpath', 'build/pyinstaller', '--specpath', 'build', '--paths', root, 'backend/server.py'], { stdio: 'inherit' });
  if (result.status !== 0) throw new Error('Python packaging failed.');
  const stage = path.join(root, 'build/electron');
  fs.mkdirSync(stage, { recursive: true });
  for (const item of ['electron', 'ui']) fs.cpSync(path.join(root, item), path.join(stage, item), { recursive: true });
  const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json')));
  delete pkg.devDependencies; delete pkg.scripts;
  fs.writeFileSync(path.join(stage, 'package.json'), JSON.stringify(pkg, null, 2));
  const icon = path.join(root, 'assets/icon.icns');
  const output = await packager({
    dir: stage, out: path.join(root, 'dist/mac'), name: 'JEV SEARCH', executableName: 'JEV SEARCH',
    platform: 'darwin', arch: process.arch, overwrite: true, prune: false,
    appBundleId: 'local.jev.search', appCategoryType: 'public.app-category.productivity',
    icon: fs.existsSync(icon) ? icon : undefined,
    extendInfo: { LSUIElement: true, NSDesktopFolderUsageDescription: 'JEV SEARCH reads your Desktop only when you run a live search.', NSDocumentsFolderUsageDescription: 'JEV SEARCH reads the folder you choose when you run a live search.', NSDownloadsFolderUsageDescription: 'JEV SEARCH reads the folder you choose when you run a live search.' },
  });
  const source = path.join(output[0], 'JEV SEARCH.app');
  // Preserve relative dylib symlinks. Node's default cp rewrites them to source paths.
  const runtimeCopy = spawnSync('/usr/bin/ditto', [path.join(root, 'dist/python'), path.join(source, 'Contents/Resources/python')], { stdio: 'inherit' });
  if (runtimeCopy.status !== 0) throw new Error('Bundling Python failed.');
  const destination = path.join(root, 'JEV SEARCH.app');
  fs.rmSync(destination, { recursive: true, force: true });
  const copy = spawnSync('/usr/bin/ditto', [source, destination], { stdio: 'inherit' });
  if (copy.status !== 0) throw new Error('Copying the app bundle failed.');
  const sign = spawnSync('/usr/bin/codesign', ['--force', '--deep', '--sign', '-', destination], { stdio: 'inherit' });
  if (sign.status !== 0) throw new Error('Local app signing failed.');
  const verify = spawnSync('/usr/bin/codesign', ['--verify', '--deep', '--strict', destination], { stdio: 'inherit' });
  if (verify.status !== 0) throw new Error('App signature verification failed.');
  console.log(`Built ${destination}`);
}
build().catch(error => { console.error(error.message); process.exit(1); });
