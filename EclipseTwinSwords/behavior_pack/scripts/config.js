// ECLIPSE TWIN SWORDS - tuning table.
// Every gameplay / VFX number lives here so balancing never needs a code change.
// Times are in ticks (20 ticks = 1 second), distances in blocks.

export const ITEM = {
  SOLARIS: "eclipse:solaris",
  NOCTIS: "eclipse:noctis",
};

export const SKILL = {
  SOLAR_SLASH: {
    id: "solar_slash", name: "Solar Slash",
    cooldown: 40, damage: 7, range: 15.5, speed: 1.6, pierce: 2, hitRadius: 1.3,
    energy: 6, castLock: 6,
  },
  RADIANT_SPEAR: {
    id: "radiant_spear", name: "Radiant Spear",
    cooldown: 160, damage: 12, edgeDamage: 8, radius: 4, range: 24,
    fallTick: 8, impactTick: 14, knockback: 0.55, lift: 0.35,
    energy: 12, castLock: 12,
  },
  SOLAR_CROWN: {
    id: "solar_crown", name: "Solar Crown",
    cooldown: 400, duration: 240, damageMul: 1.25, speedAmplifier: 0, slashScale: 1.35,
    energy: 15, castLock: 16,
  },
  VOID_CRESCENT: {
    id: "void_crescent", name: "Void Crescent",
    cooldown: 40, damage: 7, range: 15.5, speed: 1.5, pierce: 2, hitRadius: 1.3,
    pull: 0.55, energy: 6, castLock: 6,
  },
  ABYSS_FIELD: {
    id: "abyss_field", name: "Abyss Field",
    cooldown: 200, duration: 120, radius: 5, range: 18, pulseEvery: 10, pulseDamage: 2,
    pull: 0.3, slowTicks: 30, slowAmplifier: 1, energy: 12, castLock: 14,
  },
  MOONFALL: {
    id: "moonfall", name: "Moonfall",
    cooldown: 300, damage: 16, edgeDamage: 10, radius: 5.5, range: 24, impactTick: 22,
    knockback: 1.2, lift: 0.45, energy: 15, castLock: 24,
  },
  ECLIPSE_STATE: {
    id: "eclipse_state", name: "Eclipse State",
    duration: 300, damageMul: 1.3, cooldownMul: 0.75, activationRefund: 0.25, castLock: 20,
  },
  HEAVENS_ABYSS: {
    id: "heavens_abyss", name: "Eclipse: Heaven's Abyss",
    cooldown: 1000, damage: 26, edgeDamage: 16, radius: 11, knockback: 2.0, lift: 0.6,
    slowTicks: 60, slowAmplifier: 2, hitStopTicks: 6, castLock: 70,
    // phase timeline (ticks after cast)
    phase2: 8, phase3: 38, phase4: 44, phase5: 52, fogClear: 84,
  },
};

export const ENERGY = {
  MAX_SIDE: 50,          // Solar and Void each fill half of the Eclipse bar
  MAX: 100,
  HIT_BONUS: 1,          // extra energy per enemy hit by a skill
  HIT_BONUS_MAX: 3,      // per cast
  MELEE_BONUS: 2,        // basic sword hit
  DECAY_DELAY: 300,      // idle ticks before energy starts fading
  DECAY_PER_SECOND: 1,   // per side
};

export const COMBAT = {
  MAX_TARGETS: 16,
  PVP_MULTIPLIER: 0.6,   // skill damage vs players (prevents one-shots)
  IMMUNE_TAG: "eclipse_immune",
  EXCLUDE_TYPES: [
    "minecraft:item", "minecraft:xp_orb", "minecraft:arrow", "minecraft:snowball", "minecraft:egg",
    "minecraft:ender_pearl", "minecraft:fireball", "minecraft:small_fireball", "minecraft:wither_skull",
    "minecraft:wither_skull_dangerous", "minecraft:thrown_trident", "minecraft:fishing_hook",
    "minecraft:painting", "minecraft:leash_knot", "minecraft:area_effect_cloud", "minecraft:lightning_bolt",
    "minecraft:falling_block", "minecraft:tnt", "minecraft:xp_bottle", "minecraft:splash_potion",
    "minecraft:lingering_potion", "minecraft:shulker_bullet", "minecraft:dragon_fireball",
    "minecraft:wind_charge_projectile", "minecraft:breeze_wind_charge_projectile",
  ],
  EXCLUDE_FAMILIES: ["inanimate"],
};

export const VFX = {
  SCALE: 1.0,                // global size multiplier for every effect
  DENSITY: 1.0,              // global particle-count multiplier (0.5 = low-end phones)
  MAX_SPAWNS_PER_TICK: 48,   // emitter budget per tick (all players)
  PASSIVE_EVERY: 8,          // ticks between passive aura puffs while holding a blade
  AURA_EVERY: 3,             // refresh cadence of halos (particles live 5 ticks)
  CAMERA_EFFECTS: true,      // screen flashes / shakes / eclipse fog
  CAMERA_RADIUS: 28,         // who feels the ultimate's shake & darkness
};

export const HUD = {
  EVERY: 4,                  // actionbar refresh cadence (ticks)
  KEEPALIVE: 30,             // resend even if unchanged so it never fades
};
