// SOLARIS - Blade of Dawn: Solar Slash, Radiant Spear, Solar Crown (+ passive aura).
import { system } from "@minecraft/server";
import { aimGround } from "./aim.js";
import * as Cooldown from "./cooldown.js";
import { SKILL, VFX } from "./config.js";
import { areaDamage, hurt } from "./damage.js";
import { addEnergy, cooldownMultiplier, damageMultiplier, hitBonus, isEclipseActive } from "./eclipse.js";
import { launch } from "./projectile.js";
import { getState } from "./state.js";
import { add, forwardFromYaw, scale, v3 } from "./vec.js";
import { anim, flash, fx, later, nearbyPlayers, shake, sound } from "./vfx.js";

/** @param {import("@minecraft/server").Player} player */
export function isCrowned(player) {
  return getState(player).crownUntil > system.currentTick;
}

/** Total damage multiplier for Solaris skills. @param {import("@minecraft/server").Player} player */
function solarMultiplier(player) {
  return damageMultiplier(player) * (isCrowned(player) ? SKILL.SOLAR_CROWN.damageMul : 1);
}

/**
 * Cooldown gate + "not ready" notice.
 * @param {import("@minecraft/server").Player} player @param {{id:string, name:string}} skill
 */
function ready(player, skill) {
  const left = Cooldown.remaining(player, skill.id);
  if (left <= 0) return true;
  const st = getState(player);
  st.notice = `§6${skill.name} §7${Cooldown.seconds(left)}`;
  st.noticeUntil = system.currentTick + 20;
  return false;
}

// ------------------------------------------------------------ SOLAR SLASH

/** @param {import("@minecraft/server").Player} player */
export function solarSlash(player) {
  const cfg = SKILL.SOLAR_SLASH;
  if (!ready(player, cfg)) return false;
  const st = getState(player);
  st.castLockUntil = system.currentTick + cfg.castLock;
  st.slashFlip = !st.slashFlip;
  Cooldown.start(player, cfg.id, cfg.cooldown, cooldownMultiplier(player));
  addEnergy(player, "solar", cfg.energy);

  const eclipse = isEclipseActive(player);
  const crowned = isCrowned(player);
  const size = (crowned ? SKILL.SOLAR_CROWN.slashScale : 1) * (eclipse ? 1.15 : 1);
  const tilt = st.slashFlip ? 16 : -16;
  const mul = solarMultiplier(player);
  const dim = player.dimension;

  anim(player, "solar_cast");
  sound(dim, "solaris.slash", player.getHeadLocation(), 1.0);

  later(2, () => {
    if (!player.isValid) return;
    const dir = player.getViewDirection();
    const origin = add(add(player.getHeadLocation(), v3(0, -0.3, 0)), scale(dir, 0.9));
    const speed = cfg.speed * 20;
    fx(dim, "solar_flash", origin, { scale: 0.55 * size });
    let hits = 0;
    launch({
      source: player, origin, dir, speed: cfg.speed, range: cfg.range, hitRadius: cfg.hitRadius * size, pierce: cfg.pierce,
      onTick: (p, at) => {
        const base = { dir, speed, life: 0.15, alpha: 0.6, scale: size, tilt };
        fx(dim, "solar_slash_glow", at, base);
        fx(dim, "solar_slash_core", at, base);
        fx(dim, "solar_slash_ring", at, { dir, speed, life: 0.15, alpha: 0.55, scale: size, phase: p.age * 27 });
        if (eclipse) fx(dim, "void_crescent_rim", at, { ...base, scale: size * 1.08, alpha: 0.5 });
        if (p.age % 2 === 0) fx(dim, "solar_streaks", at, { dir, scale: size, density: crowned ? 1.5 : 1 });
        if (p.age % 3 === 1) fx(dim, eclipse ? "eclipse_stardust" : "solar_stars", at, { density: 0.4, radius: 0.5, speed: 0.4, scale: size });
      },
      onHit: (p, target, at) => {
        hurt(player, target, cfg.damage * mul);
        hits++;
        fx(dim, "solar_flash", at, { scale: 0.9 * size });
        fx(dim, "solar_hit_ring", at, { dir, scale: size });
        fx(dim, "solar_stars", at, { density: 1.2, speed: 1.2, scale: size });
        if (eclipse) fx(dim, "void_hit_ring", at, { dir, scale: size * 1.2 });
        sound(dim, "solaris.slash_hit", at, 0.9);
      },
      onEnd: (p, at, reason) => {
        if (hits > 0) addEnergy(player, "solar", hitBonus(hits));
        if (reason === "target") return;
        fx(dim, "solar_hit_ring", at, { dir, scale: size * 0.7, life: 0.25 });
        fx(dim, "solar_stars", at, { density: 0.7, speed: 0.6, scale: size });
        if (reason === "block") sound(dim, "solaris.slash_hit", at, 0.5, 1.2);
      },
    });
  });
  return true;
}

// ---------------------------------------------------------- RADIANT SPEAR

/** @param {import("@minecraft/server").Player} player */
export function radiantSpear(player) {
  const cfg = SKILL.RADIANT_SPEAR;
  if (!ready(player, cfg)) return false;
  const st = getState(player);
  st.castLockUntil = system.currentTick + cfg.castLock;
  Cooldown.start(player, cfg.id, cfg.cooldown, cooldownMultiplier(player));
  addEnergy(player, "solar", cfg.energy);

  const dim = player.dimension;
  const target = aimGround(player, cfg.range);
  const ground = add(target, v3(0, 0.08, 0));
  const eclipse = isEclipseActive(player);
  const mul = solarMultiplier(player);
  const telegraph = (cfg.impactTick + 12) / 20;

  // 1-3: aim, golden magic circle, light column from the sky
  anim(player, "radiant_spear");
  sound(dim, "solaris.spear_cast", player.getHeadLocation(), 1.0);
  fx(dim, "solar_circle", ground, { radius: cfg.radius, life: telegraph }, true);
  fx(dim, "solar_rune_ring", ground, { radius: cfg.radius, life: telegraph });
  fx(dim, "solar_sky_beam", ground, { height: 18, life: cfg.impactTick / 20 + 0.1, scale: 1.0 }, true);
  if (eclipse) fx(dim, "void_field_lines", ground, { radius: cfg.radius * 1.1, life: telegraph });

  // 4-5: the spear drops
  later(cfg.fallTick, () => {
    fx(dim, "solar_spear_fall", ground, { height: 16, life: (cfg.impactTick - cfg.fallTick) / 20, scale: 1.0 }, true);
    sound(dim, "solaris.spear_fall", add(ground, v3(0, 6, 0)), 1.2);
  });

  // 6-8: impact - area damage, explosion VFX (no block damage), small knockback
  later(cfg.impactTick, () => {
    const g = add(ground, v3(0, 0.12, 0));
    const chest = add(ground, v3(0, 1, 0));
    fx(dim, eclipse ? "eclipse_flash" : "solar_flash", chest, { scale: 2.6 }, true);
    fx(dim, "solar_shockwave", g, { radius: cfg.radius + 1 }, true);
    fx(dim, "solar_ground_crack", g, { radius: cfg.radius + 0.5 });
    fx(dim, "solar_spear_stuck", ground, { life: 0.9 }, true);
    fx(dim, "solar_debris", g, { density: 1 });
    fx(dim, "solar_pillar", g, { radius: cfg.radius * 0.8 });
    fx(dim, "solar_stars", chest, { density: 2.2, speed: 1.6, radius: 0.8 });
    sound(dim, "solaris.spear_impact", ground, 1.4);
    for (const p of nearbyPlayers(dim, ground, 14)) shake(p, 0.28, 0.35);
    if (eclipse) {
      later(3, () => fx(dim, "void_shockwave", add(g, v3(0, 0.03, 0)), { radius: cfg.radius + 1.5 }));
      fx(dim, "eclipse_stardust", chest, { density: 3, radius: 1.5 });
    }
    if (!player.isValid) return;
    const hits = areaDamage(player, dim, ground, {
      radius: cfg.radius, damage: cfg.damage, edgeDamage: cfg.edgeDamage, knockback: cfg.knockback, lift: cfg.lift, multiplier: mul,
    }, (t, at) => fx(dim, "solar_stars", at, { density: 0.6, speed: 0.8 }));
    if (hits.length) addEnergy(player, "solar", hitBonus(hits.length));
  });
  return true;
}

// ------------------------------------------------------------ SOLAR CROWN

/** @param {import("@minecraft/server").Player} player */
export function solarCrown(player) {
  const cfg = SKILL.SOLAR_CROWN;
  if (!ready(player, cfg)) return false;
  const st = getState(player);
  const now = system.currentTick;
  st.castLockUntil = now + cfg.castLock;
  st.crownUntil = now + cfg.duration;
  Cooldown.start(player, cfg.id, cfg.cooldown, cooldownMultiplier(player));
  addEnergy(player, "solar", cfg.energy);
  try {
    player.addEffect("speed", cfg.duration, { amplifier: cfg.speedAmplifier, showParticles: false });
  } catch {
    // ignore
  }

  const dim = player.dimension;
  const fwd = forwardFromYaw(player.getRotation().y);
  const loc = player.location;
  anim(player, "solar_crown");
  sound(dim, "solaris.crown", add(loc, v3(0, 1.5, 0)), 1.1);
  later(6, () => {
    if (!player.isValid) return;
    const l = player.location;
    fx(dim, "solar_flash", add(l, v3(0, 3.1, 0)), { scale: 1.2 }, true);
    fx(dim, "solar_crown_burst", add(add(l, v3(0, 1.3, 0)), scale(fwd, -0.5)), { dir: fwd, scale: 1.2 }, true);
    fx(dim, "solar_pillar", l, { radius: 1.6, density: 1.2 });
    fx(dim, "solar_stars", add(l, v3(0, 1.4, 0)), { density: 2.5, radius: 0.6, speed: 0.9 });
    fx(dim, "solar_shockwave", add(l, v3(0, 0.1, 0)), { radius: 3.5, life: 0.45 });
    flash(player, [255, 226, 160], 0.03, 0.0, 0.3);
  });
  return true;
}

// -------------------------------------------------------- passive & aura

/**
 * Called every tick from main.js while the player holds SOLARIS (passive)
 * and for everybody with an active crown.
 * @param {import("@minecraft/server").Player} player @param {number} now @param {boolean} holding
 */
export function tickAura(player, now, holding) {
  const st = getState(player);
  const dim = player.dimension;
  const crowned = st.crownUntil > now;
  if (holding && now % VFX.PASSIVE_EVERY === 0) {
    fx(dim, "solar_passive", add(player.location, v3(0, 1.0, 0)), crowned ? { density: 2, scale: 1.3 } : { density: 1 });
  }
  if (crowned && now % VFX.AURA_EVERY === 0) {
    const fwd = forwardFromYaw(player.getRotation().y);
    const v = player.getVelocity();
    const vel = v3(v.x * 20, v.y * 20, v.z * 20);
    const fade = Math.min(1, (st.crownUntil - now) / 30);
    const loc = player.location;
    fx(dim, "solar_crown_halo", add(add(loc, v3(0, 1.45, 0)), scale(fwd, -0.45)),
      { dir: fwd, vel, phase: (now * 2) % 360, alpha: fade, life: 0.25 });
    fx(dim, "solar_crown_orbit", add(loc, v3(0, 0.9, 0)), { vel, phase: (now * 11) % 360, alpha: fade, life: 0.25 });
  }
}

/**
 * Basic sword hit with SOLARIS.
 * @param {import("@minecraft/server").Player} player @param {import("@minecraft/server").Entity} target
 * @param {import("./vec.js").Vec} at
 */
export function onMeleeHit(player, target, at) {
  const dim = player.dimension;
  fx(dim, "solar_flash", at, { scale: 0.45, life: 0.12 });
  fx(dim, "solar_stars", at, { density: 0.5, speed: 0.7 });
  if (isEclipseActive(player)) fx(dim, "void_stars", at, { density: 0.5 });
}
