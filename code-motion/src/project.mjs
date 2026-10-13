import fs from 'node:fs';
import path from 'node:path';
export function writeEntry(project, config) {
  // Metadata and media wrapper are trusted; the model owns only Scene.tsx.
  const audio = config.audio ? `<Audio src={staticFile(${JSON.stringify(config.audio)})} />` : '';
  const fonts = config.assets.filter(a=>a.kind==='font').map((a,i)=>`@font-face{font-family:ReferenceFont${i};src:url('${a.file}');font-display:block}`).join('');
  const root = `import React from 'react';
import {registerRoot, Composition, AbsoluteFill, Audio, staticFile} from 'remotion';
import {Scene} from './Scene';
const Wrapped = () => <AbsoluteFill style={{backgroundColor:${JSON.stringify(config.transparent?'transparent':'#07131f')}}}><Scene />${audio}</AbsoluteFill>;
registerRoot(() => <Composition id="CodeMotion" component={Wrapped} width={${config.width}} height={${config.height}} fps={${config.fps}} durationInFrames={${config.durationInFrames}} />);
`;
  fs.writeFileSync(path.join(project,'index.tsx'),root);
  const publicDir=path.join(project,'public');fs.mkdirSync(publicDir,{recursive:true});
  fs.writeFileSync(path.join(publicDir,'fonts.css'),fonts);
  // Webpack bundles font stylesheet, resolving fonts from the approved public directory.
  if(fonts) fs.appendFileSync(path.join(project,'index.tsx'),`\nimport './fonts.css';\n`);
  fs.writeFileSync(path.join(project,'fonts.css'),fonts.replaceAll("url('","url('./public/"));
}
