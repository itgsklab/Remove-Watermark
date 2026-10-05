# Task worker

Document editing and preview generation run outside the FastAPI process. `TaskService` owns one supervisor thread and a FIFO queue; the supervisor starts one Python `spawn` child process for each task, so document parsers and external preview commands cannot block request handling or share mutable API-process state.

## Lifecycle

1. The API validates the persisted plan and inserts a `queued` task.
2. The supervisor revalidates the plan and source digest, then marks the task `running`.
3. A child process creates the output and optional before/after preview files.
4. The child sends only result metadata through a bounded multiprocessing queue.
5. The supervisor validates the process outcome and persists artifact rows in SQLite.

Only one child runs at a time in this development version. Heavy image processing can later increase concurrency behind explicit CPU and memory limits without changing the HTTP task contract.

## Cancellation and failure

Cancellation first sets a process-safe event used by the document editors and preview subprocess loops. If the child does not exit within `WMRM_WORKER_CANCEL_GRACE_SECONDS`, the supervisor terminates it and removes partial task files. A child that exits without a result is recorded as `PROCESSING_FAILED` with its exit code.

Application shutdown asks the active child to stop and then terminates it after the same grace period. Its database row intentionally remains non-terminal. On the next startup, recovery removes partial files and stale artifact rows, revalidates the plan, and queues the task again. A task already in `cancelling` becomes `cancelled` during recovery.

## Process boundary

The child receives plain serializable values: source and destination paths, candidate snapshots, asset kind, and preview settings. It does not open the application database. The API process remains the only writer of task and artifact metadata.
