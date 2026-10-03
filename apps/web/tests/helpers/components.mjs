import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import React from 'react';
import * as status from '../../lib/status.mjs';
import * as identity from '../../lib/entity-identity.mjs';
import * as presentation from '../../lib/presentation.mjs';
import * as assetIcon from '../../lib/asset-icon.mjs';
import * as operations from '../../lib/operations-experience.mjs';
import * as navigationIcon from '../../components/navigation-icon.mjs';
import * as presentationIdentity from '../../components/presentation-identity.mjs';
const require = createRequire(import.meta.url);
const { transformSync } = require('next/dist/compiled/babel/core');
const namespaces = { 'status.mjs': status, 'entity-identity.mjs': identity, 'presentation.mjs': presentation, 'asset-icon.mjs': assetIcon, 'operations-experience.mjs': operations, 'navigation-icon.mjs': navigationIcon, 'presentation-identity.mjs': presentationIdentity };
const cache = new Map();
export function loadComponent(url) {
  if (!url.pathname.endsWith('.js')) url = new URL(`${url.href}.js`);
  if (cache.has(url.href)) return cache.get(url.href);
  const { code } = transformSync(readFileSync(url, 'utf8'), { babelrc: false, configFile: false,
    presets: [[require('next/dist/compiled/babel/preset-react'), { runtime: 'classic' }]],
    plugins: [require('next/dist/compiled/babel/plugin-transform-modules-commonjs')],
  });
  const exports = {}; cache.set(url.href, exports);
  Function('require', 'exports', 'React', code)((name) => {
    if (name === 'react') return React;
    if (name === 'next/link') return { __esModule: true, default: ({ children, ...props }) => React.createElement('a', props, children) };
    if (name.endsWith('.mjs')) {
      const module = namespaces[name.split('/').at(-1)];
      if (!module) throw new Error(`Unregistered test module: ${name}`);
      return module;
    }
    return loadComponent(new URL(name, url));
  }, exports, React);
  return exports;
}
