// Ground targeting for placed skills (Radiant Spear, Abyss Field, Moonfall).
import { COMBAT } from "./config.js";
import { isValidTarget } from "./damage.js";
import { add, distance, scale, v3 } from "./vec.js";

/**
 * Point on the ground the player is aiming at (block, entity, or a point ahead).
 * @param {import("@minecraft/server").Player} player
 * @param {number} range
 */
export function aimGround(player, range) {
  const dim = player.dimension;
  const eye = player.getHeadLocation();
  const dir = player.getViewDirection();
  /** @type {import("./vec.js").Vec | undefined} */
  let point;
  let best = range;
  try {
    const hit = dim.getBlockFromRay(eye, dir, { maxDistance: range, includeLiquidBlocks: true, includePassableBlocks: false });
    if (hit) {
      point = add(add(hit.block.location, hit.faceLocation), scale(dir, -0.3));
      best = distance(eye, point);
    }
  } catch {
    // unloaded chunk
  }
  try {
    const hits = dim.getEntitiesFromRay(eye, dir, {
      maxDistance: best, excludeTypes: COMBAT.EXCLUDE_TYPES, excludeFamilies: COMBAT.EXCLUDE_FAMILIES,
    });
    for (const h of hits) {
      if (isValidTarget(player, h.entity)) {
        point = h.entity.location;
        break;
      }
    }
  } catch {
    // ignore
  }
  if (!point) point = add(eye, scale(dir, Math.min(range, 14)));
  return dropToGround(dim, point, 14);
}

/**
 * Settle a point onto the first solid surface below it.
 * @param {import("@minecraft/server").Dimension} dim
 * @param {import("./vec.js").Vec} p
 * @param {number} maxDown
 */
export function dropToGround(dim, p, maxDown) {
  try {
    const start = add(p, v3(0, 0.6, 0));
    const hit = dim.getBlockFromRay(start, v3(0, -1, 0), { maxDistance: maxDown, includeLiquidBlocks: true, includePassableBlocks: false });
    if (hit) return v3(p.x, hit.block.location.y + hit.faceLocation.y, p.z);
  } catch {
    // ignore
  }
  return p;
}
