import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Vite config, including the dev-server API proxy.
 *
 * Why the proxy exists: bin/proxy-server.js (the scaffold's CORS proxy on :3001)
 * rebuilds each forwarded request with only accept, content-type, user-agent and
 * host — so it drops the Authorization header, and every authenticated call from
 * the browser would arrive anonymous. Proxying through Vite's own dev server
 * instead keeps the header, and needs no change to bin/.
 *
 * Targets come from VITE_API_ENDPOINTS in .env.local, which bin/generate-env.sh
 * writes from the Terraform `api_endpoints` output: {"users-service": "<url>", ...}.
 * Deployed, that output holds paths rather than URLs and CloudFront does the
 * routing, so entries that are not absolute URLs are skipped here.
 *
 * https://vite.dev/config/
 */
export default defineConfig(({ mode }) => {
  // import.meta.dirname rather than process.cwd(): this resolves to the frontend
  // directory whatever directory vite was started from, and avoids referencing a
  // Node global that the repo's browser-targeted eslint config does not know.
  // The 'VITE_' prefix loads only the app's own variables, not the whole
  // environment this process happens to carry.
  const env = loadEnv(mode, import.meta.dirname, 'VITE_')

  let endpoints
  try {
    endpoints = JSON.parse(env.VITE_API_ENDPOINTS || '{}')
  } catch {
    // A malformed .env.local should not stop the dev server from booting; the
    // app then shows its services as unreachable, which is the honest state.
    endpoints = {}
  }

  const proxy = {}
  for (const [service, target] of Object.entries(endpoints)) {
    if (typeof target !== 'string' || !/^https?:\/\//.test(target)) continue
    proxy[`/api/${service}`] = {
      target,
      changeOrigin: true,
      // The Lambda Function URL serves routes at the root, so the
      // /api/{service} prefix is stripped before forwarding. CloudFront leaves
      // it on, which is why router.py accepts both shapes.
      rewrite: (path) => path.replace(`/api/${service}`, '') || '/',
    }
  }

  return {
    plugins: [react()],
    server: {
      port: 3000,
      proxy,
    },
    // Component tests run in jsdom, a fake browser, so a test can click a
    // button and read what appears without a real one being open.
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: './src/test/setup.js',
      css: false,
      coverage: {
        reporter: ['text-summary'],
        include: ['src/**/*.{js,jsx}'],
        // Entry points and config wire things together rather than deciding
        // anything, so counting them would only flatter the number.
        exclude: ['src/main.jsx', 'src/test/**', '**/*.test.jsx'],
      },
    },
  }
})
