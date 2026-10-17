<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-12T12:35:00Z
CHANGE: Update scenarios to reflect standard output carrying event summary text without timestamps or event names
CODE_HASH: 5da8d76d019e
-->

# Concrete scenarios for `logger_impl` (implementation)

Scenarios 1 through 6 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones
is what makes realizability structural: an implementation scenario that cannot name a realization
for its observation is a defect in the implementation rather than a gap in the set. Scenarios 7
through 11 cover behaviours the interface does not expose to a caller, and each of them is a
candidate for the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — Consuming one execution event

Given: no events have been consumed yet and no transcript log exists; the caller holds a runner
log event named render_pass with the summary rendered widget in 12 milliseconds and a transcript
representation four lines long.

1. The caller consumes that event.
   Observed: standard output gains one single-line summary carrying the text rendered widget in 12 milliseconds, and the transcript log gains a record
   whose text is the full four-line transcript representation of the event.
   Realized by: the component's own transcript log destination, opened before the first write;
   its own unbuffered write of the verbose transcript representation to
   the destination with an immediate flush after that write; and the component's own write of the
   summary line to standard output.

### Scenario 2 — Two events of the same kind

Given: no events have been consumed yet and no transcript log exists; the caller holds the runner
log events named evaluate with a summary of evaluated gadget and named evaluate with a summary of
evaluated sprocket.

1. The caller consumes the first event.
   Observed: standard output gains one single-line summary carrying the text evaluated gadget, and the transcript log gains the transcript representation of the
   first event.
   Realized by: the component's own standard output write of the summary text for the first
   event, and its own unbuffered write of that event's transcript representation to the
   destination with an immediate flush.

2. The caller consumes the second event.
   Observed: standard output gains one further single-line summary carrying the text evaluated sprocket, and the transcript log gains the transcript
   representation of the second event as a record distinct from the record of step 1.
   Realized by: the same destination held open by the component, its standard output write of the summary text for the second event, and its own unbuffered write with an immediate
   flush that leaves the record of step 1 in place.

### Scenario 3 — A long run of events

Given: no events have been consumed yet and no transcript log exists; the caller holds 120 runner
log events whose names are pass_1 through pass_120, each with a distinct transcript
representation.

1. The caller consumes the 120 events, one after another in that order.
   Observed: standard output carries 120 single-line summaries in the order the events were
   consumed, and the transcript log carries all 120 verbose records in that same order without
   loss.
   Realized by: the component's own single destination held open across the session, its standard output write of the summary text per event, and its own unbuffered write of each verbose record with an immediate
   flush after every write, so no record waits in a buffer.

### Scenario 4 — An event with no summary text

Given: no events have been consumed yet and no transcript log exists; the caller holds a runner
log event named start_up whose summary is absent and whose transcript representation is two lines
long.

1. The caller consumes that event.
   Observed: standard output gains an empty summary line, and the transcript
   log gains the full two-line transcript representation of the event.
   Realized by: the component's own write of the summary text to standard output, and its own unbuffered write of the
   verbose representation with an immediate flush.

### Scenario 5 — An event with an empty event name and an empty summary

Given: no events have been consumed yet and no transcript log exists; the caller holds a runner
log event whose event name is the empty string, whose summary is the empty string, and whose
transcript representation is the text nothing to report.

1. The caller consumes that event.
   Observed: standard output gains one single-line summary carrying the empty summary text with
   no event name, and the transcript log gains a record whose text is nothing to report.
   Realized by: the component's own formatting of the summary line from whatever strings the
   event supplies, and its own unbuffered write of the transcript representation with an
   immediate flush.

### Scenario 6 — An event whose transcript spans many lines

Given: no events have been consumed yet and no transcript log exists; the caller holds a runner
log event named compile_pass whose summary is compiled widget in 8 seconds and whose transcript
representation is 500 lines long.

1. The caller consumes that event.
   Observed: standard output gains exactly one single-line summary carrying the text compiled widget in 8 seconds, and the transcript log gains one record
   whose text is all 500 lines of the transcript representation.
   Realized by: the component's own summary formatting, which keeps the standard output line to
   one line whatever the transcript representation holds, and its own unbuffered write of all 500
   lines with an immediate flush.

## Implementation-only

### Scenario 7 — No transcript destination configured

Given: no destination variable is configured in the environment, and the caller holds a runner
log event named render_pass with a transcript representation four lines long.

1. The caller consumes that event.
   Observed: the transcript log is the file agent_loop.log in the working directory, and it gains
   a record whose text is the full four-line transcript representation of the event.
   Realized by: the component's own destination resolution, which falls back to the default
   agent_loop.log when the environment configures no destination.

### Scenario 8 — A transcript destination configured in the environment

Given: the environment configures the destination variable as /tmp/alpha_session.log, and the
caller holds a runner log event named render_pass with a transcript representation four lines
long.

1. The caller consumes that event.
   Observed: the transcript is written to /tmp/alpha_session.log, which gains a record whose text
   is the full four-line transcript representation of the event, and no agent_loop.log is
   created.
   Realized by: the component's own destination resolution, which reads the configured environment
   variable and opens the location it names in place of the default.

### Scenario 9 — The destination variable present but empty

Given: the environment presents the destination variable with an empty value, and the caller
holds a runner log event named render_pass with a transcript representation four lines long.

1. The caller consumes that event.
   Observed: the transcript log is the file agent_loop.log in the working directory, and it gains
   a record whose text is the full four-line transcript representation of the event.
   Realized by: the component's own destination resolution, which treats an empty configured value
   as no destination configured and falls back to agent_loop.log.

### Scenario 10 — The destination file does not exist yet

Given: no file exists at agent_loop.log and no directory within the working directory holds a
transcript for this session, and the caller holds a runner log event named prepare with a
transcript representation two lines long.

1. The caller consumes that event.
   Observed: agent_loop.log exists and gains the two-line transcript representation of the event,
   without the caller having created the file.
   Realized by: the component's own opening of the transcript destination, which creates the log
   file when it is absent.

### Scenario 11 — A transcript left by an earlier execution

Given: agent_loop.log already holds three records left by an earlier execution, the current
execution has consumed no events yet, and the caller holds a runner log event named finish with a
transcript representation one line long.

1. The caller consumes that event.
   Observed: agent_loop.log holds one record whose text is the one-line transcript representation
   of finish, and the three records of the earlier execution are gone.
   Realized by: the component's own truncation of the transcript log at opening, which starts
   every execution session with a clean transcript.
