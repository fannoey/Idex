// Area damage, target filtering, knockback, pull and status effects.
// Only entities inside the skill radius of the caster's dimension are queried.
import { EntityDamageCause, GameMode, world } from "@minecraft/server";
import { COMBAT } from "./config.js";
import { add, distance, normalize, sub, v3 } from "./vec.js";

/**
 * Entity query options shared by every skill.
 * @param {import("./vec.js").Vec} location @param {number} radius @param {number} [max]
 * @returns {import("@minecraft/server").EntityQueryOptions}
 */
export function queryOptions(location, radius, max = COMBAT.MAX_TARGETS) {
  return {
    location,
    maxDistance: radius,
    closest: max + 4,
    excludeTypes: COMBAT.EXCLUDE_TYPES,
    excludeFamilies: COMBAT.EXCLUDE_FAMILIES,
    excludeGameModes: [GameMode.Creative, GameMode.Spectator],
    excludeTags: [COMBAT.IMMUNE_TAG],
  };
}

/**
 * Can `source` hurt `target` with a skill?
 * @param {import("@minecraft/server").Player} source
 * @param {import("@minecraft/server").Entity} target
 */
export function isValidTarget(source, target) {
  try {
    if (!target.isValid || target.id === source.id) return false;
    if (!target.getComponent("minecraft:health")) return false;
    if (target.typeId === "minecraft:player" && !world.gameRules.pvp) return false;
    const tame = target.getComponent("minecraft:tameable");
    if (tame && tame.tamedToPlayerId === source.id) return false;
    return true;
  } catch {
    return false;
  }
}

/**
 * Entities a skill may hit around a point, closest first.
 * @param {import("@minecraft/server").Player} source
 * @param {import("@minecraft/server").Dimension} dimension
 * @param {import("./vec.js").Vec} center @param {number} radius @param {number} [max]
 */
export function findTargets(source, dimension, center, radius, max = COMBAT.MAX_TARGETS) {
  let found = [];
  try {
    found = dimension.getEntities(queryOptions(center, radius, max));
  } catch {
    return [];
  }
  const out = [];
  for (const e of found) {
    if (out.length >= max) break;
    if (isValidTarget(source, e)) out.push(e);
  }
  return out;
}

/** Body centre used for hit tests and VFX. @param {import("@minecraft/server").Entity} e */
export function bodyCenter(e) {
  try {
    const head = e.getHeadLocation();
    const feet = e.location;
    return v3(feet.x, (feet.y + head.y) * 0.5, feet.z);
  } catch {
    return add(e.location, v3(0, 0.9, 0));
  }
}

/**
 * Apply skill damage (armor applies, counts as the player's kill).
 * @param {import("@minecraft/server").Player} source
 * @param {import("@minecraft/server").Entity} target
 * @param {number} amount
 */
export function hurt(source, target, amount) {
  try {
    if (target.typeId === "minecraft:player") amount *= COMBAT.PVP_MULTIPLIER;
    /** @type {import("@minecraft/server").EntityApplyDamageOptions} */
    const options = { cause: EntityDamageCause.entityAttack };
    if (source.isValid) options.damagingEntity = source;
    return target.applyDamage(Math.max(0.5, amount), options);
  } catch {
    return false;
  }
}

/**
 * Push away from a point.
 * @param {import("@minecraft/server").Entity} target @param {import("./vec.js").Vec} from
 * @param {number} horizontal @param {number} vertical
 */
export function knockFrom(target, from, horizontal, vertical) {
  try {
    const d = sub(target.location, from);
    d.y = 0;
    const n = normalize(d.x === 0 && d.z === 0 ? v3(0.01, 0, 0.01) : d);
    target.applyKnockback({ x: n.x * horizontal, z: n.z * horizontal }, vertical);
  } catch {
    // some entities (e.g. the Ender Dragon) refuse knockback
  }
}

/**
 * Pull toward a point (Void).
 * @param {import("@minecraft/server").Entity} target @param {import("./vec.js").Vec} to
 * @param {number} strength @param {number} [vertical]
 */
export function pullTo(target, to, strength, vertical = 0.05) {
  try {
    const d = sub(to, target.location);
    d.y = 0;
    const len = Math.hypot(d.x, d.z);
    if (len < 0.4) return;
    const s = Math.min(strength, len * 0.35);
    target.applyKnockback({ x: (d.x / len) * s, z: (d.z / len) * s }, vertical);
  } catch {
    // ignore
  }
}

/** @param {import("@minecraft/server").Entity} target @param {number} ticks @param {number} amplifier */
export function slow(target, ticks, amplifier) {
  try {
    target.addEffect("slowness", ticks, { amplifier, showParticles: false });
  } catch {
    // ignore
  }
}

/**
 * Damage everything inside a radius with linear falloff toward the edge.
 * @param {import("@minecraft/server").Player} source
 * @param {import("@minecraft/server").Dimension} dimension
 * @param {import("./vec.js").Vec} center
 * @param {{radius:number, damage:number, edgeDamage?:number, knockback?:number, lift?:number,
 *          slowTicks?:number, slowAmplifier?:number, multiplier?:number, max?:number}} opt
 * @param {(target: import("@minecraft/server").Entity, at: import("./vec.js").Vec) => void} [onHit]
 */
export function areaDamage(source, dimension, center, opt, onHit) {
  const targets = findTargets(source, dimension, center, opt.radius, opt.max);
  const mul = opt.multiplier ?? 1;
  for (const t of targets) {
    const at = bodyCenter(t);
    const d = Math.min(1, distance(t.location, center) / opt.radius);
    const dmg = (opt.damage + ((opt.edgeDamage ?? opt.damage) - opt.damage) * d) * mul;
    hurt(source, t, dmg);
    if (opt.knockback) knockFrom(t, center, opt.knockback * (1 - d * 0.4), opt.lift ?? 0.2);
    if (opt.slowTicks) slow(t, opt.slowTicks, opt.slowAmplifier ?? 1);
    if (onHit) onHit(t, at);
  }
  return targets;
}
