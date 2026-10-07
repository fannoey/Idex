# Project notes (Idex — Minecraft Bedrock add-ons)

## Skill-switching convention (owner's standard — always use for combat/power add-ons)
- **Sneak (ย่อ) = switch skill**: detect the sneak *press* (rising edge of `player.isSneaking`) in a tick loop
  while the weapon is held, cycle the selected skill, show its name (title subtitle + actionbar HUD).
- **Right click (Use / คลิกขวา) = cast the selected skill**, via an item custom component `onUse` (+ `onUseOn`).
- Hold-to-charge skills: holding Use repeats `onUse` pulses; treat "no pulse for ~8 ticks" as release.
- Left click on an enemy = basic combo (`entityHitEntity`).
- Show cooldowns / gauges in an actionbar HUD while the weapon is held.

## Layout
- One folder per add-on (`vlone_outfit/`, `abyssal_inferno/`), generator script in `tools/`, `.mcaddon` in `dist/`,
  preview renders in `preview/`. Rebuild with the matching `python3 tools/build_*.py` after every change.
