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

## Seated geometry and animation pitfalls

- Establish one inward forward vector per player and derive the perpendicular side axis. Place hips, knees, feet, arms, seat, backrest and chair legs in that same basis; rotating torso meshes alone leaves knees and chairs facing outward.
- Build arm segments from shared shoulder/elbow/hand endpoints. Animate all connected segments together; isolated hand keyframes produce floating hands.
- Check pose again after `scene.frame_set`: existing actions overwrite manually assigned transforms. Preserve old actions in a checkpoint, then detach or replace deliberately before static rebuilding.
- Blender 5.2 layered actions expose curves through `action.layers -> layer.strips -> strip.channelbag(object.animation_data.action_slot).fcurves`, not `action.fcurves`.
- When changing a parent's scale or local geometry, explicitly reset child text transforms and compensate parent scale; otherwise card labels shrink, skew or move off the card.
- Validate unique playing-card identities: the exposed trump cannot also appear in another player's hand.
- Serialize every MCP call, including look calls. Never batch calls on the same Blender socket concurrently.

## Interaction acceptance

- Do not accept a character/prop interaction based only on zero wrist-target error. Inspect the actual pose in close side/three-quarter viewport views and through the production camera, including pickup, release and body-turn transitions. A mathematically reachable target can still drive an elbow or prop through the torso.
- Select the holding hand from the target's position in the character's local frame. Keep a carried prop in a consistent front/side workspace during root turns rather than linearly interpolating unrelated world-space poses across the chest. Bias the elbow pole outward AND downward for a low pan-carrying pose; an outward-only pole can create a high-elbow, hanging-forearm pose. Sample both arm segments and the full prop/handle sweep against torso volume over the whole motion.
- For telescopes and similar optics, verify both eye position at the outside lip of the eyecup and the world-space gaze direction along the optical axis. Position alone is insufficient. Use the model's actual face-forward axis (e.g. local -Y), compensate parent/root rotations, and withdraw the eye before tilting the instrument. Raise/extend the instrument mount when needed instead of folding the neck into the chest.
- Save after each substantial successful mutation, before lengthy review/QA. Persist diagnostic reports in scene properties before assertions, because a raised MCP exception can hide prior stdout. After a power loss, inspect saved files/recovery candidates and open the approved last working file; do not assume the former live process or its final unsaved polish survived.

## Verification and rendering

- Honor explicit no-render instructions literally: do not use `bpy.ops.render.*`, `bpy.ops.render.opengl`, or assume `look(mode='camera'/'frames')` is non-rendering. For strict viewport-only review, set `scene.frame_set(f)`, update the view layer, call `bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)` to redraw the existing SOLID viewport, then `bpy.ops.screen.screenshot(filepath=...)`. This is a real window screenshot, not a scene render. Batched frame/redraw/screenshot loops work. Inspect the saved images with vision_analyze. A pre-existing Render Result can belong to an earlier project and does not prove a new render occurred.
- For camera-only crops of real screenshots without bpy_extras, project `camera.data.view_frame(scene=scene)` corners through `region_3d.perspective_matrix @ (camera.matrix_world @ corner).to_4d()`, divide by w, map to the WINDOW region rectangle, and invert Y using the window height. Crop the PNG outside Blender. Keep originals and programmatically verify requested frame counts.
- Safe mode also rejects imports from `bpy_extras` and creation of `bpy.data.texts` (an execution path). Store non-code project notes in scene custom properties or external documentation; do not disable safe mode to add a README. Use mathutils matrices directly for projection.
- Use small bounded batches; print names, filepath and frame values. Read back changes through MCP.
- Begin with 640x480 previews and modest samples/threads on this integrated-GPU laptop. Cycles CPU works; Eevee is another option. Heavy architecture renders are not guaranteed fast.
- For a simple/exploratory animation render, prefer a lightweight review copy (e.g. 960x540, EEVEE 8–16 samples) instead of automatically inheriting 1080p/64-sample settings. Preserve explicitly requested final-quality deliverables separately. Benchmark one frame before a long run. If the user requests lower quality mid-render, stop the old process group, keep completed frames, downsample valid existing frames into a separate preview sequence, render only missing frames, encode MP4, and verify frame count/fps/duration plus actual decoded frames.
- Save .blend before long rendering. Render with `bpy.ops.render.render(write_still=True)` to a unique path; individual MCP calls time out after 300s. After timeout inspect running state before retrying; do not duplicate uncertain writes.
- Verify saved files and scene state, then visually inspect PNG through look(image=...) or vision_analyze. Deliver absolute paths in CLI, not MEDIA tags.
- Verify animation at two frames, then restore the intended frame; an Action alone is insufficient evidence.
- For portrait/Reels projects, verify actual saved/rendered PNG dimensions and composition. `look(mode='frames', view='camera')` can produce landscape tiles despite a portrait scene; use it for motion checks, not as proof of output aspect or exact framing.
- After `bpy.ops.wm.open_mainfile`, the MCP execution context may have `bpy.context.screen is None`. Configure camera view in a subsequent call through `bpy.context.window_manager.windows` and each window's `screen.areas`; first read back the loaded filepath rather than repeating the open/save operation.

