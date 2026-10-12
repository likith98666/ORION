#!/usr/bin/env node
/**
 * ORION Frontend Production Build Script
 * Packages static Mission Command Center assets into dist/ for Vercel deployment.
 * Zero external npm dependencies required (uses Node.js standard library: fs, path, crypto).
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const ROOT_DIR = path.resolve(__dirname, '..');
const STATIC_DIR = path.join(ROOT_DIR, 'src', 'orion', 'ui', 'static');
const DIST_DIR = path.join(ROOT_DIR, 'dist');

console.log('======================================================================');
console.log('  ORION // Frontend Production Build Pipeline');
console.log('======================================================================');

// Ensure source static directory exists
if (!fs.existsSync(STATIC_DIR)) {
  console.error(`[ERROR] Static assets directory not found: ${STATIC_DIR}`);
  process.exit(1);
}

// Clean and recreate dist directory
if (fs.existsSync(DIST_DIR)) {
  fs.rmSync(DIST_DIR, { recursive: true, force: true });
}
fs.mkdirSync(DIST_DIR, { recursive: true });

// Helper to copy directory recursively
function copyDir(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  const entries = fs.readdirSync(src, { withFileTypes: true });

  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);

    if (entry.isDirectory()) {
      copyDir(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

// 1. Copy all static files to dist/
console.log(`[1/4] Copying static assets from ${path.relative(ROOT_DIR, STATIC_DIR)} to dist/...`);
copyDir(STATIC_DIR, DIST_DIR);

// 2. Also mirror into dist/static/ so both root and /static/ paths resolve with zero 404s
console.log('[2/4] Mirroring assets to dist/static/ for legacy and same-origin path compatibility...');
const distStatic = path.join(DIST_DIR, 'static');
copyDir(STATIC_DIR, distStatic);

// 3. Process index.html: inject production environment variables if defined
console.log('[3/4] Processing production metadata and environment variables...');
const indexHtmlPath = path.join(DIST_DIR, 'index.html');
let indexHtml = fs.readFileSync(indexHtmlPath, 'utf8');

// Determine API URL from environment variables
const targetApiUrl = (
  process.env.ORION_API_URL ||
  process.env.NEXT_PUBLIC_ORION_API_URL ||
  process.env.VERCEL_BACKEND_URL ||
  ''
).trim().replace(/\/+$/, '');

if (targetApiUrl) {
  console.log(`      Configuring target ORION backend: ${targetApiUrl}`);
  indexHtml = indexHtml.replace(
    /<meta name="orion-api-url" content="[^"]*">/,
    `<meta name="orion-api-url" content="${targetApiUrl}">`
  );
} else {
  console.log('      Target backend: Relative / Same-Origin (configured via proxy or UI settings)');
}

// Inject build timestamp & commit if available
const buildTimestamp = new Date().toISOString();
indexHtml = indexHtml.replace('</head>', `  <meta name="build-timestamp" content="${buildTimestamp}">\n</head>`);

fs.writeFileSync(indexHtmlPath, indexHtml, 'utf8');
// Also write to mirrored dist/static/index.html
fs.writeFileSync(path.join(distStatic, 'index.html'), indexHtml, 'utf8');

// 4. Generate build manifest
console.log('[4/4] Generating build manifest...');
const manifest = {
  name: 'orion-frontend',
  version: '1.0.0',
  build_timestamp: buildTimestamp,
  target_api_url: targetApiUrl || null,
  assets: {}
};

function collectHashes(dir, baseDir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    const relPath = path.relative(baseDir, fullPath).replace(/\\/g, '/');
    if (entry.isDirectory()) {
      if (entry.name !== 'static') { // avoid duplicate manifest entries for mirror
        collectHashes(fullPath, baseDir);
      }
    } else {
      const buf = fs.readFileSync(fullPath);
      const hash = crypto.createHash('sha256').update(buf).digest('hex');
      manifest.assets[relPath] = {
        size_bytes: buf.length,
        sha256: hash
      };
    }
  }
}

collectHashes(DIST_DIR, DIST_DIR);
fs.writeFileSync(path.join(DIST_DIR, 'manifest.json'), JSON.stringify(manifest, null, 2), 'utf8');

console.log('======================================================================');
console.log(`[SUCCESS] Production build complete. ${Object.keys(manifest.assets).length} files ready in dist/`);
console.log('======================================================================');
