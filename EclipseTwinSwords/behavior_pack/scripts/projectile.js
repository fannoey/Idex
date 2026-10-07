// Script-driven projectiles (no entities): a point that travels along a ray,
// tests only the entities near its current segment, pierces a limited number
// of targets and is dropped from memory the moment it ends.
import { findTargets, bodyCenter } from "./damage.js";
import { add, distance, scale, segmentDistance } from "./vec.js";

/**
 * @typedef {Object} Projectile
 * @property {import("@minecraft/server").Player} source
 * @property {import("@minecraft/server").Dimension} dimension
 * @property {import("./vec.js").Vec} pos
 * @property {import("./vec.js").Vec} dir         unit vector
 * @property {number} speed                      blocks per tick
 * @property {number} range                      blocks (already clipped to the first solid block)
 * @property {boolean} blocked                   true when range was clipped by a block
 * @property {number} hitRadius
 * @property {number} maxHits                    pierce + 1
 * @property {number} travelled
 * @property {number} age                        ticks alive
 * @property {Set<string>} hits
 * @property {(p: Projectile, from: import("./vec.js").Vec) => void} [onTick]
 * @property {(p: Projectile, target: import("@minecraft/server").Entity, at: import("./vec.js").Vec) => void} [onHit]
 * @property {(p: Projectile, at: import("./vec.js").Vec, reason: "target"|"block"|"range") => void} [onEnd]
 */

/** @type {Projectile[]} */
const live = [];

/**
 * Launch a projectile from `origin` along `dir`.
 * @param {{source: import("@minecraft/server").Player, origin: import("./vec.js").Vec, dir: import("./vec.js").Vec,
 *          speed: number, range: number, hitRadius: number, pierce: number,
 *          onTick?: Projectile["onTick"], onHit?: Projectile["onHit"], onEnd?: Projectile["onEnd"]}} o
 */
export function launch(o) {
  const dimension = o.source.dimension;
  let range = o.range;
  let blocked = false;
  try {
    const hit = dimension.getBlockFromRay(o.origin, o.dir, {
      maxDistance: o.range, includeLiquidBlocks: false, includePassableBlocks: false,
    });
    if (hit) {
      const p = add(hit.block.location, hit.faceLocation);
      range = Math.max(0.5, distance(o.origin, p) - 0.2);
      blocked = true;
    }
  } catch {
    // unloaded chunk -> fly full range
  }
  /** @type {Projectile} */
  const p = {
    source: o.source, dimension, pos: o.origin, dir: o.dir, speed: o.speed, range, blocked,
    hitRadius: o.hitRadius, maxHits: o.pierce + 1, travelled: 0, age: 0, hits: new Set(),
    onTick: o.onTick, onHit: o.onHit, onEnd: o.onEnd,
  };
  live.push(p);
  try {
    p.onTick?.(p, p.pos);
  } catch {
    // ignore
  }
  return p;
}

/** Advance every live projectile by one tick. Called from main.js. */
export function tickProjectiles() {
  for (let i = live.length - 1; i >= 0; i--) {
    let done = true;
    try {
      done = step(live[i]);
    } catch {
      done = true;
    }
    if (done) live.splice(i, 1);
  }
}

/** @param {Projectile} p @returns {boolean} finished */
function step(p) {
  if (!p.source.isValid) return true;
  const len = Math.min(p.speed, p.range - p.travelled);
  const from = p.pos;
  const to = add(from, scale(p.dir, len));
  const mid = add(from, scale(p.dir, len * 0.5));

  const candidates = findTargets(p.source, p.dimension, mid, len * 0.5 + p.hitRadius + 1.2, 8);
  /** @type {{e: import("@minecraft/server").Entity, t: number, at: import("./vec.js").Vec}[]} */
  const hits = [];
  for (const e of candidates) {
    if (p.hits.has(e.id)) continue;
    const c = bodyCenter(e);
    const feet = add(e.location, { x: 0, y: 0.35, z: 0 });
    const a = segmentDistance(c, from, to);
    const b = segmentDistance(feet, from, to);
    const best = a.dist < b.dist ? a : b;
    if (best.dist <= p.hitRadius + 0.3) hits.push({ e, t: best.t, at: c });
  }
  hits.sort((x, y) => x.t - y.t);

  p.age++;
  for (const h of hits) {
    p.hits.add(h.e.id);
    p.onHit?.(p, h.e, h.at);
    if (p.hits.size >= p.maxHits) {
      const end = add(from, scale(p.dir, len * h.t));
      p.pos = end;
      p.onEnd?.(p, end, "target");
      return true;
    }
  }

  p.pos = to;
  p.travelled += len;
  if (p.travelled >= p.range - 1e-3) {
    p.onEnd?.(p, to, p.blocked ? "block" : "range");
    return true;
  }
  p.onTick?.(p, to);
  return false;
}

/** Number of projectiles in flight (debug / HUD). */
export function liveCount() {
  return live.length;
}
