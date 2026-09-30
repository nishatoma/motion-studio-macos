"""Export validated Motion Studio vector beats as an editable Motion Canvas project.

The model never supplies TypeScript. Only data from app.validate_spec is embedded.
Motion Canvas renders in its own browser editor; this module does not pretend to
provide an unattended CLI renderer.
"""

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


PACKAGE = {
    "name": "motion-studio-motion-canvas",
    "private": True,
    "scripts": {"serve": "vite --host 127.0.0.1", "typecheck": "tsc --noEmit"},
    "dependencies": {
        "@motion-canvas/2d": "3.17.2",
        "@motion-canvas/core": "3.17.2",
        "@motion-canvas/ui": "3.17.2",
        "@motion-canvas/vite-plugin": "3.17.2",
    },
    "devDependencies": {"typescript": "^5.5.0", "vite": "^5.4.0"},
}

SCENE = r'''import {Circle, Line, Node, Path, Rect, Txt, makeScene2D} from '@motion-canvas/2d';
import {all, waitFor} from '@motion-canvas/core';
import raw from '../scene.json';

// Data is produced by Motion Studio's bounded JSON validator, not executable AI code.
type Part = {type: string; id?: string; text?: string; color: string;
  position: number[]; size?: number[]; points?: number[][]; stroke_width?: number;
  fill_opacity?: number; fill_color?: string; glow?: boolean; rotation?: number;
  start_angle?: number; angle?: number};
type Action = {target: string; type: string; position?: number[]; factor?: number; degrees?: number};
type Beat = {duration: number; clear_before: boolean; items: Part[]; actions: Action[]};
const spec = raw as {beats: Beat[]};
const U = 135; // Manim's 8-unit frame maps to 1080 pixels.
const at = (point: number[]) => [point[0] * U, -point[1] * U] as [number, number];
const fmt = (n: number) => Number(n.toFixed(2));

function geometry(part: Part): Node {
  const [w, h] = part.size ?? [3, 1];
  const stroke = part.color;
  const lineWidth = (part.stroke_width ?? 4) * 1.5;
  const fill = part.fill_opacity ? `${part.fill_color ?? stroke}${Math.round(part.fill_opacity * 255).toString(16).padStart(2, '0')}` : undefined;
  const base = {position: at(part.position), rotation: -(part.rotation ?? 0),
    stroke, lineWidth, fill, opacity: 0,
    shadowColor: part.glow ? stroke : 'transparent', shadowBlur: part.glow ? 32 : 0};
  if (['text', 'title', 'number'].includes(part.type)) {
    return new Txt({text: part.text ?? '', position: at(part.position),
      fill: part.color, fontFamily: 'Arial', fontWeight: part.type === 'title' ? 700 : 500,
      fontSize: 44, opacity: 0});
  }
  if (part.type === 'circle' || part.type === 'ring' || part.type === 'ellipse') {
    return new Circle({...base, width: w * U, height: (part.type === 'ellipse' ? h : w) * U,
      fill: part.type === 'ring' ? undefined : fill,
      lineWidth: part.type === 'ring' ? w * U * 0.18 : lineWidth});
  }
  if (part.type === 'rectangle') {
    return new Rect({...base, width: w * U, height: h * U, radius: Math.min(16, w * U / 4)});
  }
  if (part.type === 'line' || part.type === 'arrow') {
    return new Line({...base, points: [[-w * U / 2, h * U / 2], [w * U / 2, -h * U / 2]],
      endArrow: part.type === 'arrow'});
  }
  let coords = part.points ?? [];
  if (part.type === 'star') {
    coords = Array.from({length: 10}, (_, i) => {
      const a = -Math.PI / 2 + i * Math.PI / 5, r = (i % 2 ? 0.23 : 0.5) * w;
      return [r * Math.cos(a), r * Math.sin(a)];
    });
  }
  if (part.type === 'arc') {
    const start = (part.start_angle ?? 0) * Math.PI / 180;
    const sweep = (part.angle ?? 180) * Math.PI / 180;
    coords = Array.from({length: 17}, (_, i) => {
      const a = start + sweep * i / 16;
      return [w / 2 * Math.cos(a), w / 2 * Math.sin(a)];
    });
  }
  const path = coords.map((p, i) => `${i ? 'L' : 'M'} ${fmt(p[0] * U)} ${fmt(-p[1] * U)}`).join(' ');
  return new Path({...base, data: path + (['polygon', 'star'].includes(part.type) ? ' Z' : ''),
    fill: ['polygon', 'star'].includes(part.type) ? fill : undefined});
}

export default makeScene2D(function* (view) {
  // Leave the project background blank in Video Settings to export PNGs with alpha.
  const objects = new Map<string, Node>();
  for (const beat of spec.beats) {
    if (beat.clear_before) {
      const old = [...view.children()];
      if (old.length) yield* all(...old.map(node => node.opacity(0, 0.25)));
      old.forEach(node => node.remove());
      objects.clear();
    }
    const changes = [];
    for (const part of beat.items) {
      const node = geometry(part);
      view.add(node);
      if (part.id) objects.set(part.id, node);
      changes.push(node.opacity(1, beat.duration));
    }
    for (const action of beat.actions) {
      const node = objects.get(action.target);
      if (!node) continue;
      switch (action.type) {
        case 'move_to': changes.push(node.position(at(action.position ?? [0, 0]), beat.duration)); break;
        case 'shift': {
          const [x, y] = at(action.position ?? [0, 0]);
          changes.push(node.position(node.position().add([x, y]), beat.duration)); break;
        }
        case 'scale': changes.push(node.scale(node.scale().mul(action.factor ?? 1), beat.duration)); break;
        case 'rotate': changes.push(node.rotation(node.rotation() - (action.degrees ?? 0), beat.duration)); break;
        case 'fade_out': changes.push(node.opacity(0, beat.duration)); break;
      }
    }
    if (changes.length) yield* all(...changes);
    else yield* waitFor(beat.duration);
    for (const action of beat.actions) if (action.type === 'fade_out') {
      objects.get(action.target)?.remove();
      objects.delete(action.target);
    }
  }
  yield* waitFor(0.4);
});
'''

