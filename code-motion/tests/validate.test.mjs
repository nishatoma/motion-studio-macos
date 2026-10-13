import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
import {validate} from '../src/validate.mjs';
const prefix="import React from 'react'; import {useCurrentFrame} from 'remotion'; export const Scene=()=>{const frame=useCurrentFrame();";
for(const name of ['financial','kinetic','overlay','audio'])test(`accept ${name}`,()=>assert.equal(validate(fs.readFileSync(new URL(`../examples/${name}.tsx`,import.meta.url),'utf8')),true));
for(const code of ["fetch('https://example.com');", "process.env.OPENAI_API_KEY;", "eval('x');", "window.location;", "Math.random();", "setTimeout(()=>{},100);", "const x=new Function('return 1');", "import('node:fs');", "const x=Date.now();", "const x={transition:'all 1s'};", "const x={animationName:'spin'};", "const x=React['createElement'];"]){test(`reject ${code}`,()=>assert.throws(()=>validate(prefix+code+'return <div>{frame}</div>};')))}
test('reject imports',()=>assert.throws(()=>validate("import fs from 'node:fs'; "+prefix+'return <div/>};')));
test('reject media escape',()=>assert.throws(()=>validate(prefix+'return <img src="file:///etc/passwd"/>};')));
test('approved assets only',()=>{const source="import {Img,staticFile} from 'remotion';"+prefix+"return <Img src={staticFile('asset.png')}/>};";assert.throws(()=>validate(source));assert.equal(validate(source,['asset.png']),true)});
test('reject namespace imports',()=>assert.throws(()=>validate("import * as R from 'remotion'; "+prefix+'return <div/>};')));
