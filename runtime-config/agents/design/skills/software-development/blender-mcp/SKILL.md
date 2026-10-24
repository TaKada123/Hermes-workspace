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

Use native MCP tools, not merely generated Python text. Main/default handles integration and diagnostics. Creative design stays behind the existing `design.route` handoff; the design profile also has this MCP configured with user permission. Do not bypass isolation or change other profiles. Only one profile may mutate the scene at a time; do not delegate concurrent writers.

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
4. Every execute_blender_code call must start with `import bpy`; globals from previous calls do NOT persist. Do not import os, pathlib, subprocess, socket, or use filesystem probes inside Blender safe mode. A rejected script is a code error to rewrite, not evidence of a disconnected Blender. Use the exact minimal preflight: `import bpy; print(bpy.context.scene.get('hermes_ai_workspace')); print(bpy.context.scene.blendermcp_port); print(bpy.data.filepath)`. After this succeeds, proceed with the authorized fixes, do not ask the user to reconnect. bpy/bmesh/mathutils support objects, modifiers, materials, lights, cameras, keyframes and rendering. Pass the user's goal verbatim in user_prompt.
5. Before every mutating batch, verify `bpy.context.scene.get('hermes_ai_workspace') == '/home/vottak/Blender-AI'` and `getattr(bpy.context.scene, 'blendermcp_port', None) == 9877`. Stop on a real mismatch. NEVER check the port using `scene.get('blendermcp_port')`: this reads custom ID properties, not the registered RNA setting, and can return None even when the actual port is correctly 9877. Do not ask the user to reconnect based on that false negative.
6. Serialize Blender MCP calls. If handshake fails with connection closed, retry read-only status once sequentially before diagnosing installation failure.
7. When the user asks for an animation, produce and verify a real animated .blend and a playable rendered preview, not merely a prompt. Preserve the full supplied choreography; choose sensible card identities consistent with the game rules if unspecified. If only one attachment is available, inspect it and follow the explicit text for missing staging rather than inventing a second reference.

## Project protection

- Never clear an arbitrary scene or modify an existing project merely because the port connects.
- New work gets a unique name/subdirectory under `/home/vottak/Blender-AI`. Check output paths with filesystem tools before writing. Do not overwrite integration tests or existing files.
- If the scene contains work, save a checkpoint to a NEW unique path before edits. Blender save-as copy=True permits a non-switching checkpoint. Existing user projects require an explicit target and a separate working copy; never overwrite the source.
- Startup is a fresh factory scene, never an automatically opened existing user project. Opening an approved working copy is a separate action.
- Workspace has save versions=3 and temporary autosave enabled. These do not replace checkpoints. Restart does NOT automatically recover unsaved work; inspect recovery files and ask before replacing anything.
- Safe mode is a code validator, NOT a sandbox or path allowlist. Saving/render/export remain allowed, so verify paths yourself. The addon socket has no authentication: never expose it beyond localhost.

## Corrective work on an existing scene

When the user asks to fix a visible defect, actually edit the approved working scene; merely inspecting existing actions is not completion. Make a unique checkpoint first. Use the newest attached screenshot as evidence of defects, not automatically as a desired reference. For seated card players, inspect world bounds: seat under pelvis, feet supported, torso and shoulders above the tabletop, tabletop approximately at seated elbow height, hands able to reach the playing surface. Correct the static staging before adjusting animation. After changes, render and inspect a camera image and multiple animation frames. Do not stop after identifying a fixable defect or describing what should be done. If slow full rendering is the only issue, deliver a fast material-color Workbench animation preview plus the saved working blend. Print exact output paths and actual checks.

## Verification and rendering

- Use small bounded batches; print names, filepath and frame values. Read back changes through MCP.
- Begin with 640x480 previews and modest samples/threads on this integrated-GPU laptop. Cycles CPU works; Eevee is another option. Heavy architecture renders are not guaranteed fast.
- Save .blend before long rendering. Render with `bpy.ops.render.render(write_still=True)` to a unique path; individual MCP calls time out after 300s. After timeout inspect running state before retrying; do not duplicate uncertain writes.
- Verify saved files and scene state, then visually inspect PNG through look(image=...) or vision_analyze. Deliver absolute paths in CLI, not MEDIA tags.
- Verify animation at two frames, then restore the intended frame; an Action alone is insufficient evidence.
- Do not deliver a gray clay blockout when the brief requires colored players and a wooden table. For Cycles/EEVEE set node-based Principled BSDF Base Color, not only material.diffuse_color; visually verify a rendered frame, not only solid viewport.
- Validate card-to-hand contact throughout each transfer, arm joint continuity, and card contact with the tabletop after placement. Rank/suit labels must follow the animated card (parent or equivalent); no floating, unlabelled, submerged, or pre-placed defense cards. Respect each stated time window.
- If resuming an incomplete project in the workspace, inspect it and save a unique checkpoint before fixing it. Finish the requested playable video, not only one PNG. Use a modest Workbench material-color preview render if full shaded animation is too slow, but label preview quality honestly.
- Blender 5 may lack FFMPEG as a render file format. This is not a video-export blocker: render a PNG sequence to a unique project subdirectory, then use the system ffmpeg executable to encode H.264 MP4 (`ffmpeg -framerate 30 -i frame_%04d.png -c:v libx264 -pix_fmt yuv420p output.mp4`), and verify via ffprobe. Use bounded low-resolution Workbench rendering for a fast first playable preview.
- Do not finalize with known below-table card trajectories or broken hand contact; fix and re-check them first. Derive safe card heights from actual tabletop world bounding box, start defense cards at the red player's hand above the table, and keep ranks/suits parented to card geometry.

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
