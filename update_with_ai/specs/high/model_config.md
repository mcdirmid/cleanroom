# model_config interface component

## Purpose

The model_config interface component defines execution settings and model parameters governing agent session runs.

Language model interactions require explicit connection coordinates, authorization credentials, network timeouts, and turn limits. Centralizing these operational parameters into an ambient system service eliminates fragmented configuration channels across invocation layers and ensures uniform execution boundaries throughout the system.

**Out of scope:** The model_config interface component does not transmit network requests, parse build target syntax, or enforce turn execution loops; these are handled by other components.

## Types and Behavior

A *conversation limit* is a bound on the maximum number of model interaction turns permitted in an agent run.

The *model config* is a system service that provides execution parameters for language model agent runs. The model config provides:

- A *model name* designating the target model.

- A *base url* designating the remote model API endpoint address, or absent if default address resolution applies.

- An *api key* providing authentication credentials, or absent if ambient environment credentials apply.

- A *timeout* specifying the maximum duration in seconds permitted for a model request.

- The conversation limit bounding interaction turns.

- A *temperature* specifying the sampling temperature for model requests.

- A *max tokens* upper bound specifying the maximum number of response tokens permitted per request, or absent if unconstrained.

- Whether the agent should use *step mode* to communicate a guide to the agent progressively.

- Whether the agent should perform *startup reads* to inspect declared files at session start.
