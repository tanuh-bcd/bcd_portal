const { readdirSync, readFileSync, writeFileSync, statSync } = require('fs');
const { join } = require('path');
const JavaScriptObfuscator = require('javascript-obfuscator');

const JS_DIR = join(__dirname, '..', 'build', 'static', 'js');

const MAX_SIZE = 200 * 1024; // skip files over 200KB (vendor chunks)

const options = {
  compact: true,
  controlFlowFlattening: false,
  deadCodeInjection: false,
  identifierNamesGenerator: 'hexadecimal',
  renameGlobals: false,
  stringArray: true,
  stringArrayEncoding: ['base64'],
  stringArrayThreshold: 0.5,
  unicodeEscapeSequence: false,
  selfDefending: false,
  sourceMap: false,
};

const files = readdirSync(JS_DIR).filter(f => f.endsWith('.js') && !f.endsWith('.LICENSE.txt'));

console.log(`Obfuscating JS files (skipping vendor chunks > ${MAX_SIZE / 1024}KB)...`);

for (const file of files) {
  const filePath = join(JS_DIR, file);
  const size = statSync(filePath).size;

  if (size > MAX_SIZE) {
    console.log(`  SKIP ${file} (${(size / 1024).toFixed(0)}KB — vendor chunk)`);
    continue;
  }

  const code = readFileSync(filePath, 'utf8');
  const result = JavaScriptObfuscator.obfuscate(code, options);
  writeFileSync(filePath, result.getObfuscatedCode());
  console.log(`  ${file} (${(size / 1024).toFixed(0)}KB)`);
}

console.log('Done.');