README = """# Motion Studio → Motion Canvas (editable project)

This is an editable Motion Canvas version of the validated vector plan. It is
not a finished video. It uses the same shapes and actions as Motion Studio,
so it will not automatically improve an under-specified drawing.

1. Install Node.js 20 or newer, then run `npm install` and `npm run serve`
   from this folder. Open the local URL Vite prints (usually localhost:5173).
2. Play and edit `src/scenes/generated.tsx` in the Motion Canvas editor.
   Run `npm run typecheck` if you change the code.
3. In Video Settings, use 1920 × 1080 at 24 fps. For 4K, use a render scale
   of 2 (3840 × 2160). Keep the background empty for alpha. Render PNG frames.
4. Import the PNG sequence into Resolve. For ProRes 4444, use FFmpeg with
   `-c:v prores_ks -profile:v 4 -pix_fmt yuva444p10le`.

Motion Canvas currently renders through its editor; this project does not
provide an unattended one-click Motion Studio MP4 or MOV. Preview at 720p
before a high-resolution render. npm installs the open-source engine once.
"""


def write_project(plan: dict, destination: Path) -> None:
    """Package only validated vector beats; never execute or interpolate prompt text."""
    if not isinstance(plan.get("beats"), list) or any(
            item["type"] in {"graph", "face_marker"}
            for beat in plan["beats"] for item in beat["items"]):
        raise ValueError("Motion Canvas project export supports vector beats, not graphs or directed templates.")
    scene = {"beats": [{"duration": beat["duration"], "clear_before": beat.get("clear_before", False),
                        "items": beat["items"], "actions": beat.get("actions", [])} for beat in plan["beats"]]}
    with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
        archive.writestr("motion-canvas-project/package.json", json.dumps(PACKAGE, indent=2))
        archive.writestr("motion-canvas-project/vite.config.ts", "import {defineConfig} from 'vite';\nimport motionCanvas from '@motion-canvas/vite-plugin';\nexport default defineConfig({plugins: [motionCanvas()]});\n")
        archive.writestr("motion-canvas-project/tsconfig.json", json.dumps({
            "extends": "@motion-canvas/2d/tsconfig.project.json",
            "compilerOptions": {"moduleResolution": "bundler", "resolveJsonModule": True,
                                "skipLibCheck": True, "types": ["vite/client"]},
            "include": ["src", "node_modules/@motion-canvas/core/project.d.ts"]}, indent=2))
        archive.writestr("motion-canvas-project/src/project.ts", "import {makeProject} from '@motion-canvas/core';\nimport generated from './scenes/generated?scene';\nexport default makeProject({scenes: [generated]});\n")
        archive.writestr("motion-canvas-project/src/motion-canvas.d.ts", '/// <reference types="@motion-canvas/core/project" />\n')
        archive.writestr("motion-canvas-project/src/scenes/generated.tsx", SCENE)
        archive.writestr("motion-canvas-project/src/scene.json", json.dumps(scene, indent=2))
        archive.writestr("motion-canvas-project/README.md", README)