## Restart and failure handling

- Addon auto-starts on GUI launch/load; service sets port9877 before GUI timers. Restart=on-failure recovers crashes, not normal closes. Service is NOT enabled at login; start on demand.
- Existing MCP reconnects after Blender restart. One read-only retry may be needed after a stale socket; never blindly repeat mutations.
- If Blender is closed, start the service; do not run another MCP server manually.
- Missing tools in an existing chat: `/reload-mcp` or new session. `hermes mcp test blender` prints raw upstream discovery, not the effective include filter.
- If the Python3.11 package imports Hermes Python3.14 libraries, remove inherited PYTHONPATH/PYTHONHOME for that subprocess, not install extra dependencies. Native MCP filters these already.
- Use manage_connections for catalog/current connections, official `hermes mcp add` / `hermes config set` for custom entries. Backup configs first; preserve unrelated settings and the existing defer list.

## FaceBuilder photo fitting via safe-mode MCP

- Read installed KeenTools `facebuilder_config.py` and operator source before invoking operators; creation is `bpy.ops.keentools_fb.add_head`, not `create_head`. Call bpy operators through their full literal paths, not aliases: safe mode rejects `op = bpy.ops...; op(...)`, module namespace introspection, computed getattr, dunder access and addon imports. A rejected script is not evidence that the addon is broken.
- Keep the target FaceBuilder head ACTIVE and selected before loading photos. Outside pinmode, `FaceBuilderCameraInput._camera_at` resolves the active head, even when the import operator receives another headnum. Mismatched active/import heads cause `AssertionError: camera is not None` and partially added camera records with duplicate keyframe IDs. Do not add more heads to troubleshoot this. Check headnum, active object, camera image and keyframe IDs; retain damaged setup hidden after checkpoint and use an existing clean head if available.
- Import with direct `bpy.ops.keentools_fb.open_multiple_filebrowser('EXEC_DEFAULT', headnum=N, directory=absolute_dir, files=[{'name': filename}, ...])`. Verify camera count, distinct keyframe_id values and all image assignments. Place frontal photo first.
- In a VIEW_3D/WINDOW `bpy.context.temp_override`, start `bpy.ops.keentools_fb.pinmode('INVOKE_DEFAULT', headnum=N, camnum=0, detect_face=True)`. For each remaining camera, switch with pinmode INVOKE then call `bpy.ops.keentools_fb.pickmode_starter('EXEC_DEFAULT', headnum=N, camnum=C, auto_detect_single=True)`. Verify pins_count for every view; detector success alone is not quality approval.
- Bake via `bpy.ops.keentools_fb.bake_tex('EXEC_DEFAULT', headnum=N)` in view context. Exit using `bpy.ops.keentools_fb.exit_pinmode('EXEC_DEFAULT')`, pack source and baked images, save a unique .blend, and use look angles material shading for actual frontal/profile/three-quarter review. Viewport look can omit KeenTools GPU wire overlays, so a photo-only viewport capture cannot verify mesh fitting. Describe auto-fitted results as first-pass models until visually refined; baked hair is not hair geometry, and neck textures may capture clothing/background.

## References

https://github.com/ahujasid/mcp-for-blender
https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp
