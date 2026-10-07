// Per-player skill cooldowns, stored as "tick when ready" (no per-tick work).
import { system } from "@minecraft/server";

/** @type {Map<string, Map<string, number>>} playerId -> (skillId -> ready tick) */
const readyAt = new Map();

/** @param {string} playerId */
function table(playerId) {
  let t = readyAt.get(playerId);
  if (!t) {
    t = new Map();
    readyAt.set(playerId, t);
  }
  return t;
}

/** Remaining ticks (0 = ready). @param {{id:string}} player @param {string} skillId */
export function remaining(player, skillId) {
  const at = readyAt.get(player.id)?.get(skillId) ?? 0;
  return Math.max(0, at - system.currentTick);
}

/** @param {{id:string}} player @param {string} skillId */
export function isReady(player, skillId) {
  return remaining(player, skillId) <= 0;
}

/**
 * Start a cooldown. `multiplier` < 1 shortens it (Eclipse State).
 * @param {{id:string}} player @param {string} skillId @param {number} ticks @param {number} [multiplier]
 */
export function start(player, skillId, ticks, multiplier = 1) {
  table(player.id).set(skillId, system.currentTick + Math.max(1, Math.round(ticks * multiplier)));
}

/**
 * Shorten every running cooldown by a fraction (0.25 = 25% of what is left).
 * @param {{id:string}} player @param {number} fraction @param {string[]} [except]
 */
export function refund(player, fraction, except = []) {
  const t = readyAt.get(player.id);
  if (!t) return;
  const now = system.currentTick;
  for (const [id, at] of t) {
    if (except.includes(id) || at <= now) continue;
    t.set(id, now + Math.round((at - now) * (1 - fraction)));
  }
}

/** Seconds text for the HUD. @param {number} ticks */
export function seconds(ticks) {
  return (ticks / 20).toFixed(1) + "s";
}

/** @param {string} playerId */
export function forget(playerId) {
  readyAt.delete(playerId);
}
