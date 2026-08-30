# BDA Frontend v2

React 19 + TypeScript + Vite frontend for the native `/api/v2` contract. It uses generated OpenAPI types, Zod at dynamic research boundaries, TanStack Query, Zustand, React Flow, and Mol*.

```bash
npm ci
npm run generate:api
npm run dev
npm test
npm run lint
npm run build
```

`VITE_API_BASE` defaults to `/api/v2`. Authentication uses a session access token and an HttpOnly refresh cookie; uploads use browser SHA-256 plus presigned MinIO PUT. Resource edits use UUIDs, cursor pages, ETags, Problem Details, and SSE.

See [docs/FRONTEND_V2.md](../docs/FRONTEND_V2.md) for page contracts, state, authentication, upload, streaming, errors, and tests.
