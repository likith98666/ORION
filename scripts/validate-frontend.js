#!/usr/bin/env node
/**
 * ORION Frontend Validation Script
 * Verifies production integrity of dist/ output for Vercel deployment.
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const ROOT_DIR = path.resolve(__dirname, '..');
const DIST_DIR = path.join(ROOT_DIR, 'dist');

console.log('======================================================================');
console.log('  ORION // Frontend Verification & Integrity Audit');
console.log('======================================================================');

let errors = 0;

function assert(condition, message) {
  if (!condition) {
    console.error(`  [FAIL] ${message}`);
    errors++;
  } else {
    console.log(`  [PASS] ${message}`);
  }
}

// 1. Verify build directory exists
assert(fs.existsSync(DIST_DIR), 'dist/ directory exists');

// 2. Critical files check
const criticalFiles = [
  'index.html',
  'app.css',
  'app.js',
  '404.html',
  'favicon.svg',
  'orion-preview.png',
  'manifest.json',
  'static/app.css',
  'static/app.js',
  'static/favicon.svg'
];

for (const file of criticalFiles) {
  const p = path.join(DIST_DIR, file);
  assert(fs.existsSync(p), `Critical asset exists: ${file} (${fs.existsSync(p) ? fs.statSync(p).size + ' bytes' : 'MISSING'})`);
}

// 3. Fonts validation
const fontDir = path.join(DIST_DIR, 'fonts');
assert(fs.existsSync(fontDir), 'dist/fonts/ directory exists');

const requiredFonts = [
  'orbitron-latin-400.woff2',
  'orbitron-latin-700.woff2',
  'jetbrains-mono-latin-400.woff2',
  'jetbrains-mono-latin-600.woff2',
  'space-grotesk-latin-400.woff2',
  'space-grotesk-latin-700.woff2'
];

for (const font of requiredFonts) {
  const p = path.join(fontDir, font);
  assert(fs.existsSync(p), `Typography asset exists: fonts/${font}`);
}

// 4. Validate JavaScript syntax
try {
  execSync(`node --check "${path.join(DIST_DIR, 'app.js')}"`, { stdio: 'pipe' });
  assert(true, 'app.js passed JavaScript syntax validation');
} catch (e) {
  assert(false, `app.js syntax error: ${e.message}`);
}

// 5. Check index.html markup requirements
const htmlContent = fs.readFileSync(path.join(DIST_DIR, 'index.html'), 'utf8');
assert(htmlContent.includes('<title>'), 'index.html contains <title>');
assert(htmlContent.includes('og:title'), 'index.html contains Open Graph metadata');
assert(htmlContent.includes('twitter:card'), 'index.html contains Twitter card metadata');
assert(htmlContent.includes('orion-api-url'), 'index.html contains orion-api-url meta tag');
assert(htmlContent.includes('btnTopbarBackendStatus'), 'index.html contains backend connection trigger');
assert(htmlContent.includes('cfgApiEndpointInput'), 'index.html contains interactive API configuration input');

// 6. Check 404 page
const notFoundContent = fs.readFileSync(path.join(DIST_DIR, '404.html'), 'utf8');
assert(notFoundContent.includes('Directive Not Found'), '404.html contains Directive Not Found');
assert(notFoundContent.includes('href="/"'), '404.html links back to Command Center');

console.log('======================================================================');
if (errors === 0) {
  console.log('  [ALL CHECKS PASSED] Frontend bundle is 100% production ready for Vercel.');
  console.log('======================================================================');
  process.exit(0);
} else {
  console.error(`  [FAILED] ${errors} validation errors detected.`);
  console.log('======================================================================');
  process.exit(1);
}
