// ECLIPSE system: Solar/Void energy, Eclipse State and the ultimate
// "Eclipse: Heaven's Abyss".
//
// Energy is stored on scoreboards so it survives relogs and can be set by
// commands (see functions/eclipse/*.mcfunction):
//   eclipse_solar  0..50   gained with SOLARIS
//   eclipse_void   0..50   gained with NOCTIS
//   eclipse_energy 0..100  = solar + void (display / command friendly)
import { system, world } from "@minecraft/server";
import * as Cooldown from "./cooldown.js";
import { ENERGY, SKILL, VFX } from "./config.js";
import { areaDamage, findTargets, slow } from "./damage.js";
import { getState } from "./state.js";
import { add, forwardFromYaw, rightFromYaw, scale, v3 } from "./vec.js";
import { anim, flash, fogPush, fogRemove, fx, later, nearbyPlayers, shake, sound } from "./vfx.js";

const OBJ = { solar: "eclipse_solar", void: "eclipse_void", total: "eclipse_energy" };
const STATE_TAG = "eclipse_state";
const FOG_ID = "eclipse:black_eclipse";
const FOG_KEY = "eclipse_ult";

/** @param {string} id @param {string} display */
function objective(id, display) {
  const sb = world.scoreboard;
  return sb.getObjective(id) ?? sb.addObjective(id, display);
}

/** Create the scoreboards (called once the world is loaded). */
export function setupScoreboards() {
  try {
    objective(OBJ.solar, "Solar Energy");
    objective(OBJ.void, "Void Energy");
    objective(OBJ.total, "Eclipse Energy");
  } catch (e) {
    console.warn(`[EclipseTwinSwords] scoreboard setup failed: ${e}`);
  }
}

/** @param {import("@minecraft/server").Player} player */
export function getEnergy(player) {
  let solar = 0;
  let voidE = 0;
  try {
    solar = objective(OBJ.solar, "Solar Energy").getScore(player) ?? 0;
    voidE = objective(OBJ.void, "Void Energy").getScore(player) ?? 0;
  } catch {
    // scoreboard not ready
  }
  solar = Math.max(0, Math.min(ENERGY.MAX_SIDE, solar));
  voidE = Math.max(0, Math.min(ENERGY.MAX_SIDE, voidE));
  return { solar, void: voidE, total: solar + voidE };
}

/** @param {import("@minecraft/server").Player} player @param {number} solar @param {number} voidE */
function setEnergy(player, solar, voidE) {
  try {
    solar = Math.round(Math.max(0, Math.min(ENERGY.MAX_SIDE, solar)));
    voidE = Math.round(Math.max(0, Math.min(ENERGY.MAX_SIDE, voidE)));
    objective(OBJ.solar, "Solar Energy").setScore(player, solar);
    objective(OBJ.void, "Void Energy").setScore(player, voidE);
    objective(OBJ.total, "Eclipse Energy").setScore(player, solar + voidE);
  } catch {
    // ignore
  }
}

/**
 * Add Solar or Void energy.
 * @param {import("@minecraft/server").Player} player @param {"solar"|"void"} side @param {number} amount
 */
export function addEnergy(player, side, amount) {
  if (amount <= 0) return;
  const e = getEnergy(player);
  if (side === "solar") setEnergy(player, e.solar + amount, e.void);
  else setEnergy(player, e.solar, e.void + amount);
  getState(player).lastGainAt = system.currentTick;
}

/** Bonus energy for enemies hit by one cast (capped). @param {number} hits */
export function hitBonus(hits) {
  return Math.min(ENERGY.HIT_BONUS_MAX, hits * ENERGY.HIT_BONUS);
}

// ------------------------------------------------------------------ state

/** @param {import("@minecraft/server").Player} player */
export function isEclipseActive(player) {
  return getState(player).eclipseUntil > system.currentTick;
}

/** Damage multiplier from the Eclipse State. @param {import("@minecraft/server").Player} player */
export function damageMultiplier(player) {
  return isEclipseActive(player) ? SKILL.ECLIPSE_STATE.damageMul : 1;
}

/** Cooldown multiplier from the Eclipse State. @param {import("@minecraft/server").Player} player */
export function cooldownMultiplier(player) {
  return isEclipseActive(player) ? SKILL.ECLIPSE_STATE.cooldownMul : 1;
}

