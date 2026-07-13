// UNTRUSTED candidate sandbox — the ONLY process that executes JS candidate code
// (audit A3, Node twin of oracle/sandbox_runner.py).
//
// Two-process integrity property:
//   worker (oracle_js/isolate_worker.mjs, TRUSTED)  holds the verdict sentinel +
//     the real stdout, computes NOTHING with candidate code; it spawns THIS
//     process and talks to it over two dedicated pipes (fd 3 = worker->sandbox
//     requests, fd 4 = sandbox->worker results).
//   sandbox (this file, UNTRUSTED)  loads + runs the candidate and returns, per
//     request, the canonJson of the candidate's output (or a raised/unencodable
//     marker). It CANNOT reach the verdict channel: its fd 1/fd 2 are wired to
//     /dev/null by the worker's spawn, and the sentinel is never sent here — so a
//     candidate that prints a forged framed verdict + a sentinel guess reaches
//     nothing. Only canon VALUES cross fd 4; the worker classifies them against
//     the answer key (which lives only in the worker), so even a candidate that
//     forges a result on fd 4 can at most claim its own output was X — it cannot
//     learn the hidden reference, hence cannot turn a wrong answer into CORRECT.
//   This is why the Node port needs only two processes where Python uses three
//   (its relay+fork exists to stop the child forging call-RESULTS; here forging a
//   result is harmless because the answer key is not in this process). See the
//   return report / THREAT_MODEL.md for the full justification.
//
// Answer-key block (A2 parity): the candidate module is written into a scrubbed
// temp dir OUTSIDE the repo (with only a node_modules symlink for the polyfill)
// and the process chdir's there, so `import "../refs/all.mjs"` and
// `readFileSync("oracle_js/tasks_export.json")` both fail — the JS twin of the
// Python child's sys.path / cwd scrub. Answer-key discovery by ABSOLUTE path
// stays out of scope (THREAT_MODEL.md), exactly as on the Python side.
//
// Protocol (length-prefixed JSON, big-endian u32 header):
//   worker -> {"cmd":"load","source":str,"entry_point":str}
//   sandbox-> {"loaded":bool,"error":str}
//   worker -> {"cmd":"call","args":[<neutral>,...]}
//   sandbox-> {"ok":true,"canon":[...]} | {"ok":false,"kind":"raised"|"unencodable","error":str}
//   worker -> {"cmd":"stop"}
process.env.TZ = "UTC";   // ESM note: no static imports, so this runs before any date work

const fs = await import("node:fs");
const os = await import("node:os");
const { fileURLToPath, pathToFileURL } = await import("node:url");
const { dirname, join } = await import("node:path");

// --------------------------------------------------------------------------- //
// Framed message helpers (shared with the worker, twin of read_msg/write_msg).
// --------------------------------------------------------------------------- //
export function writeFrame(stream, obj) {
  const body = Buffer.from(JSON.stringify(obj), "utf8");
  const hdr = Buffer.alloc(4);
  hdr.writeUInt32BE(body.length, 0);
  stream.write(Buffer.concat([hdr, body]));
}

// Returns next() -> Promise<message | null> (null == EOF / channel closed).
export function makeFrameReader(stream) {
  let buf = Buffer.alloc(0);
  let ended = false;
  const waiters = [];
  const pump = () => {
    while (waiters.length) {
      if (buf.length < 4) break;
      const n = buf.readUInt32BE(0);
      if (buf.length < 4 + n) break;
      const body = buf.subarray(4, 4 + n);
      buf = buf.subarray(4 + n);
      let msg = null;
      try { msg = JSON.parse(body.toString("utf8")); } catch { msg = null; }
      waiters.shift().resolve(msg);
    }
    if (ended) while (waiters.length) waiters.shift().resolve(null);
  };
  stream.on("data", (c) => { buf = Buffer.concat([buf, c]); pump(); });
  stream.on("end", () => { ended = true; pump(); });
  stream.on("error", () => { ended = true; pump(); });
  return () => new Promise((resolve) => { waiters.push({ resolve }); pump(); });
}

