# Code-checked M2 launch note — 2026-10-27

The first server launch directory, `code_checked_m2_20261027`, was stopped
before any trial result was written. A PowerShell quoting error caused two
copies of the same runner to start in that same directory. Both processes were
our own (`2284779` and `2285604`) and were stopped at once; no shared process
or file was modified.

This directory is retained unchanged as an aborted-launch record and is not an
experimental result. The pre-registered manifest and frozen prompts are reused
without changes in a fresh, separately named server run directory.