/** @param {import("@minecraft/server").Player} player */
export function canActivate(player) {
  return !isEclipseActive(player) && getEnergy(player).total >= ENERGY.MAX;
}

/** @param {import("@minecraft/server").Player} player */
export function canUltimate(player) {
  return Cooldown.isReady(player, SKILL.HEAVENS_ABYSS.id) && (isEclipseActive(player) || getEnergy(player).total >= ENERGY.MAX);
}

/** Small helper: chest point and facing basis of a player. @param {import("@minecraft/server").Player} player */
function basis(player) {
  const yaw = player.getRotation().y;
  const fwd = forwardFromYaw(yaw);
  return { loc: player.location, fwd, right: rightFromYaw(yaw), chest: add(player.location, v3(0, 1.2, 0)) };
}

/** Enter ECLIPSE STATE. @param {import("@minecraft/server").Player} player */
export function activate(player) {
  const st = getState(player);
  const now = system.currentTick;
  const cfg = SKILL.ECLIPSE_STATE;
  st.eclipseUntil = now + cfg.duration;
  st.castLockUntil = now + cfg.castLock;
  st.stance = "";
  setEnergy(player, 0, 0);
  st.wasReady = false;
  Cooldown.refund(player, cfg.activationRefund, [SKILL.HEAVENS_ABYSS.id]);
  try {
    player.addTag(STATE_TAG);
  } catch {
    // ignore
  }

  const dim = player.dimension;
  const { loc, fwd, chest } = basis(player);
  anim(player, "eclipse_activate");
  sound(dim, "eclipse.activate", chest, 1.2);
  flash(player, [255, 214, 150], 0.04, 0.0, 0.35);
  fx(dim, "eclipse_flash", add(chest, scale(fwd, 0.5)), { scale: 1.3 }, true);
  fx(dim, "eclipse_split_ring", add(add(loc, v3(0, 1.4, 0)), scale(fwd, -0.6)), { scale: 0.9, life: 0.9, dir: fwd }, true);
  fx(dim, "eclipse_burst", chest, { density: 0.7, radius: 0.5 });
  fx(dim, "solar_shockwave", add(loc, v3(0, 0.12, 0)), { radius: 4.5 });
  fx(dim, "eclipse_ready", chest, { density: 1.5 });
  later(3, () => fx(dim, "void_shockwave", add(loc, v3(0, 0.14, 0)), { radius: 5.5 }));
}

/** @param {import("@minecraft/server").Player} player @param {boolean} [silent] */
export function endState(player, silent = false) {
  const st = getState(player);
  if (st.eclipseUntil <= 0) return;
  st.eclipseUntil = 0;
  st.stance = "";
  try {
    player.removeTag(STATE_TAG);
  } catch {
    // ignore
  }
  if (!silent && player.isValid) {
    const chest = add(player.location, v3(0, 1.1, 0));
    fx(player.dimension, "eclipse_ready", chest, { density: 0.8 });
    sound(player.dimension, "eclipse.ready", chest, 0.5, 0.8);
  }
}

/**
 * ECLIPSE: HEAVEN'S ABYSS - five-phase ultimate.
 * @param {import("@minecraft/server").Player} player
 */
