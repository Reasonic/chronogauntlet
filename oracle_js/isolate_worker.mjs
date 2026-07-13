// TRUSTED evaluator worker (audit A3, Node twin of oracle/isolate_worker.py).
//
// Evaluates ONE JS candidate and prints its verdict as a sentinel-framed JSON
// line on the REAL stdout. The critical property: this process NEVER executes
// candidate code. It spawns an untrusted sandbox (oracle_js/sandbox_runner.mjs)
// that runs the candidate, and proxies each candidate call to it over a dedicated
// pipe pair; the answer key (tasks_export.json), the comparison, and the outcome
// classification all live HERE, in a process the candidate cannot enter.
//
// Two-process integrity property (closes the A3 single-process defect):
//   * the verdict sentinel is read from stdin into THIS process only and is never
//     sent to the sandbox, and the candidate's stdout/stderr are wired to
//     /dev/null — so a candidate that prints a forged framed verdict + a sentinel
//     guess writes into a void it does not share with the verdict channel;
//   * only canon VALUES cross the boundary (never a live object, never code — the
//     twin of oracle/safecodec.py: JSON is parsed, never eval'd, and rebuilt via
//     neutral.fromCanon into inert Temporal values), so no candidate __proto__ /
//     getter runs in the evaluator;
//   * the answer key is looked up HERE from tasks_export.json and is never
//     delivered to the sandbox (nor is the task id) — a candidate that reads the
//     export or imports the refs to delegate finds neither (A2 parity, enforced
//     structurally by the sandbox's scrub dir);
//   * an infinite-loop candidate hangs the sandbox; this worker simply awaits, so
//     the parent (oracle/isolate.py) SIGKILLs the whole process group ->
//     TIMEOUT_KILLED, never a wedge.
//
// Speaks the exact run_isolated(lang="js") protocol oracle/isolate.py expects:
// reads {"task_id","source","sentinel"} JSON from stdin, writes ONE
// sentinel-framed verdict to stdout, exits immediately.
//
// Manual use (no sentinel -> plain JSON line, debugging only):
//   echo '{"task_id":"E2_iso_roundtrip","source":"..."}' | node oracle_js/isolate_worker.mjs
process.env.TZ = "UTC";   // ESM note: this file has NO static imports, so this runs first

const fs = await import("node:fs");
const { spawn } = await import("node:child_process");
const { fileURLToPath } = await import("node:url");
const { dirname, join } = await import("node:path");

const realExit = process.exit.bind(process);
const hardExit = (code) => {
  try { realExit(code); } catch { /* fall through */ }
  try { process.kill(process.pid, "SIGKILL"); } catch { /* unreachable */ }
};

async function main() {
  // ---- read the request ---- //
  const chunks = [];
  for await (const c of process.stdin) chunks.push(c);
  const req = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  const sentinel = req.sentinel;

  const here = dirname(fileURLToPath(import.meta.url));

  // ---- trusted machinery + the answer key (candidate never touches either) --- //
  const { classifyRows, result, verdictBody, jstr, LOAD_ERROR } =
    await import(new URL("./run_oracle.mjs", import.meta.url));
  const { fromCanon } = await import(new URL("./neutral.mjs", import.meta.url));
  const { writeFrame, makeFrameReader } =
    await import(new URL("./sandbox_runner.mjs", import.meta.url));

  const data = JSON.parse(fs.readFileSync(join(here, "tasks_export.json"), "utf8"));
  const taskRow = data.tasks.find((t) => t.id === req.task_id);
  if (!taskRow) {
    // Python twin: KeyError -> non-zero exit -> parent classifies WORKER_ERROR.
    process.stderr.write(`unknown task_id '${req.task_id}'\n`);
    hardExit(1);
  }

  // ---- spawn the untrusted sandbox ---- //
  // stdio: candidate stdin/stdout/stderr -> /dev/null (fd 1/2 cannot reach the
  // verdict channel); fd 3 = worker->sandbox requests, fd 4 = sandbox->worker
  // results. No `detached` -> the sandbox stays in this worker's process group,
  // so the parent's timeout killpg reaches it too.
  const sandbox = spawn(process.execPath, [join(here, "sandbox_runner.mjs")], {
    stdio: ["ignore", "ignore", "ignore", "pipe", "pipe"],
    env: { ...process.env, TZ: "UTC" },
  });
  const toSandbox = sandbox.stdio[3];         // worker writes -> sandbox fd 3
  const nextResp = makeFrameReader(sandbox.stdio[4]);
  sandbox.on("error", () => { /* surfaced as an EOF on the result channel below */ });

  // ---- load ---- //
  writeFrame(toSandbox, { cmd: "load", source: req.source, entry_point: taskRow.entry_point });
  const load = await nextResp();

  let r;
  if (!load || !load.loaded) {
    r = result(taskRow, LOAD_ERROR, false, false,
               { error: (load && load.error) || "sandbox failed to load candidate" });
  } else {
    // Same classification as in-process, but each candidate call runs in the
    // sandbox: the candidate output crosses back as canon, we rebuild it with
    // fromCanon and run the SAME weak-happy / strict-oracle comparators HERE.
    const runOneRemote = async (row, cmp) => {
      if (row.canon[0] === "raise") {
        return { refOk: false, matched: false, kind: "ref_raised",
                 note: `reference raised on ${jstr(row.args)}: ${row.canon[1]}` };
      }
      writeFrame(toSandbox, { cmd: "call", args: row.args });
      const resp = await nextResp();
      if (resp === null) throw new Error("sandbox closed during candidate call");  // -> WORKER_ERROR
      if (!resp.ok) {
        if (resp.kind === "unencodable") {              // out-of-domain value -> WRONG VALUE
          return { refOk: true, matched: false, kind: "mismatch",
                   note: `unencodable output on ${jstr(row.args)}: ${resp.error}` };
        }
        return { refOk: true, matched: false, kind: "cand_raised",  // latent crash
                 note: `candidate raised on ${jstr(row.args)}: ${resp.error}` };
      }
      const candOut = fromCanon(resp.canon);
      let ok;
      try {
        ok = cmp(row.canon, candOut);
      } catch (e) {
        return { refOk: true, matched: false, kind: "compare_raised",
                 note: `compare raised on ${jstr(row.args)}: ${e?.constructor?.name ?? "Error"}: ${e?.message ?? e}` };
      }
      if (ok) return { refOk: true, matched: true, kind: "match", note: "" };
      return { refOk: true, matched: false, kind: "mismatch",
               note: `diverged on ${jstr(row.args)}: ref_canon=${jstr(row.canon)} cand_canon=${jstr(resp.canon)}` };
    };
    r = await classifyRows(taskRow, runOneRemote);
  }

  // ---- tear the sandbox down ---- //
  try { writeFrame(toSandbox, { cmd: "stop" }); } catch { /* pipe already closed */ }
  try { sandbox.kill("SIGKILL"); } catch { /* already gone */ }

  // ---- framed verdict on the REAL stdout, then immediate exit ---- //
  // No stdout sealing is needed: this process never ran candidate code, so fd 1
  // was never exposed to it.
  const body = JSON.stringify(verdictBody(r));
  const line = sentinel ? `${sentinel}${body}${sentinel}\n` : `${body}\n`;
  fs.writeSync(1, line);
  hardExit(0);
}

main().catch((e) => {
  process.stderr.write(`worker crashed: ${e?.stack ?? e}\n`);
  hardExit(1);
});
