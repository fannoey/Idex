// VFX / SFX / camera helpers shared by every skill.
//  - fx():     spawns an eclipse:* particle with Molang variables (scale, density, dir, ...)
//  - sound():  plays a sound with a little pitch variation so repeats never sound robotic
//  - flash(), shake(), fogPush(): screen-space feedback (can be disabled in config)
// All calls are wrapped: a player leaving or a chunk unloading must never break a skill.
import { MolangVariableMap, system } from "@minecraft/server";
import { VFX } from "./config.js";

let budgetTick = -1;
let budgetUsed = 0;

/**
 * Spawn a particle effect from resource_pack/particles.
 * @param {import("@minecraft/server").Dimension} dimension
 * @param {string} name effect name without the "eclipse:" namespace
 * @param {import("./vec.js").Vec} location
 * @param {Record<string, number | import("./vec.js").Vec>} [vars] Molang variables (numbers or vectors)
 * @param {boolean} [critical] critical effects ignore the per-tick budget
 */
export function fx(dimension, name, location, vars, critical = false) {
  const tick = system.currentTick;
  if (tick !== budgetTick) {
    budgetTick = tick;
    budgetUsed = 0;
  }
  if (!critical && budgetUsed >= VFX.MAX_SPAWNS_PER_TICK) return false;
  budgetUsed++;
  try {
    const map = new MolangVariableMap();
    const all = vars ?? {};
    for (const key in all) {
      const value = all[key];
      if (typeof value === "number") map.setFloat(`variable.${key}`, value);
      else if (value) map.setVector3(`variable.${key}`, value);
    }
    if (VFX.DENSITY !== 1) map.setFloat("variable.density", (typeof all.density === "number" ? all.density : 1) * VFX.DENSITY);
    if (VFX.SCALE !== 1) map.setFloat("variable.scale", (typeof all.scale === "number" ? all.scale : 1) * VFX.SCALE);
    dimension.spawnParticle(`eclipse:${name}`, location, map);
    return true;
  } catch {
    return false;
  }
}

/**
 * @param {import("@minecraft/server").Dimension} dimension
 * @param {string} id sound event from sound_definitions.json
 * @param {import("./vec.js").Vec} location
 * @param {number} [volume]
 * @param {number} [pitch]
 */
export function sound(dimension, id, location, volume = 1, pitch = 1) {
  try {
    dimension.playSound(id, location, { volume, pitch: pitch * (0.96 + Math.random() * 0.08) });
  } catch {
    // dimension/chunk unavailable
  }
}

/**
 * Full-screen colour flash (camera fade). Colour channels 0..255.
 * @param {import("@minecraft/server").Player} player
 * @param {[number, number, number]} rgb
 * @param {number} fadeIn @param {number} hold @param {number} fadeOut seconds
 */
export function flash(player, rgb, fadeIn, hold, fadeOut) {
  if (!VFX.CAMERA_EFFECTS) return;
  try {
    player.camera.fade({
      fadeColor: { red: rgb[0] / 255, green: rgb[1] / 255, blue: rgb[2] / 255 },
      fadeTime: { fadeInTime: fadeIn, holdTime: hold, fadeOutTime: fadeOut },
    });
  } catch {
    // camera API unavailable for this player
  }
}

/** @param {import("@minecraft/server").Player} player @param {number} intensity 0..4 @param {number} seconds */
export function shake(player, intensity, seconds) {
  if (!VFX.CAMERA_EFFECTS) return;
  try {
    player.runCommand(`camerashake add @s ${intensity.toFixed(2)} ${seconds.toFixed(2)} positional`);
  } catch {
    // ignore
  }
}

/** @param {import("@minecraft/server").Player} player @param {string} fogId @param {string} key */
export function fogPush(player, fogId, key) {
  if (!VFX.CAMERA_EFFECTS) return;
  try {
    player.runCommand(`fog @s push ${fogId} ${key}`);
  } catch {
    // ignore
  }
}

/** @param {import("@minecraft/server").Player} player @param {string} key */
export function fogRemove(player, key) {
  try {
    player.runCommand(`fog @s remove ${key}`);
  } catch {
    // ignore (player left)
  }
}

/**
 * Players near a point (same dimension only).
 * @param {import("@minecraft/server").Dimension} dimension
 * @param {import("./vec.js").Vec} location
 * @param {number} radius
 */
export function nearbyPlayers(dimension, location, radius) {
  try {
    return dimension.getPlayers({ location, maxDistance: radius });
  } catch {
    return [];
  }
}

/**
 * Run fn after `ticks`, swallowing errors so one failed step never kills the script.
 * @param {number} ticks @param {() => void} fn
 */
export function later(ticks, fn) {
  return system.runTimeout(() => {
    try {
      fn();
    } catch (e) {
      console.warn(`[EclipseTwinSwords] ${e}`);
    }
  }, Math.max(1, Math.round(ticks)));
}

/**
 * Play a resource-pack animation on the player for everyone to see.
 * @param {import("@minecraft/server").Player} player
 * @param {string} name short name, e.g. "solar_cast" -> animation.eclipse.solar_cast
 * @param {string} [controller]
 * @param {string} [stopExpression]
 * @param {number} [blendOut]
 */
export function anim(player, name, controller = "eclipse.cast", stopExpression, blendOut = 0.2) {
  try {
    /** @type {import("@minecraft/server").PlayAnimationOptions} */
    const options = { controller, blendOutTime: blendOut };
    if (stopExpression) options.stopExpression = stopExpression;
    player.playAnimation(`animation.eclipse.${name}`, options);
  } catch {
    // ignore
  }
}