export function ultimate(player) {
  const cfg = SKILL.HEAVENS_ABYSS;
  const st = getState(player);
  const now = system.currentTick;
  const mul = damageMultiplier(player);
  if (isEclipseActive(player)) endState(player, true);
  else setEnergy(player, 0, 0);
  st.wasReady = false;
  st.castLockUntil = now + cfg.castLock;
  Cooldown.start(player, cfg.id, cfg.cooldown);

  const dim = player.dimension;
  const { loc, fwd, right } = basis(player);
  const ground = add(loc, scale(fwd, 1.0));
  const sky = add(ground, v3(0, 6.5, 0));
  const ringPos = add(add(loc, v3(0, 2.4, 0)), scale(fwd, -1.1));
  /** @type {import("@minecraft/server").Player[]} */
  let fogged = [];

  // PHASE 1 - raise both blades, giant half-gold / half-void ring behind
  anim(player, "eclipse_ultimate");
  try {
    player.addEffect("slowness", cfg.castLock, { amplifier: 3, showParticles: false });
  } catch {
    // ignore
  }
  sound(dim, "eclipse.charge", add(loc, v3(0, 1.5, 0)), 1.6);
  fx(dim, "eclipse_split_ring", ringPos, { scale: 1.6, life: 2.6, dir: fwd, phase: 0 }, true);
  fx(dim, "eclipse_flash", add(loc, v3(0, 3.0, 0)), { scale: 0.8 }, true);
  fx(dim, "eclipse_stardust", add(loc, v3(0, 1.2, 0)), { density: 3, radius: 2.2 });
  for (const p of nearbyPlayers(dim, loc, VFX.CAMERA_RADIUS)) shake(p, 0.06, 1.8);

  // PHASE 2 - golden sun and black moon drift together
  later(cfg.phase2, () => {
    const travel = (cfg.phase3 - cfg.phase2) / 20;
    const span = 4.2;
    const sunStart = add(sky, scale(right, -span));
    const moonStart = add(sky, scale(right, span));
    const sunVel = scale(right, span / travel);
    const moonVel = scale(right, -span / travel);
    fx(dim, "eclipse_sun", sunStart, { scale: 1.1, life: travel, vel: sunVel }, true);
    fx(dim, "void_moon", moonStart, { scale: 0.75, life: travel, vel: moonVel }, true);
    fx(dim, "void_moon_corona", moonStart, { scale: 0.75, life: travel, vel: moonVel }, true);
    fx(dim, "eclipse_vortex", sky, { radius: 4.6, life: travel + 0.2, density: 1.2 }, true);
    fx(dim, "eclipse_stardust", ground, { density: 4, radius: 3.5 });
  });

  // PHASE 3 - Black Eclipse: darkness + hit-stop
  later(cfg.phase3, () => {
    fx(dim, "eclipse_disc", sky, { scale: 1.25, life: (cfg.phase5 - cfg.phase3) / 20 + 0.4 }, true);
    fx(dim, "eclipse_corona", sky, { scale: 1.25, life: (cfg.phase5 - cfg.phase3) / 20 + 0.4 }, true);
    sound(dim, "eclipse.rumble", sky, 1.6);
    fogged = nearbyPlayers(dim, ground, VFX.CAMERA_RADIUS);
    for (const p of fogged) {
      fogPush(p, FOG_ID, FOG_KEY);
      flash(p, [16, 4, 28], 0.08, 0.22, 0.3);
    }
    if (player.isValid) {
      for (const t of findTargets(player, dim, ground, cfg.radius)) slow(t, cfg.hitStopTicks + 2, 6);
    }
  });

  // PHASE 4 - giant shockwave from the centre
  later(cfg.phase4, () => {
    const g = add(ground, v3(0, 0.15, 0));
    fx(dim, "eclipse_pillar", ground, { scale: 1.3, height: 7.5 }, true);
    fx(dim, "eclipse_flash", sky, { scale: 2.6 }, true);
    fx(dim, "eclipse_flash", add(ground, v3(0, 1, 0)), { scale: 2.0 }, true);
    fx(dim, "eclipse_shockwave", g, { radius: cfg.radius + 0.5 }, true);
    fx(dim, "eclipse_shock_wall", add(ground, v3(0, 0.6, 0)), { radius: cfg.radius }, true);
    fx(dim, "eclipse_burst", sky, { density: 1.0, radius: 1.0 }, true);
    fx(dim, "eclipse_burst", add(ground, v3(0, 0.8, 0)), { density: 1.3, radius: 1.5, speed: 1.2 }, true);
    fx(dim, "solar_ground_crack", g, { radius: 8, life: 1.8 }, true);
    fx(dim, "void_ground_crack", add(g, v3(0, 0.02, 0)), { radius: 10, life: 2.0 }, true);
    fx(dim, "void_smoke", g, { radius: 6, density: 1.5 });
    fx(dim, "solar_debris", g, { density: 1.6, scale: 1.3 });
    sound(dim, "eclipse.impact", ground, 2.0);
    sound(dim, "eclipse.burst", sky, 1.6);
    for (const p of nearbyPlayers(dim, ground, VFX.CAMERA_RADIUS)) {
      shake(p, 0.7, 0.7);
      flash(p, [255, 240, 210], 0.02, 0.05, 0.4);
    }
    if (player.isValid) {
      const hits = areaDamage(player, dim, ground, {
        radius: cfg.radius, damage: cfg.damage, edgeDamage: cfg.edgeDamage, knockback: cfg.knockback,
        lift: cfg.lift, slowTicks: cfg.slowTicks, slowAmplifier: cfg.slowAmplifier, multiplier: mul,
      }, (t, at) => fx(dim, "eclipse_ready", at, { density: 0.5 }));
      if (hits.length) sound(dim, "eclipse.burst", ground, 0.6, 1.3);
    }
  });
  later(cfg.phase4 + 6, () => {
    fx(dim, "solar_shockwave", add(ground, v3(0, 0.2, 0)), { radius: 8, life: 0.6 });
    fx(dim, "void_shockwave", add(ground, v3(0, 0.25, 0)), { radius: 9.5, life: 0.7 });
  });

  // PHASE 5 - the Eclipse ring expands and fades away
  later(cfg.phase5, () => {
    fx(dim, "eclipse_final_ring", add(ground, v3(0, 0.3, 0)), { radius: cfg.radius + 1 }, true);
    fx(dim, "eclipse_star_rain", ground, { radius: cfg.radius * 0.85, life: 1.4 });
  });
  later(cfg.fogClear, () => {
    for (const p of fogged) if (p.isValid) fogRemove(p, FOG_KEY);
  });
}

