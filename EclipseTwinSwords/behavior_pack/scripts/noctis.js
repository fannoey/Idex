// NOCTIS - Blade of Night: Void Crescent, Abyss Field, Moonfall (+ passive aura).
import { system } from "@minecraft/server";
import { aimGround } from "./aim.js";
import * as Cooldown from "./cooldown.js";
import { SKILL, VFX } from "./config.js";
import { areaDamage, findTargets, hurt, pullTo, slow } from "./damage.js";
import { addEnergy, cooldownMultiplier, damageMultiplier, hitBonus, isEclipseActive } from "./eclipse.js";
import { launch } from "./projectile.js";
import { getState } from "./state.js";
import { add, distance, scale, v3 } from "./vec.js";
import { anim, fx, later, nearbyPlayers, shake, sound } from "./vfx.js";

/**
 * @typedef {Object} AbyssField
 * @property {import("@minecraft/server").Player} source
 * @property {import("@minecraft/server").Dimension} dimension
 * @property {import("./vec.js").Vec} center
 * @property {number} endTick
 * @property {number} nextPulse
 * @property {number} multiplier
 * @property {boolean} eclipse
 * @property {number} hits
 */

/** @type {AbyssField[]} */
const fields = [];

/**
 * @param {import("@minecraft/server").Player} player @param {{id:string, name:string}} skill
 */
function ready(player, skill) {
  const left = Cooldown.remaining(player, skill.id);
  if (left <= 0) return true;
  const st = getState(player);
  st.notice = `§d${skill.name} §7${Cooldown.seconds(left)}`;
  st.noticeUntil = system.currentTick + 20;
  return false;
}

// ---------------------------------------------------------- VOID CRESCENT

/** @param {import("@minecraft/server").Player} player */
export function voidCrescent(player) {
  const cfg = SKILL.VOID_CRESCENT;
  if (!ready(player, cfg)) return false;
  const st = getState(player);
  st.castLockUntil = system.currentTick + cfg.castLock;
  st.crescentFlip = !st.crescentFlip;
  Cooldown.start(player, cfg.id, cfg.cooldown, cooldownMultiplier(player));
  addEnergy(player, "void", cfg.energy);

  const eclipse = isEclipseActive(player);
  const size = eclipse ? 1.15 : 1;
  const tilt = st.crescentFlip ? 28 : -28;
  const mul = damageMultiplier(player);
  const dim = player.dimension;

  anim(player, "void_crescent");
  sound(dim, "noctis.crescent", player.getHeadLocation(), 1.0);

  later(2, () => {
    if (!player.isValid) return;
    const dir = player.getViewDirection();
    const origin = add(add(player.getHeadLocation(), v3(0, -0.3, 0)), scale(dir, 0.9));
    const speed = cfg.speed * 20;
    fx(dim, "void_hit_core", origin, { scale: 0.45 });
    let hits = 0;
    launch({
      source: player, origin, dir, speed: cfg.speed, range: cfg.range, hitRadius: cfg.hitRadius * size, pierce: cfg.pierce,
      onTick: (p, at) => {
        const base = { dir, speed, life: 0.15, scale: size, tilt };
        fx(dim, "void_crescent_aura", at, { ...base, alpha: 0.35 });
        fx(dim, "void_crescent_body", at, { ...base, alpha: 0.7 });
        fx(dim, "void_crescent_rim", at, { ...base, alpha: 0.6 });
        if (eclipse) fx(dim, "solar_slash_core", at, { ...base, scale: size * 1.06, alpha: 0.45 });
        if (p.age % 2 === 0) fx(dim, "void_trail", at, { dir, scale: size });
        else fx(dim, "void_lines", at, { dir, scale: size });
        if (p.age % 3 === 1) fx(dim, eclipse ? "eclipse_stardust" : "void_stars", at, { density: 0.4, radius: 0.5, speed: 0.4, scale: size });
      },
      onHit: (p, target, at) => {
        hurt(player, target, cfg.damage * mul);
        if (player.isValid) pullTo(target, player.location, cfg.pull, 0.1);
        hits++;
        fx(dim, "void_hit_ring", at, { dir, scale: 0.9 * size });
        fx(dim, "void_hit_core", at, { scale: 0.7 * size });
        fx(dim, "void_stars", at, { density: 1.2, speed: 1.1, scale: size });
        if (eclipse) fx(dim, "solar_hit_ring", at, { dir, scale: size * 1.2 });
        sound(dim, "noctis.crescent_hit", at, 0.9);
      },
      onEnd: (p, at, reason) => {
        if (hits > 0) addEnergy(player, "void", hitBonus(hits));
        if (reason === "target") return;
        fx(dim, "void_hit_ring", at, { dir, scale: 0.7 * size, life: 0.28 });
        fx(dim, "void_stars", at, { density: 0.7, speed: 0.6, scale: size });
        if (reason === "block") sound(dim, "noctis.crescent_hit", at, 0.5, 1.15);
      },
    });
  });
  return true;
}

