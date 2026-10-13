/** Static checks only. Never import or execute generated code on the host. */
import ts from 'typescript';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const react = new Set(['useMemo', 'Fragment']);
const remotion = new Set(['AbsoluteFill','Sequence','Series','Img','Audio','OffthreadVideo','useCurrentFrame','useVideoConfig','interpolate','interpolateColors','spring','Easing','staticFile','random']);
const forbidden = new Set(['eval','Function','global','globalThis','window','document','process','require','module','exports','fetch','XMLHttpRequest','WebSocket','Worker','SharedWorker','navigator','location','localStorage','sessionStorage','indexedDB','setTimeout','setInterval','requestAnimationFrame','Date','performance','crypto','constructor','prototype','__proto__','dangerouslySetInnerHTML','innerHTML','outerHTML','importScripts','alert','open','useEffect','useLayoutEffect','useState','createElement','cloneElement','createPortal','createRef','delayRender','continueRender']);
export function validate(source, assets = []) {
  if (typeof source !== 'string' || source.length > 100000) throw Error('Scene must be TSX under 100 KB');
  const ast = ts.createSourceFile('Scene.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const errors = ast.parseDiagnostics.map(d => ts.flattenDiagnosticMessageText(d.messageText, '\n'));
  let sceneExport = false, frameDriven = false;
  const fail = message => errors.push(message);
  function walk(n) {
    if (ts.isImportDeclaration(n)) {
      const mod = n.moduleSpecifier.text;
      if (!['react','remotion'].includes(mod)) fail(`Import not allowed: ${mod}`);
      const clause = n.importClause;
      if (!clause || clause.namedBindings && !ts.isNamedImports(clause.namedBindings)) fail('Namespace and side-effect imports are not allowed');
      if (clause?.name && (mod !== 'react' || clause.name.text !== 'React')) fail('Only React may be a default import');
      for (const el of clause?.namedBindings?.elements || []) {
        const name = el.propertyName?.text || el.name.text;
        if (!(mod === 'react' ? react : remotion).has(name)) fail(`Unsupported import: ${name}`);
        if (name !== el.name.text) fail('Import aliases are not allowed');
        if (name === 'useCurrentFrame') frameDriven = true;
      }
    }
    if (ts.isExportDeclaration(n) || ts.isExportAssignment(n)) fail('Export a named Scene function or const; no re-exports/default export');
    if (n.modifiers?.some(m => m.kind === ts.SyntaxKind.ExportKeyword)) {
      if (ts.isFunctionDeclaration(n) && n.name?.text === 'Scene') sceneExport = true;
      else if (ts.isVariableStatement(n) && n.declarationList.declarations.some(d => d.name.getText(ast) === 'Scene')) sceneExport = true;
      else fail('Only the Scene component may be exported');
    }
    if (ts.isIdentifier(n) && forbidden.has(n.text)) fail(`Forbidden capability: ${n.text}`);
    if (ts.isElementAccessExpression(n)) {
      // Array access is useful; reject string/computed member escapes. OS sandbox remains mandatory.
      if (!ts.isNumericLiteral(n.argumentExpression) && !ts.isIdentifier(n.argumentExpression)) fail('Only numeric/index-variable array access is supported');
    }
    if (ts.isNewExpression(n) || ts.isAwaitExpression(n) || ts.isImportEqualsDeclaration(n)) fail('No constructors, async, or require imports');
    if (ts.isCallExpression(n) && n.expression.kind === ts.SyntaxKind.ImportKeyword) fail('Dynamic imports are forbidden');
    if (ts.isCallExpression(n) && n.expression.getText(ast) === 'Math.random') fail('Use seeded Remotion random()');
    if (ts.isStringLiteralLike(n)) {
      const v = n.text;
      if (/(https?:|file:|data:|javascript:|\/\/|@import|url\s*\((?!#)|animation\s*:|transition\s*:|@keyframes)/i.test(v)) fail('No external URLs, embedded data, or CSS animation');
      if (['animation','animationName','animationDuration','transition','transitionDuration'].includes(v)) fail('Use frame-driven animation');
    }
    if (ts.isPropertyAssignment(n) && /^(animation|transition)/i.test(n.name.getText(ast))) fail('Use frame-driven animation');
    if (ts.isJsxOpeningElement(n) || ts.isJsxSelfClosingElement(n)) {
      const tag = n.tagName.getText(ast);
      const forbiddenTags = ['script','iframe','object','embed','link','meta','foreignObject','style','video','audio'];
      if (forbiddenTags.includes(tag) || tag.includes('.')) fail(`Unsupported element ${tag}`);
    }
    if (ts.isJsxAttribute(n) && (/^on[A-Z]/.test(n.name.getText(ast)) || ['href','xlinkHref'].includes(n.name.getText(ast)))) fail('No event handlers or navigation');
    if (ts.isCallExpression(n) && n.expression.getText(ast) === 'staticFile') {
      if (n.arguments.length !== 1 || !ts.isStringLiteral(n.arguments[0]) || !assets.includes(n.arguments[0].text)) fail('staticFile must use a literal approved asset filename');
    }
    if (ts.isJsxAttribute(n) && n.name.getText(ast) === 'src') {
      const expr = n.initializer?.expression;
      if (!expr || !ts.isCallExpression(expr) || expr.expression.getText(ast) !== 'staticFile') fail('Media src must be staticFile(approved asset)');
    }
    ts.forEachChild(n, walk);
  }
  walk(ast);
  if (!sceneExport) fail('Missing export function Scene or export const Scene');
  if (!frameDriven) fail('Use useCurrentFrame for deterministic timing');
  if (errors.length) throw Error([...new Set(errors)].join('\n'));
  return true;
}
export function typecheck(project) {
  const options = {jsx:ts.JsxEmit.ReactJSX, target:ts.ScriptTarget.ES2020, module:ts.ModuleKind.ESNext, moduleResolution:ts.ModuleResolutionKind.Bundler, strict:true, noEmit:true, esModuleInterop:true, skipLibCheck:true, types:['react','react-dom'], typeRoots:[path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../node_modules/@types')]};
  const host = ts.createCompilerHost(options);
  // Projects live outside our service directory; resolve only trusted installed dependencies.
  host.resolveModuleNames = (names, containingFile) => names.map(name => ts.resolveModuleName(name, containingFile.includes('node_modules') || name.startsWith('.') ? containingFile : path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../__resolve.tsx'), options, host).resolvedModule);
  const program = ts.createProgram([path.join(project,'Scene.tsx')], options, host);
  const diagnostics = ts.getPreEmitDiagnostics(program);
  if (diagnostics.length) throw Error(ts.formatDiagnosticsWithColorAndContext(diagnostics,{getCanonicalFileName:x=>x,getCurrentDirectory:()=>project,getNewLine:()=> '\n'}));
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const project = path.resolve(process.argv[2]);
    const manifest = JSON.parse(fs.readFileSync(path.join(project,'job.json'),'utf8'));
    validate(fs.readFileSync(path.join(project,'Scene.tsx'),'utf8'), manifest.assets.map(a=>a.file));
    typecheck(project);
    console.log(JSON.stringify({valid:true}));
  } catch(e) { console.error(e.message); process.exitCode=1; }
}
