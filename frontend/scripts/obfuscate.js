const { readdirSync, readFileSync, writeFileSync } = require('fs');
const { join } = require('path');
const JavaScriptObfuscator = require('javascript-obfuscator');

const JS_DIR = join(__dirname, '..', 'build', 'static', 'js');

const options = {
  compact: true,
  controlFlowFlattening: true,
  controlFlowFlatteningThreshold: 0.4,
  deadCodeInjection: false,
  stringArray: true,
  stringArrayEncoding: ['rc4'],
  stringArrayThreshold: 0.5,
  unicodeEscapeSequence: false,
  selfDefending: false,
  sourceMap: false,
};

const files = readdirSync(JS_DIR).filter(f => f.endsWith('.js') && !f.endsWith('.LICENSE.txt'));

console.log(`Obfuscating ${files.length} JS files...`);

for (const file of files) {
  const filePath = join(JS_DIR, file);
  const code = readFileSync(filePath, 'utf8');
  const result = JavaScriptObfuscator.obfuscate(code, options);
  writeFileSync(filePath, result.getObfuscatedCode());
  console.log(`  ${file}`);
}

console.log('Done.');