// ------------------------------------------------------------ ABYSS FIELD

/** @param {import("@minecraft/server").Player} player */
export function abyssField(player) {
  const cfg = SKILL.ABYSS_FIELD;
  if (!ready(player, cfg)) return false;
  const st = getState(player);
  const now = system.currentTick;
  st.castLockUntil = now + cfg.castLock;
  Cooldown.start(player, cfg.id, cfg.cooldown, cooldownMultiplier(player));
  addEnergy(player, "void", cfg.energy);

  const dim = player.dimension;
  const center = add(aimGround(player, cfg.range), v3(0, 0.06, 0));
  const eclipse = isEclipseActive(player);
  const life = cfg.duration / 20;
  const vars = { radius: cfg.radius, life };

  anim(player, "abyss_field");
  sound(dim, "noctis.field", center, 1.2);
  // spawned once: the client animates the whole field for its lifetime
  fx(dim, "void_field_pool", center, vars, true);
  fx(dim, "void_field_swirl", add(center, v3(0, 0.02, 0)), vars, true);
  fx(dim, "void_field_circle", add(center, v3(0, 0.04, 0)), vars, true);
  fx(dim, "void_field_lines", add(center, v3(0, 0.06, 0)), vars);
  fx(dim, "void_field_inflow", center, vars);
  fx(dim, "void_field_stars", center, vars);
  fx(dim, "void_field_core", center, { life }, true);
  fx(dim, "void_implode", add(center, v3(0, 0.8, 0)), { radius: 2.5 });
  fx(dim, "void_shockwave", add(center, v3(0, 0.1, 0)), { radius: 3.5, life: 0.4 });
  if (eclipse) fx(dim, "solar_rune_ring", add(center, v3(0, 0.08, 0)), { radius: cfg.radius * 1.6, life });

  fields.push({
    source: player, dimension: dim, center, endTick: now + cfg.duration, nextPulse: now + 6,
    multiplier: damageMultiplier(player), eclipse, hits: 0,
  });
  return true;
}

/** Advance every active Abyss Field. Called each tick from main.js. @param {number} now */
export function tickFields(now) {
  const cfg = SKILL.ABYSS_FIELD;
  for (let i = fields.length - 1; i >= 0; i--) {
    const f = fields[i];
    if (now >= f.endTick || !f.source.isValid) {
      if (f.source.isValid && f.hits > 0) addEnergy(f.source, "void", hitBonus(f.hits));
      fields.splice(i, 1);
      continue;
    }
    if (now < f.nextPulse) continue;
    f.nextPulse = now + cfg.pulseEvery;
    try {
      fx(f.dimension, f.eclipse && (now / cfg.pulseEvery) % 2 < 1 ? "solar_shockwave" : "void_pulse",
        add(f.center, v3(0, 0.15, 0)), { radius: cfg.radius, life: 0.45 });
      const targets = findTargets(f.source, f.dimension, add(f.center, v3(0, 0.5, 0)), cfg.radius + 0.5);
      for (const t of targets) {
        hurt(f.source, t, cfg.pulseDamage * f.multiplier);
        slow(t, cfg.slowTicks, cfg.slowAmplifier);
        const d = distance(t.location, f.center);
        pullTo(t, f.center, cfg.pull * Math.min(1, 0.4 + d / cfg.radius), 0.0);
      }
      if (targets.length) {
        f.hits = Math.min(f.hits + 1, 3);
        sound(f.dimension, "noctis.field_pulse", f.center, 0.45);
      }
    } catch {
      // ignore this pulse
    }
  }
}

// --------------------------------------------------------------- MOONFALL

/** @param {import("@minecraft/server").Player} player */
export function moonfall(player) {
  const cfg = SKILL.MOONFALL;
  if (!ready(player, cfg)) return false;
  const st = getState(player);
  st.castLockUntil = system.currentTick + cfg.castLock;
  Cooldown.start(player, cfg.id, cfg.cooldown, cooldownMultiplier(player));
  addEnergy(player, "void", cfg.energy);

  const dim = player.dimension;
  const ground = add(aimGround(player, cfg.range), v3(0, 0.08, 0));
  const moonAt = add(ground, v3(0, 9, 0));
  const eclipse = isEclipseActive(player);
  const mul = damageMultiplier(player);
  const charge = cfg.impactTick / 20;

  // 1-3: void circle, the black moon appears above the target
  anim(player, "moonfall");
  sound(dim, "noctis.moonfall_charge", moonAt, 1.4);
  fx(dim, "void_circle", ground, { radius: cfg.radius, life: charge + 0.6 }, true);
  fx(dim, "void_moon", moonAt, { scale: 1.25, life: charge + 0.05 }, true);
  fx(dim, "void_moon_corona", moonAt, { scale: 1.25, life: charge + 0.05 }, true);
  if (eclipse) fx(dim, "solar_rune_ring", add(ground, v3(0, 0.1, 0)), { radius: cfg.radius * 1.5, life: charge + 0.4 });

  // 4: charge (~1 second) - void gathers into the moon
  later(4, () => fx(dim, "void_implode", moonAt, { radius: 3.5, density: 1.2 }));
  later(12, () => fx(dim, "void_implode", moonAt, { radius: 2.5, density: 1.2 }));

  // 5: release toward the ground
  later(cfg.impactTick - 4, () => {
    fx(dim, "void_beam", ground, { height: 9, life: 0.5, scale: 1.3 }, true);
    fx(dim, "void_rain", ground, { radius: 2.5, height: 9, density: 1.2 });
    sound(dim, "solaris.spear_fall", moonAt, 0.7, 0.6);
  });

  // 6-8: area damage, knockback, shockwave, scattered stars
  later(cfg.impactTick, () => {
    const g = add(ground, v3(0, 0.12, 0));
    const chest = add(ground, v3(0, 1, 0));
    fx(dim, "void_hit_core", chest, { scale: 2.6, life: 0.4 }, true);
    fx(dim, "void_shockwave", g, { radius: cfg.radius + 1 }, true);
    fx(dim, "void_ground_crack", g, { radius: cfg.radius }, true);
    fx(dim, "void_smoke", g, { radius: cfg.radius, density: 1.1 });
    fx(dim, "void_stars", chest, { density: 3, speed: 2.6, radius: 1.0 });
    fx(dim, "void_implode", chest, { radius: 1.2 });
    sound(dim, "noctis.moonfall_impact", ground, 1.8);
    for (const p of nearbyPlayers(dim, ground, 16)) shake(p, 0.4, 0.45);
    if (eclipse) {
      fx(dim, "solar_shockwave", add(g, v3(0, 0.03, 0)), { radius: cfg.radius + 0.5 });
      fx(dim, "solar_stars", chest, { density: 1.5, speed: 1.6 });
    }
    if (!player.isValid) return;
    const hits = areaDamage(player, dim, ground, {
      radius: cfg.radius, damage: cfg.damage, edgeDamage: cfg.edgeDamage, knockback: cfg.knockback, lift: cfg.lift, multiplier: mul,
    }, (t, at) => fx(dim, "void_stars", at, { density: 0.6 }));
    if (hits.length) addEnergy(player, "void", hitBonus(hits.length));
  });
  return true;
}

// -------------------------------------------------------- passive & melee

/** @param {import("@minecraft/server").Player} player @param {number} now */
export function tickAura(player, now) {
  if (now % VFX.PASSIVE_EVERY !== 0) return;
  const dim = player.dimension;
  const at = add(player.location, v3(0, 1.0, 0));
  fx(dim, "void_passive_wisp", at, { density: 1 });
  if (now % (VFX.PASSIVE_EVERY * 2) === 0) fx(dim, "void_stars", at, { density: 0.3, radius: 0.8, speed: 0.2 });
}

/**
 * Basic sword hit with NOCTIS.
 * @param {import("@minecraft/server").Player} player @param {import("@minecraft/server").Entity} target
 * @param {import("./vec.js").Vec} at
 */
export function onMeleeHit(player, target, at) {
  const dim = player.dimension;
  fx(dim, "void_hit_ring", at, { dir: player.getViewDirection(), scale: 0.55, life: 0.22 });
  fx(dim, "void_stars", at, { density: 0.5, speed: 0.7 });
  if (isEclipseActive(player)) fx(dim, "solar_stars", at, { density: 0.5 });
}

/** Drop fields owned by a player who left. @param {string} playerId */
export function forgetPlayer(playerId) {
  for (let i = fields.length - 1; i >= 0; i--) {
    try {
      if (!fields[i].source.isValid || fields[i].source.id === playerId) fields.splice(i, 1);
    } catch {
      fields.splice(i, 1);
    }
  }
}
