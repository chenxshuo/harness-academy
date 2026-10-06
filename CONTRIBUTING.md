# Working on this repo

This repository is the deployed site. It is published from a monorepo where
the curriculum source sits next to the reference solutions that validate it.

```
.            the site - Vite, no build step beyond npm
course/      the curriculum source, in Python
public/      the generated content bundle, committed
```

## Changing the site

Edit and `npm run dev`. Nothing else is needed - `public/content/` is
committed, so the site builds with Node alone.

## Changing the curriculum

Edit under `course/src/academy/`, then:

```bash
npm run content   # regenerate public/content/ (needs uv and a tau checkout)
npm run check
```

`npm run content` reads the Tau specimen from `../tau`. Clone it alongside
this repository if you need to regenerate the bundled excerpts.

Reference solutions are deliberately not published - they are the answers to
the exercises - so `npm run test:python` is monorepo-only. The Pyodide and
browser checks run here.
