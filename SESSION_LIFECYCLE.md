# Session Lifecycle

_Last reviewed: 2026-04-26_

This document describes the session lifecycle FSM that gates
recording, finalization, and review of a telemetry session.
The state machine is implemented in
`src/lap_coach_logger/core/session_state.py` and driven by the
`SessionCoordinator` in
`src/lap_coach_logger/core/session_coordinator.py`.

## 1. Why a state machine

A session has many failure modes — sim disconnects, paused
games, finalization crashes, unexpected mid-session resets —
and the recording pipeline must respond consistently. A
formal FSM:

- gives every component (UI, writer, watcher, finalizer) one
  authoritative answer to "what is the system doing right
  now?"
- forbids invalid transitions (e.g. `recording → idle`) so
  bugs surface as a logged warning rather than data loss
- produces an audit trail (`transition_history`) that is
  attached to every saved session bundle

The state machine is backed by the [`transitions`][1]
library; the public API is preserved so callers still see
plain Python enums.

[1]: https://github.com/pytransitions/transitions

## 2. States

There are eight states, all members of the `SessionState`
enum:

| State | Meaning |
|-------|---------|
| `idle` | No simulator detected. The watcher is polling, but no telemetry pipeline is running. |
| `simulator_detected` | A sim adapter has started returning data, but the in-game session has not yet entered a recordable phase (e.g. main menu). |
| `waiting_for_valid_session` | The sim is up and the adapter has handshaked, but the live session metadata (track, car, session type) is incomplete or pending. |
| `arming` | The session metadata is sufficient and we are about to start writing samples — we hold here for a tick to seed buffers and verify the dashboard is in a recordable state. |
| `recording` | Samples are being captured and buffered for the writer pipeline. |
| `finalizing` | Recording has stopped; the writer is flushing buffered samples to disk and computing per-session metrics, lap analysis, and quality reports. |
| `ready_for_review` | Finalization succeeded. The bundle is written and visible in the History page. |
| `failed` | A non-recoverable error happened (sim crashed mid-recording, finalize threw, disk full, …). The user is shown a recovery dialog. |

## 3. Transition graph

```
idle → simulator_detected

simulator_detected → waiting_for_valid_session
simulator_detected → idle
simulator_detected → failed

waiting_for_valid_session → arming
waiting_for_valid_session → idle
waiting_for_valid_session → failed

arming → recording
arming → finalizing
arming → idle
arming → failed

recording → finalizing
recording → failed

finalizing → ready_for_review
finalizing → failed

ready_for_review → waiting_for_valid_session
ready_for_review → idle

failed → finalizing
failed → ready_for_review
failed → idle
```

The set of allowed edges is declared explicitly in
`_TRANSITIONS` in `session_state.py` and enforced by the
`transitions.Machine` (`ignore_invalid_triggers=True`); an
invalid attempt is logged as a warning and the state stays
unchanged.

## 4. Notable transitions

- **`recording → finalizing`** is the happy path. Triggered by
  the watcher detecting that the sim has left the session
  (e.g. car returned to garage, race ended, sim closed).
- **`arming → finalizing`** handles the tiny-session case
  where the user backs out before any meaningful samples
  arrive — we still finalize so any partial buffer is flushed
  cleanly.
- **`failed → finalizing`** lets us salvage as much of a
  bad-end session as possible: even on a sim crash, whatever
  samples are buffered get written so the user keeps their
  laps.
- **`failed → ready_for_review`** is for failures that happen
  *after* the bundle has already been written (e.g. quality
  validation fails) — the data is on disk, so we let the user
  open it.
- **`ready_for_review → waiting_for_valid_session`** is the
  back-to-back-session path. The user finishes one outing,
  reviews, and the sim launches a new session without
  closing — we re-arm without bouncing through `idle`.

## 5. Audit trail

Every transition records a `TransitionEntry` with:

- `timestamp_utc`
- `previous_state`
- `new_state`
- `reason` — short string explaining the transition
- `event` — optional event name for log correlation

The full history is exposed as
`SessionStateMachine.transition_history` and is captured by
the finalizer so each saved session bundle contains its own
state-machine timeline. This is the single source of truth
when a user asks "what happened with this session?".

## 6. Drift prevention

`tests/test_session_lifecycle_doc.py` pins the doc -> code
contract: every state value, every allowed transition, and
the freshness marker must appear here. Adding a new state or
edge to `session_state.py` without updating this doc fails
CI, so the prose can't silently age out of the FSM.