/**
 * Per-tick upkeep for one player: state aura, energy decay, ready notice.
 * @param {import("@minecraft/server").Player} player
 * @param {number} now
 */
export function tickPlayer(player, now) {
  const st = getState(player);
  const dim = player.dimension;

  if (st.eclipseUntil > 0) {
    if (now >= st.eclipseUntil) {
      endState(player);
    } else if (now % VFX.AURA_EVERY === 0) {
      const yaw = player.getRotation().y;
      const fwd = forwardFromYaw(yaw);
      const v = player.getVelocity();
      const vel = v3(v.x * 20, v.y * 20, v.z * 20);
      const loc = player.location;
      const left = (st.eclipseUntil - now) / SKILL.ECLIPSE_STATE.duration;
      const fade = Math.min(1, left * 6);
      fx(dim, "eclipse_halo", add(add(loc, v3(0, 1.35, 0)), scale(fwd, -0.55)),
        { dir: fwd, vel, phase: (now * 1.5) % 360, alpha: fade, life: 0.25 });
      fx(dim, "eclipse_orbit", add(loc, v3(0, 0.95, 0)), { vel, phase: (now * 10) % 360, alpha: fade, life: 0.25 });
      if (now % (VFX.AURA_EVERY * 2) === 0) fx(dim, "eclipse_stardust", add(loc, v3(0, 1.0, 0)), { density: 0.7 });
    }
  }

  if (now % 4 !== 0) return;
  const e = getEnergy(player);
  if (e.total >= ENERGY.MAX && !st.wasReady && st.eclipseUntil <= now) {
    st.wasReady = true;
    const chest = add(player.location, v3(0, 1.2, 0));
    fx(dim, "eclipse_ready", chest, { density: 1.2 });
    sound(dim, "eclipse.ready", chest, 0.9);
    st.notice = "§l§6ECLIPSE §dREADY§r §7- Sneak to select";
    st.noticeUntil = now + 50;
  } else if (e.total < ENERGY.MAX) {
    st.wasReady = false;
  }

  // partial energy fades after a while without combat; a full bar stays banked
  if (now % 20 === 0 && e.total > 0 && e.total < ENERGY.MAX && st.eclipseUntil <= now && now - st.lastGainAt > ENERGY.DECAY_DELAY) {
    setEnergy(player, e.solar - ENERGY.DECAY_PER_SECOND, e.void - ENERGY.DECAY_PER_SECOND);
  }
}

/** Clean leftovers after a relog. @param {import("@minecraft/server").Player} player */
export function onJoin(player) {
  try {
    player.removeTag(STATE_TAG);
  } catch {
    // ignore
  }
  fogRemove(player, FOG_KEY);
}
