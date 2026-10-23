# Concrete scenarios for `openai_config` (interface)

## Scenario 1 — Reading the connection coordinates

Given: the system's openai config supplies the model name `widget-4o`, the base url
`https://models.example.test/v1`, and the api key `key-alpha-0001`.

1. The caller reads the model name of the openai config.
   Observed: `widget-4o`.

2. The caller reads the base url of the openai config.
   Observed: `https://models.example.test/v1`.

3. The caller reads the api key of the openai config.
   Observed: `key-alpha-0001`.

## Scenario 2 — Reading the request limits and sampling parameters

Given: the system's openai config supplies a timeout of 30 seconds, a temperature of 0.2, and a max
tokens upper bound of 4096.

1. The caller reads the timeout of the openai config.
   Observed: 30 seconds.

2. The caller reads the temperature of the openai config.
   Observed: 0.2.

3. The caller reads the max tokens upper bound of the openai config.
   Observed: 4096.

## Scenario 3 — Stable values across repeated reads

Given: the system's openai config supplies the model name `gadget-3`, a timeout of 90 seconds, and
a temperature of 0.7.

1. The caller reads the model name, the timeout, and the temperature twice in succession.
   Observed: both reads report `gadget-3`, 90 seconds, and 0.7, and the reads alter none of the
   supplied values.

## Scenario 4 — Coordinates recovered from a fresh openai config

Given: the same system configuration, supplying the model name `sprocket-2`, the base url
`https://widgets.example.test:8443/v1`, the api key `key-beta-0002`, a timeout of 15 seconds, a
temperature of 0.0, and a max tokens upper bound of 512, is used to build a fresh openai config.

1. The caller reads the model name of the fresh openai config.
   Observed: `sprocket-2`.

2. The caller reads the base url of the fresh openai config.
   Observed: `https://widgets.example.test:8443/v1`.

3. The caller reads the api key of the fresh openai config.
   Observed: `key-beta-0002`.

4. The caller reads the timeout of the fresh openai config.
   Observed: 15 seconds.

5. The caller reads the temperature of the fresh openai config.
   Observed: 0.0.

6. The caller reads the max tokens upper bound of the fresh openai config.
   Observed: 512.

## Scenario 5 — Coordinates and bounds that do not apply

Given: the system's openai config supplies the model name `widget-4o`, a timeout of 30 seconds, and
a temperature of 0.2, while custom endpoint routing does not apply, designated environment secrets
do not apply, and token generation is unconstrained.

1. The caller reads the base url of the openai config.
   Observed: no base url is reported.

2. The caller reads the api key of the openai config.
   Observed: no api key is reported.

3. The caller reads the max tokens upper bound of the openai config.
   Observed: no max tokens upper bound is reported.

## Scenario 6 — No openai config active

Given: no openai config is active for the caller.

1. The caller reads the model name.
   Observed: the read fails explicitly, and no model name is reported.

2. The caller reads the base url.
   Observed: the read fails explicitly, and no base url is reported.

3. The caller reads the timeout and the temperature.
   Observed: both reads fail explicitly, and neither the timeout nor the temperature is reported.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:12:26Z
CHANGE: Author openai openai_config concrete scenarios
-->