async function main() {
  const realExit = process.exit.bind(process);
  const here = dirname(fileURLToPath(import.meta.url));   // oracle_js/

  // ---- scrub: candidate module dir OUTSIDE the repo + node_modules symlink --- //
  const scrub = fs.mkdtempSync(join(os.tmpdir(), "cg_sbx_"));
  try {
    fs.symlinkSync(join(here, "node_modules"), join(scrub, "node_modules"), "dir");
  } catch { /* bare-specifier candidates fall back to the global Temporal below */ }

  // ---- trusted machinery, imported by ABSOLUTE url (chdir cannot affect it) -- //
  const { loadCandidate } = await import(new URL("./run_oracle.mjs", import.meta.url));
  const { fromNeutral, canonJson } = await import(new URL("./neutral.mjs", import.meta.url));

  // Break relative FS reads of the answer key (ESM imports already broken by the
  // scrub-dir placement); then seal stdout/stderr at the stream layer too — the
  // worker already points fd 1/fd 2 at /dev/null, this is defence in depth.
  try { process.chdir(scrub); } catch { /* best effort */ }
  const sink = () => true;
  process.stdout.write = sink;
  process.stderr.write = sink;

  // Contain process.exit for the candidate's whole lifetime: a candidate calling
  // it becomes a thrown Error -> LOAD_ERROR (at load) / cand_raised (in a call),
  // never a silent sandbox death (Python audit CMP-2 parity).
  process.exit = (code) => { throw new Error(`SystemExit: process.exit(${code ?? 0}) blocked by sandbox`); };

  const reqStream = fs.createReadStream(null, { fd: 3 });   // worker -> sandbox
  const respStream = fs.createWriteStream(null, { fd: 4 }); // sandbox -> worker
  const nextReq = makeFrameReader(reqStream);

  const shutdown = (code) => {
    try { fs.rmSync(scrub, { recursive: true, force: true }); } catch { /* SIGKILL path leaks; hourly sweep reaps */ }
    realExit(code);
  };

  // ---- load the candidate (the only untrusted exec) ---- //
  const first = await nextReq();
  if (!first || first.cmd !== "load") {
    writeFrame(respStream, { loaded: false, error: "protocol error: expected 'load'" });
    return shutdown(0);
  }
  let fn = null, error = "";
  try {
    ({ fn, error } = await loadCandidate(first.source, first.entry_point, scrub));
  } catch (e) {
    error = `exec failed: ${e?.constructor?.name ?? "Error"}: ${e?.message ?? e}`;
  }
  if (!fn) {
    writeFrame(respStream, { loaded: false, error });
    return shutdown(0);
  }
  writeFrame(respStream, { loaded: true });

  // ---- serve one call-result per request ---- //
  for (;;) {
    const req = await nextReq();
    if (!req || req.cmd === "stop") break;
    if (req.cmd !== "call") {
      writeFrame(respStream, { ok: false, kind: "raised", error: `protocol error: cmd '${req.cmd}'` });
      continue;
    }
    let args;
    try {
      args = req.args.map(fromNeutral);               // neutral -> Temporal inputs (fresh per call)
    } catch (e) {
      writeFrame(respStream, { ok: false, kind: "raised",
        error: `bad-args: ${e?.constructor?.name ?? "Error"}: ${e?.message ?? e}` });
      continue;
    }
    let out;
    try {
      out = fn(...args);
      if (out && typeof out.then === "function") out = await out;   // async candidates
    } catch (e) {                                      // candidate raised (incl. contained process.exit)
      writeFrame(respStream, { ok: false, kind: "raised",
        error: `${e?.constructor?.name ?? "Error"}: ${e?.message ?? e}` });
      continue;
    }
    let canon;
    try {
      canon = canonJson(out);                          // reduce to the closed canonical domain
    } catch (e) {                                      // out-of-domain / cyclic -> WRONG VALUE, not a crash
      writeFrame(respStream, { ok: false, kind: "unencodable",
        error: `${e?.constructor?.name ?? "Error"}: ${e?.message ?? e}` });
      continue;
    }
    writeFrame(respStream, { ok: true, canon });
  }
  return shutdown(0);
}

// Only run the sandbox when executed directly; the worker imports the framing
// helpers above without spawning a candidate loop.
if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  main().catch(() => { try { process.exit(0); } catch { /* unreachable */ } });
}
