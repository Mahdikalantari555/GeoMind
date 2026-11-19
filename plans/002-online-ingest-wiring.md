# Plan 002: Wire studio's ingest flow to the real gateway in online mode

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving on.
> If a STOP condition triggers, stop and report — do not improvise. When
> done, update the status row for this plan in `plans/README.md` — unless a
> reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat 2b85a31..HEAD -- apps/studio/src/lib/store.tsx apps/studio/src/lib/api.ts apps/studio/src/lib/types.ts`
> Compare the "Current state" excerpts below against the live code; on
> mismatch treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/001-studio-gateway-dev-fix.md (online mode must be
  reachable in dev to verify this plan end-to-end)
- **Category**: bug
- **Planned at**: commit `2b85a31`, 2026-11-14

## Why this matters

In online mode (gateway up, demo opt-in off), the studio Resources view's
**ingest flow never talks to the gateway at all**. It fabricates a client-side
job id (`uid("job")`) that can never match the gateway's server-generated SSE
job ids, fabricates a sha256 with `fakeSha()`, and registers a fake asset
row. Result: with the gateway online, "Ingest files" shows a job card stuck
at 0% forever, no asset is created server-side, and no error surfaces —
the exact "silent fake" behavior commit `2d4b6fa` ("demo mode becomes
opt-in only") set out to eliminate. Two secondary defects in the same SSE
subscription layer compound this: the EventSource is closed on the first
transient error (no reconnect), and listeners are never removed for
failed/cancelled jobs (leak).

## Current state

- `apps/studio/src/lib/store.tsx:88` — client id generator:
  ```ts
  const uid = (p: string) => `${p}-${Date.now().toString(36).slice(-4)}${(idc++).toString(36)}`;
  ```
- `store.tsx:171-190` — `startJob` online branch subscribes with the
  **client-side** id and only unsubscribes on `"complete"`:
  ```ts
  if (online) {
    const unsub = subscribeJob(job.id, (e) => {
      patchJob(job.id, (cur) => ({ ... }));
      if (e.status === "complete") {
        unsub();
        opts.onDone?.(e.result);
      }
    });
    return job.id;
  }
  ```
- `store.tsx:265-295` — `ingestFiles` fabricates everything locally:
  ```ts
  const fakeSha = () => Array.from({ length: 64 }, () => "0123456789abcdef"[Math.floor(Math.random() * 16)]).join("");
  const ingestFiles: Store["ingestFiles"] = (files) => {
    files.forEach((f) => {
      const type = fileType(f.name);
      const vision = type === "tif";
      const steps = [...];
      startJob(
        { id: uid("job"), kind: "ingest", title: `Ingest ${f.name}`, steps, meta: { file: f.name } },
        { stepMs: 900, onDone: () => { setAssets(...sha256: fakeSha()...); ... addLayer(...); toast(...); } },
      );
    });
  };
  ```
  Note: `ingestFiles` currently receives `{ name: string; size: number }[]`
  (see `store.tsx:55` and the `Store` interface) — the real `File` objects
  are dropped before this function, so you must widen the signature to carry
  the `File` objects for upload.
- `apps/studio/src/lib/api.ts:167-198` — `subscribeJob`:
  ```ts
  export function subscribeJob(jobId: string, onEvent: (e: {...}) => void): () => void {
    if (!gatewayUp || !API_BASE) return () => {};
    const es = new EventSource(`${API_BASE}/api/v1/events`);
    es.addEventListener("job.progress", (ev) => {
      ...
      if (payload.id !== jobId) return;
      const progress = payload.percent ?? Math.round((payload.progress ?? 0) * 100);
      const status = payload.status === "completed" ? "complete" : payload.status;
      onEvent({...});
    });
    es.onerror = () => es.close();          // ← kills auto-reconnect
    return () => es.close();
  }
  ```
- Gateway contract (do not change it — studio adapts to it):
  - `POST /api/v1/ingest` — multipart, 202. Form fields: `file`
    (UploadFile), `collection_id` (string, **required**), optional
    `index_after` (bool), `parser` (string). Response:
    `{"job_id": "<server id>", "status": "accepted"}`.
    (`server/src/geofront_api/routers/ingest.py:119-130`)
  - Server job ids look like `uuid4().hex[:12]` (`jobs.py:77`).
  - SSE events arrive on the `job.progress` event name with payload
    `{id, status: "running"|"completed"|"error"|"failed"|"cancelled", percent, stage, detail, result}`
    (`jobs.py:120-251`). `failed` currently only arrives under the legacy
    `job_progress` name — see plan 010's maintenance note; treat
    `status === "error"` as terminal here.
  - The ingest job result (delivered in `event.result` on completion)
    contains `asset_id`, `revision_id`, `skipped`, `reason` —
    (`ingest.py:80-100`).
- **Exemplar to copy** — `apps/studio/src/views/AcquireView.tsx:55-66` does
  the correct two-phase dance for downloads: POST first, use the returned
  server `job_id` as the store job id, then `startJob`:
  ```ts
  job_id = (await requestDownload(sc.id, roi?.coords ?? null, { sensor, from, to })).job_id;
  s.startJob({ id: job_id ?? uid("job"), kind: "download", ... }, {...});
  ```

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Studio typecheck | `cd apps/studio && pnpm.cmd check` | exit 0 |
| Studio unit tests | `cd apps/studio && pnpm.cmd test` | all pass |
| Server tests | `conda run -n geo pytest server/tests -q` | 156+ passed (unchanged) |

**Windows note:** `pnpm.cmd`, not `pnpm`. Python via `conda run -n geo`.

## Scope

**In scope** (the only files you should modify):
- `apps/studio/src/lib/api.ts` (add `ingestFile`; fix `subscribeJob`)
- `apps/studio/src/lib/api.test.ts` (extend)
- `apps/studio/src/lib/store.tsx` (`startJob`, `ingestFiles`, callers)
- `apps/studio/src/views/ResourcesView.tsx` and any caller of
  `ingestFiles` (signature widening only)
- `apps/studio/src/lib/types.ts` (only if the `Asset`/job types need a
  server-id field)

**Out of scope** (do NOT touch):
- The gateway (`server/**`) — its contract is the fixed point.
- Demo-mode simulation branches — keep them working exactly as today
  (`DEMO_MODE=1` must still produce the simulated progress + fake asset,
  clearly labeled demo).
- `trainNow` / `AcquireView.download` — they already use server job ids
  correctly; only `subscribeJob` fixes apply to them.
- Asset dedup UI, collection picker UI — out of scope.

## Git workflow

- Branch: `advisor/002-online-ingest-wiring`
- Conventional commits: `fix(studio): upload files to the gateway in online ingest`, `fix(studio): keep SSE job subscription alive across reconnects`
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Add `ingestFile` to `api.ts`

Add near the other gateway calls, matching file style:

```ts
/** Upload one file to the gateway ingest job queue. Returns the server job id. */
export async function ingestFile(file: File, collectionId: string): Promise<{ job_id: string }> {
  requireGateway("file ingest");
  const form = new FormData();
  form.append("file", file);
  form.append("collection_id", collectionId);
  form.append("index_after", "true");
  const r = await fetch(`${API_BASE}/api/v1/ingest`, { method: "POST", body: form });
  if (!r.ok) throw new Error(await r.text());
  return (await r.json()) as { job_id: string };
}
```

Check how sibling functions handle error bodies (e.g. `post<T>` at the top
of `api.ts`) and reuse that helper instead of raw `fetch` if it supports
FormData — match the file's existing conventions.

**Verify**: `cd apps/studio && pnpm.cmd check` → exit 0.

### Step 2: Fix `subscribeJob` lifecycle

In `api.ts`:
1. Replace `es.onerror = () => es.close();` with a handler that leaves the
   EventSource open (the browser auto-reconnects) and reports a transient
   state: `es.onerror = () => onEvent({ progress: 0, status: "reconnecting" });`
   (add `"reconnecting"` handling in the subscriber so it does NOT flip the
   job to terminal status).
2. Document on the returned unsubscribe function that callers must call it
   for **every** terminal status.

In `store.tsx` `startJob` online branch: call `unsub()` and `opts.onDone`
for terminal statuses:

```ts
const terminal = e.status === "complete" || e.status === "error" || e.status === "failed" || e.status === "cancelled";
if (terminal) { unsub(); }
if (e.status === "complete") { opts.onDone?.(e.result); }
if (e.status === "error" || e.status === "failed") {
  patchJob(job.id, (cur) => ({ status: "failed", logs: [...cur.logs, `[job] ${e.log ?? "job failed"}`] }));
}
if (e.status === "cancelled") { patchJob(job.id, (cur) => ({ status: "cancelled" })); }
```

`trainNow` (`store.tsx:314-321`) already unsubscribes on
`"complete" || "error"` — leave its logic; it now benefits from not closing
on transient errors.

**Verify**: `pnpm.cmd check` + `pnpm.cmd test` → pass.

### Step 3: Rewire `ingestFiles` for online mode

1. Widen the store signature (`store.tsx:55` and the `Store` interface):
   `ingestFiles: (files: { file: File; name: string; size: number }[]) => void`
   (or pass `File[]` and derive name/size inside — pick the smaller diff).
   Update the caller(s) — grep `ingestFiles(` under `src/` (ResourcesView)
   and pass the real `File` objects from the input change event.
2. In `ingestFiles`, branch on `online`:
   - **Online**: resolve the collection id (use the settings' default
     collection name the gateway accepts; if the store has no collection
     concept, use `"default"` only if the gateway tolerates it — otherwise
     STOP per conditions below). Call `await ingestFile(file, collectionId)`
     inside a try/catch; on success call `startJob({ id: resp.job_id, kind: "ingest", title: \`Ingest ${f.name}\`, steps, meta }, { onDone })`.
     On POST failure: `patchJob` the card to `failed` with the error log —
     never fake progress.
   - **Demo** (`DEMO_MODE` and offline): keep today's simulated path
     unchanged (uid id, fakeSha asset, synthetic steps).
   - **Online but gateway down**: `startJob` already fails loudly
     (`store.tsx:191-197`); do not fabricate assets.
3. In the online `onDone`, replace the fabricated `setAssets` entry with
   data from `e.result` (`asset_id`, hash if present in result) and keep the
   layer/toast behavior for rasters/vectors. If `e.result` lacks the fields
   you need for the asset card, fall back to a refetch of assets (the
   gateway has asset list routes — check `api.ts` for an existing
   `listAssets`-style helper; if none exists, render the card from
   `meta` + `e.result.asset_id` rather than a fake sha).

**Verify**: `pnpm.cmd check` → exit 0; `pnpm.cmd test` → pass.

### Step 4: Manual end-to-end verification (requires gateway running)

1. Start gateway: `conda run -n geo uvicorn geofront_api.main:app --port 8000`
2. Start studio: `cd apps/studio && pnpm.cmd dev` → http://localhost:5174
3. In studio Resources view, ingest any small `.txt` file.
4. Expected: job card shows a server job id, progresses via SSE, completes;
   `curl http://localhost:8000/api/v1/assets` (or the collections/assets
   route the UI uses) lists the new asset with a real sha256.
5. Kill the gateway mid-job once and confirm the card surfaces a
   failure/reconnect state instead of freezing silently (soft check — a
   frozen card after gateway death is acceptable only if a reconnecting
   status is shown).

**Verify**: record what you observed in the final report. If you cannot run
the gateway (no env), report that explicitly instead of claiming success.

## Test plan

- New tests in `api.test.ts`:
  - `ingestFile` posts multipart to `/api/v1/ingest` and returns `job_id`
    (stub `fetch`; follow existing stubbing style in that file).
  - `subscribeJob` does not close the EventSource on `onerror` (spy that
    `es.close` was not called) and surfaces a `reconnecting` event.
  - `subscribeJob` unsubscribes on `error`/`failed`/`cancelled` statuses.
- Store-level tests are NOT required by this plan (store has no test file
  yet); the api-level tests above pin the contract.
- Verification: `pnpm.cmd test` → all pass including ≥3 new tests.

## Done criteria

- [ ] `cd apps/studio && pnpm.cmd check` → exit 0
- [ ] `cd apps/studio && pnpm.cmd test` → all pass incl. new tests
- [ ] `grep -n "fakeSha" apps/studio/src/lib/store.tsx` → `fakeSha` remains
      ONLY inside the demo-mode branch
- [ ] `grep -n "uid(\"job\")" apps/studio/src/lib/store.tsx` → no occurrence
      on the online ingest path (demo path may keep it)
- [ ] `conda run -n geo pytest server/tests -q` → unchanged pass count
- [ ] No gateway files modified (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

- The gateway route `POST /api/v1/ingest` requires `collection_id` and the
  store has no notion of which collection to target, and no documented
  default exists in `docs/SPEC_SERVER.md` or the gateway schemas — report;
  this needs an owner decision (do not invent a collection silently).
- `subscribeJob`'s payload shape differs from the excerpt (event renamed or
  fields moved) — report the drift.
- `ResourcesView` passes something other than real `File` objects and
  cannot be changed without touching >2 additional files — report scope.

## Maintenance notes

- When plan 010 lands (event-name cleanup), `subscribeJob` may simplify.
- Future multi-file upload batching (one POST per file today) is fine — the
  gateway job manager serializes.
- Reviewer should scrutinize: no demo-only helpers (`fakeSha`, synthetic
  steps) reachable from the online path; terminal-status handling covers
  all four statuses.
