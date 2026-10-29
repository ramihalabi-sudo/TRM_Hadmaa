"""Run the test modules in parallel processes (same tests as `python -m unittest discover -s tests`).

    python tests/run_parallel.py            all modules, cores - 1 processes (TRM4_TEST_JOBS overrides)
    python tests/run_parallel.py -j 4       4 processes
    python tests/run_parallel.py extensions metrics    only test_extensions.py and test_metrics.py

Each module runs in its own `python -m unittest` process, the longest first; the exit code is non-zero if any
module fails.  The model analyses inside the tests run with one pool worker (TRM4_WORKERS=1), except the
advisor / report modules (POOLED), so the modules do not oversubscribe the machine.
"""
import argparse
import glob
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
# longest modules first (measured on 12 cores), so the slowest one does not start last
SLOW_FIRST = ("test_advisor", "test_extensions", "test_metrics", "test_report_he", "test_analysis",
              "test_analysis_scope", "test_research_review", "test_invariants", "test_performance")
# modules dominated by model runs in a process pool keep a few workers of their own
POOLED = {"test_advisor": 4, "test_report_he": 2}


def run_module(mod):
    t0 = time.time()
    env = dict(os.environ, TRM4_WORKERS=str(POOLED.get(mod, 1)), PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, "-m", "unittest", mod], cwd=HERE, env=env, stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                       errors="replace")
    return mod, p.returncode, time.time() - t0, p.stdout


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-j", "--jobs", type=int, default=int(os.environ.get("TRM4_TEST_JOBS", 0)) or
                    max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("only", nargs="*", help="module names without the test_ prefix")
    a = ap.parse_args()
    mods = sorted(os.path.basename(f)[:-3] for f in glob.glob(os.path.join(HERE, "test_*.py")))
    if a.only:
        mods = [m for m in mods if m[5:] in a.only or m in a.only]
    mods.sort(key=lambda m: SLOW_FIRST.index(m) if m in SLOW_FIRST else len(SLOW_FIRST))
    t0 = time.time()
    failed = []
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for mod, code, dt, out in ex.map(run_module, mods):
            tail = [ln for ln in out.strip().splitlines() if ln.startswith(("Ran ", "OK", "FAILED"))]
            print("%-32s %6.1f s  %s" % (mod, dt, " ".join(tail[-2:]) if tail else "no result"), flush=True)
            if code != 0:
                failed.append((mod, out))
    for mod, out in failed:
        print("\n" + "=" * 70 + "\n" + mod + "\n" + "=" * 70 + "\n" + out)
    print("\n%d modules, %d failed, %.0f s wall time with %d processes" % (len(mods), len(failed), time.time() - t0,
                                                                           a.jobs))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
