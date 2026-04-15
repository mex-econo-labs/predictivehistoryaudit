#!/usr/bin/env python3
"""Append one structured JSON line to the pipeline log per phase transition.

Called from analyze.sh (and peer scripts) to record who invoked the pipeline,
what it did, and how it ended. Every invocation and every phase transition
appends one JSON record. Queried with `jq` or grep.

Record shape:
  ts            : ISO 8601 local time with offset
  run_id        : uuid unique to one script invocation; joins all phases
  phase         : start | transcript | metadata | claude_done |
                  screencaps | built | committed | pushed | exit | warn
  host, user    : where it ran and as whom
  tty           : controlling terminal or 'notty'
  pid, ppid     : process and parent ids
  ancestry      : chain up to init of (pid:comm:cmdline), 80 chars of cmdline
                  each — enough to identify claude, cron, ssh, tmux as the
                  invoking shell without reading /proc later
  cwd           : working dir at the time of the phase
  argv          : the full command line of the pipeline script itself
  ssh           : SSH_CONNECTION if present (forwarded ssh info)
  claude_session: CLAUDE_SESSION_ID / CLAUDE_CODE_SESSION_ID env var if set
  (extras)      : any additional key=value passed on the cli, merged in

Usage:
  log-pipeline.py --run-id $RUN_ID --phase start \\
                  --log-file analysis/pipeline.log \\
                  argv="$0 $*" url="$URL"

Designed to never fail the caller: errors are swallowed after a best-effort
write attempt so the pipeline isn't killed by a logging hiccup.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys


def ancestry(start_pid: int, max_depth: int = 10) -> list[str]:
    """Return parent-process chain as list of 'pid:comm:cmdline[:80]' strings."""
    chain = []
    pid = start_pid
    for _ in range(max_depth):
        try:
            with open(f'/proc/{pid}/status') as f:
                ppid = None
                for line in f:
                    if line.startswith('PPid:'):
                        ppid = int(line.split()[1])
                        break
            if not ppid or ppid <= 1:
                break
            try:
                with open(f'/proc/{ppid}/comm') as f:
                    comm = f.read().strip()
            except FileNotFoundError:
                comm = '?'
            try:
                with open(f'/proc/{ppid}/cmdline') as f:
                    cmdline = f.read().replace('\0', ' ').strip()[:80]
            except FileNotFoundError:
                cmdline = ''
            chain.append(f'{ppid}:{comm}:{cmdline}')
            pid = ppid
        except Exception:
            break
    return chain


def current_tty() -> str:
    try:
        r = subprocess.run(['tty'], capture_output=True, text=True, timeout=2,
                           stdin=subprocess.DEVNULL)
        out = r.stdout.strip()
        return out if out else 'notty'
    except Exception:
        return 'notty'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run-id', required=True,
                    help='Shared id across all phases of one invocation')
    ap.add_argument('--phase', required=True,
                    help='start | transcript | metadata | claude_done | '
                         'screencaps | built | committed | pushed | exit | warn')
    ap.add_argument('--log-file', required=True,
                    help='Path to pipeline.log (appended, JSONL)')
    ap.add_argument('kv', nargs='*',
                    help='Extra fields as key=value, merged into record')
    args = ap.parse_args()

    pid = os.getpid()
    ppid = os.getppid()
    rec = {
        'ts': datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
        'run_id': args.run_id,
        'phase': args.phase,
        'host': os.uname().nodename,
        'user': os.environ.get('USER') or os.environ.get('LOGNAME') or '?',
        'tty': current_tty(),
        'pid': pid,
        'ppid': ppid,
        'ancestry': ancestry(pid),
        'cwd': os.getcwd(),
        'ssh': os.environ.get('SSH_CONNECTION', ''),
        'claude_session': (os.environ.get('CLAUDE_SESSION_ID')
                           or os.environ.get('CLAUDE_CODE_SESSION_ID')
                           or ''),
    }
    for kv in args.kv:
        if '=' in kv:
            k, v = kv.split('=', 1)
            rec[k] = v

    try:
        os.makedirs(os.path.dirname(args.log_file) or '.', exist_ok=True)
        with open(args.log_file, 'a') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    except Exception as e:
        # Never propagate — logging must not kill the pipeline
        print(f'log-pipeline: warning: {e}', file=sys.stderr)


if __name__ == '__main__':
    main()
