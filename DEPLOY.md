# Deploying to harness-academy.schen.app

`schen.app` is on GitHub Pages behind Cloudflare DNS. That makes **Cloudflare
Pages** the natural home for this: same DNS account, so the subdomain is one
click rather than a manual record, and it serves the `_headers` file the build
already ships.

GitHub Pages works too and is covered below. Either way the site is static —
there is no server to run, and nothing to secure.

---

## Option A — Cloudflare Pages (recommended)

### 1. Push this repo to GitHub

Pages builds from a repository. If the course lives in a monorepo, note the
subdirectory; the build settings below account for it.

### 2. Create the project

In the Cloudflare dashboard: **Workers & Pages → Create → Pages → Connect to
Git**, pick the repo, then set:

| setting | value |
|---|---|
| Framework preset | None |
| Build command | `npm run build:ci` |
| Build output directory | `dist` |
| Root directory | leave empty |
| Deploy command | leave empty |
| Node version | `20` or newer (env var `NODE_VERSION`) |

**Use `build:ci`, not `build`.** `npm run build` runs `npm run content` first,
which needs `uv`, Python and a `tau/` checkout. Cloudflare's build image has
none of those, so it fails. `build:ci` is `vite build` alone, against the
committed `public/content/` - see *Content generation* below.

**Leave the deploy and preview commands empty.** Those fields belong to the
Workers Builds flow, where you ship a Worker and call `wrangler` yourself. A
static Pages site has nothing to run after the build: Cloudflare publishes
whatever is in `dist`, and builds non-production branches with the same build
command automatically, giving a preview URL per branch.

If the form *requires* a deploy command, you are in the Workers flow rather
than Pages. Back out and create a Pages project instead; there is no
`wrangler.toml` here, so the Workers path would need one added first.

### 3. Add the subdomain

**Custom domains → Set up a custom domain → `harness-academy.schen.app`.**

Because `schen.app` is already on Cloudflare DNS, the CNAME is created for you
and the certificate is issued automatically. Nothing about `schen.app` itself
changes — the apex keeps pointing at GitHub Pages.

### 4. Check it

Visit the domain and confirm:

- the map renders 16 levels
- opening Level 1 and answering a prediction works (this boots Pyodide)
- an implement step runs tests in the embedded terminal

---

## Option B — GitHub Pages

Consistent with how `schen.app` is already hosted.

### 1. Workflow

`.github/workflows/deploy-academy.yml`:

```yaml
name: Deploy Harness Academy

on:
  push:
    branches: [main, master]
    paths: ["web-next/**", ".github/workflows/deploy-academy.yml"]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages-academy
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
          cache-dependency-path: web-next/package-lock.json
      - run: npm ci
        working-directory: web-next
      - run: npm run build:ci
        working-directory: web-next
      - uses: actions/upload-pages-artifact@v3
        with:
          path: web-next/dist

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

This is committed as `.github/workflows/deploy-academy.yml`, ready to use. It
runs `build:ci`, which assumes the content bundle is committed.

### 2. Repository settings

**Settings → Pages → Source: GitHub Actions**, then **Custom domain:
`harness-academy.schen.app`** and tick **Enforce HTTPS**.

### 3. DNS in Cloudflare

Add one record on the `schen.app` zone:

| type | name | target | proxy |
|---|---|---|---|
| CNAME | `harness-academy` | `<user>.github.io` | **DNS only** |

Set the proxy to **DNS only** (grey cloud) until GitHub has issued the
certificate, or validation fails. You can switch it to proxied afterwards.

GitHub Pages does not read `_headers`, so caching falls back to its defaults.
That is fine; it costs a little repeat bandwidth, nothing else.

---

## Content generation

`npm run build` runs `npm run content`, which regenerates
`public/content/*.json` from the Python sources — and that needs Python and
`uv`. CI images generally have neither.

Two ways round it, pick one:

**Commit the generated content** — this is what the repo does now.
`public/content/` is tracked, so CI needs only Node. After changing the
curriculum, run `npm run content` locally and commit the result.

**Or generate in CI**, by adding this before the build step:

```yaml
      - uses: astral-sh/setup-uv@v5
      - run: npm run content
        working-directory: web-next
```

and leaving the build step as `npm run build`, which regenerates content.

---

## What actually gets served

```
dist/
  index.html            3.8 KB
  assets/*.js|css       ~500 KB  (170 KB gzipped)
  content/*.json        ~440 KB  (107 KB gzipped)
  pyodide-worker.js
  _headers              cache rules (Cloudflare/Netlify only)
  404.html
```

About **290 KB gzipped**. Pyodide (~5 MB) loads from jsDelivr on demand, after
first paint, and only when a learner reaches something that runs Python.

The build is base-relative, so it also works from a subdirectory — you could
serve it at `schen.app/harness-academy/` instead of a subdomain without any
change.

## Cost and load

There is no backend, so no compute to pay for and nothing to scale. The
learner's Python runs in their own browser.

The tutor runs on **the learner's own OpenRouter key**, connected in one click
via OAuth. You are not funding anyone's tokens, and their rate limits are
their own. Everything else works without a key.

## Updating

Push to the branch. Both options rebuild automatically.

## Checks worth running before a deploy

```bash
cd web-next
npm run check    # unit tests, pytest, and the same suite under Pyodide
npm run build
npx vite preview --port 5273
npm run test:browser
```
