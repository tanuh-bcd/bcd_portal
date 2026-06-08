const { readdirSync, readFileSync, writeFileSync } = require('fs');
const { join } = require('path');
const JavaScriptObfuscator = require('javascript-obfuscator');

const JS_DIR = join(__dirname, '..', 'build', 'static', 'js');

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

const files = readdirSync(JS_DIR).filter(f => f.startsWith('main.') && f.endsWith('.js'));

if (files.length === 0) {
  console.log('No main bundle found — skipping obfuscation.');
  process.exit(0);
}

for (const file of files) {
  const filePath = join(JS_DIR, file);
  console.log(`Obfuscating ${file}...`);
  const code = readFileSync(filePath, 'utf8');
  const result = JavaScriptObfuscator.obfuscate(code, options);
  writeFileSync(filePath, result.getObfuscatedCode());
  console.log('Done.');
}
