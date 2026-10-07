// Small Vector3 helpers (plain objects, no allocations beyond the result).

/** @typedef {{x:number, y:number, z:number}} Vec */

/** @param {Vec} a @param {Vec} b @returns {Vec} */
export const add = (a, b) => ({ x: a.x + b.x, y: a.y + b.y, z: a.z + b.z });
/** @param {Vec} a @param {Vec} b @returns {Vec} */
export const sub = (a, b) => ({ x: a.x - b.x, y: a.y - b.y, z: a.z - b.z });
/** @param {Vec} a @param {number} s @returns {Vec} */
export const scale = (a, s) => ({ x: a.x * s, y: a.y * s, z: a.z * s });
/** @param {Vec} a @param {Vec} b */
export const dot = (a, b) => a.x * b.x + a.y * b.y + a.z * b.z;
/** @param {Vec} a */
export const length = (a) => Math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z);
/** @param {Vec} a @param {Vec} b */
export const distance = (a, b) => length(sub(a, b));
/** @param {Vec} a @param {Vec} b @param {number} t @returns {Vec} */
export const lerp = (a, b, t) => ({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t, z: a.z + (b.z - a.z) * t });
/** @param {number} x @param {number} y @param {number} z @returns {Vec} */
export const v3 = (x, y, z) => ({ x, y, z });

/** @param {Vec} a @returns {Vec} */
export function normalize(a) {
  const l = length(a);
  return l > 1e-6 ? scale(a, 1 / l) : { x: 0, y: 0, z: 1 };
}

/** Horizontal forward vector for a Minecraft yaw (degrees). @param {number} yaw @returns {Vec} */
export function forwardFromYaw(yaw) {
  const r = (yaw * Math.PI) / 180;
  return { x: -Math.sin(r), y: 0, z: Math.cos(r) };
}

/** Horizontal right-hand vector for a Minecraft yaw (degrees). @param {number} yaw @returns {Vec} */
export function rightFromYaw(yaw) {
  const r = (yaw * Math.PI) / 180;
  return { x: -Math.cos(r), y: 0, z: -Math.sin(r) };
}

/** Closest distance from point p to segment ab. @param {Vec} p @param {Vec} a @param {Vec} b */
export function segmentDistance(p, a, b) {
  const ab = sub(b, a);
  const l2 = dot(ab, ab);
  const t = l2 > 1e-9 ? Math.min(1, Math.max(0, dot(sub(p, a), ab) / l2)) : 0;
  return { dist: distance(p, add(a, scale(ab, t))), t };
}
