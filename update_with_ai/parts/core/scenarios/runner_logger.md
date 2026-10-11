<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-11T22:09:02Z
LAST_CHANGED: 2026-10-11T03:09:09Z
CHANGE: Author core runner_logger concrete scenarios
CODE_HASH: 05d9a4512686
-->

# Concrete scenarios for `runner_logger` (interface)

## Scenario 1 — Consuming one execution event

Given: no events have been consumed yet and no transcript log exists; the caller holds a runner
log event named render_pass with the summary rendered widget in 12 milliseconds and a transcript
representation four lines long.

1. The caller consumes that event.
   Observed: standard output gains one single-line summary naming the event render_pass and
   carrying the text rendered widget in 12 milliseconds, and the transcript log gains a record
   whose text is the full four-line transcript representation of the event.

## Scenario 2 — Two events of the same kind

Given: no events have been consumed yet and no transcript log exists; the caller holds the runner
log events named evaluate with a summary of evaluated gadget and named evaluate with a summary of
evaluated sprocket.

1. The caller consumes the first event.
   Observed: standard output gains one single-line summary naming the event evaluate and carrying
   the text evaluated gadget, and the transcript log gains the transcript representation of the
   first event.

2. The caller consumes the second event.
   Observed: standard output gains one further single-line summary naming the event evaluate and
   carrying the text evaluated sprocket, and the transcript log gains the transcript
   representation of the second event as a record distinct from the record of step 1.

## Scenario 3 — A long run of events

Given: no events have been consumed yet and no transcript log exists; the caller holds 120 runner
log events whose names are pass_1 through pass_120, each with a distinct transcript
representation.

1. The caller consumes the 120 events, one after another in that order.
   Observed: standard output carries 120 single-line summaries in the order the events were
   consumed, and the transcript log carries all 120 verbose records in that same order without
   loss.

## Scenario 4 — An event with no summary text

Given: no events have been consumed yet and no transcript log exists; the caller holds a runner
log event named start_up whose summary is absent and whose transcript representation is two lines
long.

1. The caller consumes that event.
   Observed: standard output gains a summary line naming the event start_up, and the transcript
   log gains the full two-line transcript representation of the event.

## Scenario 5 — An event with an empty event name and an empty summary

Given: no events have been consumed yet and no transcript log exists; the caller holds a runner
log event whose event name is the empty string, whose summary is the empty string, and whose
transcript representation is the text nothing to report.

1. The caller consumes that event.
   Observed: standard output gains one single-line summary carrying the empty summary text with
   no event name, and the transcript log gains a record whose text is nothing to report.

## Scenario 6 — An event whose transcript spans many lines

Given: no events have been consumed yet and no transcript log exists; the caller holds a runner
log event named compile_pass whose summary is compiled widget in 8 seconds and whose transcript
representation is 500 lines long.

1. The caller consumes that event.
   Observed: standard output gains exactly one single-line summary naming the event compile_pass
   and carrying the text compiled widget in 8 seconds, and the transcript log gains one record
   whose text is all 500 lines of the transcript representation.
