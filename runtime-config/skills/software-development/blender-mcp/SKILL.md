---
name: blender-mcp
description: "Control Blender via MCP with project protection."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [blender, mcp, animation, rendering, safety]
---

# Blender MCP

## When to Use

Use for Blender MCP installation, diagnostics, connection recovery, and tool-driven scene work. Load before changing or rendering a Blender scene.

## Scope and routing

Use native MCP tools, not merely generated Python text. Main/default handles integration and diagnostics. By default creative design routes to `design.route`. Exception: on an explicit user request for direct Blender work in Main, use registered action `blender.direct` and execute here, loading cinedance, acting-system and lira-image-prompts with their required references. The design profile also has this MCP configured with user permission. Do not bypass isolation or change other profiles. Only one profile may mutate the scene at a time; do not delegate concurrent writers.

## Installed capability

- `mcp-for-blender==2.1.9`, installed via `uv tool install --python 3.11`; executable `/home/vottak/.local/bin/mcp-for-blender`. Internal module `blender_mcp` is upstream naming, not the obsolete PyPI package.
- Blender: `/home/vottak/.local/opt/blender-5.2.2-linux-x64/blender`.
- Addon: `/home/vottak/.config/blender/5.2/scripts/addons/blender_mcp.py`.
- Dedicated workspace: `/home/vottak/Blender-AI`.
- User service: `blender-ai.service`; desktop launcher `Blender AI (Hermes MCP)`.
- Agent connects only to `127.0.0.1:9877`; normal Blender's port 9876 is NOT its target.
- Default and design expose `get_addon_status`, `get_scene_info`, `execute_blender_code`, `look`; prompts/resources wrappers disabled. Progressive disclosure hides full schemas until tool_describe; lazy:true delays server startup after schema caching.
- `BLENDER_MCP_SAFE_MODE=1`, `DISABLE_TELEMETRY=true`, sampling disabled. No paid generators or remote asset integrations enabled. Do not enable or buy anything without approval and budget.

## Start and connect

1. `systemctl --user start blender-ai.service`, then `systemctl --user show blender-ai.service -p ActiveState -p SubState -p MainPID`. Starting an active service does not reset its scene; no sudo.
2. Find Blender tools with tool_search, load schemas via tool_describe, then tool_call. Exposed names follow `mcp__blender__...`; do not guess prefixes.
3. Call get_addon_status once, then get_scene_info with fields settings/materials/animation. Verify addon version and disabled generators.
4. Start every execute_blender_code call with `import bpy`; globals do not persist across calls. Do not import os or subprocess in safe mode. A rejected script must be rewritten within safe-mode limits, not treated as a broken connection. Use bpy/bmesh/mathutils for objects, materials, cameras, keyframes and rendering. Pass the user's goal verbatim in user_prompt.
5. Before every mutating batch, verify `bpy.context.scene.get('hermes_ai_workspace') == '/home/vottak/Blender-AI'` and `bpy.context.scene.blendermcp_port == 9877`. Stop on mismatch. Read the port via the registered RNA attribute (`getattr(scene, 'blendermcp_port', None)`), NOT `scene.get('blendermcp_port')`: the latter reads custom ID properties and can return None while the real configured port is 9877.
6. Serialize Blender MCP calls: do not issue concurrent status/code calls against the same socket. On a handshake connection-close error, retry read-only status once sequentially before diagnosing a broken installation or updating the addon.

## Project protection

- Never clear an arbitrary scene or modify an existing project merely because the port connects.
- New work gets a unique name/subdirectory under `/home/vottak/Blender-AI`. Check output paths with filesystem tools before writing. Do not overwrite integration tests or existing files.
- If the scene contains work, save a checkpoint to a NEW unique path before edits. Blender save-as copy=True permits a non-switching checkpoint. Existing user projects require an explicit target and a separate working copy; never overwrite the source.
- Startup is a fresh factory scene, never an automatically opened existing user project. Opening an approved working copy is a separate action.
- Workspace has save versions=3 and temporary autosave enabled. These do not replace checkpoints. Restart does NOT automatically recover unsaved work; inspect recovery files and ask before replacing anything.
- Safe mode is a code validator, NOT a sandbox or path allowlist. Saving/render/export remain allowed, so verify paths yourself. The addon socket has no authentication: never expose it beyond localhost.

## Direct Blender acceptance order

Inspect existing objects through get_scene_info before changes. Save a unique checkpoint. Fix static geometry, seated proportions, inward body orientation and chair alignment before animation; use look camera and angles to visually approve composition. Then create keyframes and use look frames at 1, 24, 48, 72, 96 and the final frame. Correct individual objects instead of recreating the whole scene. Use meaningful names and collections. Preserve card identities and hand contact. Deliver saved blend, playable preview and review images, and never claim completion on code execution alone.

## Verification and rendering

- Use small bounded batches; print names, filepath and frame values. Read back changes through MCP.
- Begin with 640x480 previews and modest samples/threads on this integrated-GPU laptop. Cycles CPU works; Eevee is another option. Heavy architecture renders are not guaranteed fast.
- Save .blend before long rendering. Render with `bpy.ops.render.render(write_still=True)` to a unique path; individual MCP calls time out after 300s. After timeout inspect running state before retrying; do not duplicate uncertain writes.
- Verify saved files and scene state, then visually inspect PNG through look(image=...) or vision_analyze. Deliver absolute paths in CLI, not MEDIA tags.
- Verify animation at two frames, then restore the intended frame; an Action alone is insufficient evidence.

## Restart and failure handling

- Addon auto-starts on GUI launch/load; service sets port9877 before GUI timers. Restart=on-failure recovers crashes, not normal closes. Service is NOT enabled at login; start on demand.
- Existing MCP reconnects after Blender restart. One read-only retry may be needed after a stale socket; never blindly repeat mutations.
- If Blender is closed, start the service; do not run another MCP server manually.
- Missing tools in an existing chat: `/reload-mcp` or new session. `hermes mcp test blender` prints raw upstream discovery, not the effective include filter.
- If the Python3.11 package imports Hermes Python3.14 libraries, remove inherited PYTHONPATH/PYTHONHOME for that subprocess, not install extra dependencies. Native MCP filters these already.
- Use manage_connections for catalog/current connections, official `hermes mcp add` / `hermes config set` for custom entries. Backup configs first; preserve unrelated settings and the existing defer list.

## References

https://github.com/ahujasid/mcp-for-blender
https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp
