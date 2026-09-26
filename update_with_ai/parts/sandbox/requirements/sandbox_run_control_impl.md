# sandbox_run_control_impl implementation component

imports: tool_provider, agent_file_alias, dag_storage, sandbox_file_editor, sandbox_guide_delivery, agent_node_config, template_format, agent_config, dag_subgraph, sandbox
implements: sandbox_run_control

## Assumptions and Requirements

### Requirements

1. Tools cannot be configured against non-role/agent-specific state; the run controller installs submit, fail, check files, get work, and blame tools unconditionally, and installs advance tool when guide step mode is active.
2. Verification results are cached alongside edit manager file hashes for target nodes and reused when file hashes have not changed.
3. The check files tool is named check_files, accepts no parameters, and shares constant suppression key check_files.
4. Executing check files tool updates verification results if outdated, evaluates verification checks across open targets and modified files, and reminds the agent that no new information will be revealed until files are updated when hashes are unchanged.
5. Check files tool fails when verification fails, presenting sanitized diagnostic feedback and verification failure instructions.
6. Check files tool produces passing results using configured success message or default passing results alongside sanitized output.
7. The advance tool is named advance, accepts no parameters, and shares constant suppression key advance.
8. Executing advance tool delivers initial guide summary without updating verification when guide delivery has not started.
9. Advance tool fails when verification has not been evaluated for the current workspace files or is failing, specifying follow-up execution of check files tool.
10. Advance tool advances guide delivery when verification passes and steps remain.
11. Advance tool fails with reminder to call submit tool with change summary when verification passes, no steps remain, and files were modified.
12. Advance tool specifies follow-up submit tool without change summary when verification passes, no steps remain, and files were not modified.
13. Resolve tools match resolve target parameter against open active nodes, defaulting to single read-write file or last read/written path when omitted.
14. Resolve tools fail when resolve target cannot be resolved or does not match an open active node.
15. Resolve tools fail when in-batch dependency of resolve target is not clean.
16. Resolve tools lock resolve target read-write files against subsequent modification.
17. The submit tool is named submit, accepts resolve target and change summary parameters.
18. Submit tool fails when verification is failing, specifying follow-up check files tool.
19. Submit tool fails when guide steps remain, specifying follow-up advance tool.
20. Submit tool fails when an initial implementation change is assigned and no workspace files were modified.
21. Submit tool fails when workspace files were modified and change summary is omitted.
22. Submit tool marks resolve target clean on success and produces non-terminating response if active nodes remain or terminating response if all nodes are resolved.
23. The fail tool is named fail, accepts resolve target and explanation parameters, failing the target and marking in-batch dependents failed.
24. The blame tool is named blame, accepts resolve target, blame target, and explanation parameters, attributing failure to upstream node.
25. The get work tool is named get_work, accepts max batch size parameter, retrieves ready dirty nodes, initializes guide delivery, materializes startup templates, delivers session task prompt, and specifies a follow-up execution of the advance tool when the guide is in step mode.

## Grounding Facts

### Knowledge Needed

- Mode flags from `agent_config` (`step_mode`).
- Active nodes and blame targets from `agent_node_config`.
- Verification checks from `sandbox_run_control`.
- Cached file hashes and modification status from `sandbox_file_editor`.
- Guide steps and remaining status from `sandbox_guide_delivery`.

### Actions Needed

- Register and dispatch `check_files`, `advance`, `submit`, `fail`, `blame`, and `get_work` tools.
- Evaluate verification checks and cache outcome by file hash.
- Progress guide steps via `sandbox_guide_delivery`.
- Lock resolved files on `sandbox_file_editor`.
- Mark target nodes clean, failed, or blamed.
