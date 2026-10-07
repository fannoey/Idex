// ECLIPSE TWIN SWORDS - entry point.
// Reads input, finds the held blade, dispatches skills and runs the single
// per-tick loop (players only - never scans every entity in the world).
//
// Controls (one button each, mobile friendly):
//   Sneak (press) ........ cycle the selected skill
//                          SOLARIS: Solar Slash > Radiant Spear > Solar Crown
//                          NOCTIS:  Void Crescent > Abyss Field > Moonfall
//                          + ECLIPSE STATE / HEAVEN'S ABYSS when they are available
//   Use / right click .... cast the selected skill
import { ButtonState, EquipmentSlot, InputButton, Player, system, world } from "@minecraft/server";
import * as Cooldown from "./cooldown.js";
import { ENERGY, HUD, ITEM } from "./config.js";
import { bodyCenter } from "./damage.js";
import * as Eclipse from "./eclipse.js";
import * as Hud from "./hud.js";
import * as Noctis from "./noctis.js";
import { tickProjectiles } from "./projectile.js";
import * as Skills from "./skills.js";
import * as Solaris from "./solaris.js";
import { forgetState, getState, resetStances } from "./state.js";
import { anim, sound } from "./vfx.js";

const LORE = {
  solaris: [
    "§r§6The Blade of Dawn",
    "§r§eBearer of the Eternal Sun",
    "",
    "§r§7Sneak §8- §fchange skill   §7Use §8- §fcast",
    "§r§6Solar Slash §8> §6Radiant Spear §8> §6Solar Crown",
    "§r§dEclipse State §8/ §dHeaven's Abyss §7at 100 energy",
  ],
  noctis: [
    "§r§5The Blade of Night",
    "§r§dBearer of the Endless Void",
    "",
    "§r§7Sneak §8- §fchange skill   §7Use §8- §fcast",
    "§r§dVoid Crescent §8> §dAbyss Field §8> §dMoonfall",
    "§r§6Eclipse State §8/ §6Heaven's Abyss §7at 100 energy",
  ],
};

const TIPS = {
  solaris: "§6Sneak§7: change skill  §6Use§7: cast",
  noctis: "§dSneak§7: change skill  §dUse§7: cast",
};

/** @type {Set<string>} players who already saw the controls tip this session */
const tipped = new Set();

/** @param {string | undefined} typeId @returns {"solaris"|"noctis"|""} */
function weaponOf(typeId) {
  if (typeId === ITEM.SOLARIS) return "solaris";
  if (typeId === ITEM.NOCTIS) return "noctis";
  return "";
}

/** @param {Player} player */
function heldWeapon(player) {
  try {
    return weaponOf(player.getComponent("minecraft:equippable")?.getEquipment(EquipmentSlot.Mainhand)?.typeId);
  } catch {
    return "";
  }
}

/** @param {Player} player @param {"solaris"|"noctis"} weapon */
function handleUse(player, weapon) {
  if (system.currentTick < getState(player).castLockUntil) return;
  Skills.castSelected(player, weapon);
}

world.afterEvents.itemUse.subscribe((ev) => {
  const weapon = weaponOf(ev.itemStack?.typeId);
  if (!weapon) return;
  try {
    handleUse(ev.source, weapon);
  } catch (e) {
    console.warn(`[EclipseTwinSwords] skill error: ${e}`);
  }
});

// Sneak press -> next skill (works for hold-to-sneak and toggle-sneak alike:
// every press of the button is one step).
world.afterEvents.playerButtonInput.subscribe((ev) => {
  const held = heldWeapon(ev.player);
  if (!held) return;
  try {
    Skills.cycle(ev.player, held);
    anim(ev.player, "skill_select", "eclipse.select", undefined, 0.1);
    sound(ev.player.dimension, "eclipse.select", ev.player.getHeadLocation(), 0.6, held === "solaris" ? 1.15 : 0.85);
  } catch (e) {
    console.warn(`[EclipseTwinSwords] select error: ${e}`);
  }
}, { buttons: [InputButton.Sneak], state: ButtonState.Pressed });

world.afterEvents.entityHitEntity.subscribe((ev) => {
  const player = ev.damagingEntity;
  if (!(player instanceof Player)) return;
  const held = heldWeapon(player);
  if (!held) return;
  try {
    const st = getState(player);
    const now = system.currentTick;
    st.combo = now - st.comboAt > 30 ? 1 : st.combo + 1;
    st.comboAt = now;
    // basic swings alternate blades: right (vanilla swing, re-shaped) > left > cross slash
    if (now >= st.castLockUntil && st.combo % 3 === 2) anim(player, "attack_left", "eclipse.cast", undefined, 0.15);
    if (now >= st.castLockUntil && st.combo % 3 === 0) anim(player, "attack_cross", "eclipse.cast", undefined, 0.15);
    const at = bodyCenter(ev.hitEntity);
    if (held === "solaris") {
      Solaris.onMeleeHit(player, ev.hitEntity, at);
      Eclipse.addEnergy(player, "solar", ENERGY.MELEE_BONUS);
    } else {
      Noctis.onMeleeHit(player, ev.hitEntity, at);
      Eclipse.addEnergy(player, "void", ENERGY.MELEE_BONUS);
    }
  } catch {
    // ignore
  }
});

// ---------------------------------------------------------------- per tick

/** @param {Player} player @param {import("./state.js").PlayerState} st @param {string} held @param {number} now */
function updateStance(player, st, held, now) {
  let key = "";
  if (held) key = st.eclipseUntil > now ? "eclipse_idle" : held === "solaris" ? "idle_solaris" : "idle_noctis";
  if (key === st.stance) return;
  st.stance = key;
  if (!key) return; // the stop expression already ended the stance on every client
  const items = key === "eclipse_idle" ? `'${ITEM.SOLARIS}', '${ITEM.NOCTIS}'` : `'${held === "solaris" ? ITEM.SOLARIS : ITEM.NOCTIS}'`;
  const stop = `!query.is_item_name_any('slot.weapon.mainhand', 0, ${items})`;
  // layered, each fades in/out by its own blend_weight (see anims.py):
  anim(player, key, "eclipse.stance", stop, 0.3);            // holding (standing)
  anim(player, "walk", "eclipse.walk", stop, 0.3);           // walking
  anim(player, "run", "eclipse.run", stop, 0.3);             // sprinting
  anim(player, "attack", "eclipse.attack", stop, 0.2);       // basic sword swing
}

/** Write the legendary lore onto a freshly obtained blade. @param {Player} player @param {"solaris"|"noctis"} held */
function ensureLore(player, held) {
  try {
    const eq = player.getComponent("minecraft:equippable");
    const item = eq?.getEquipment(EquipmentSlot.Mainhand);
    if (!eq || !item || item.getLore().length > 0) return;
    item.setLore(LORE[held]);
    eq.setEquipment(EquipmentSlot.Mainhand, item);
  } catch {
    // ignore
  }
}

/** @param {Player} player @param {number} now */
function tickPlayer(player, now) {
  const st = getState(player);
  const held = heldWeapon(player);
  if (held !== st.held) {
    st.held = held;
    if (held) {
      ensureLore(player, held);
      if (!tipped.has(player.id + held)) {
        tipped.add(player.id + held);
        st.notice = TIPS[held];
        st.noticeUntil = now + 80;
      }
    }
  }
  updateStance(player, st, held, now);
  if (held === "solaris" || st.crownUntil > now) Solaris.tickAura(player, now, held === "solaris");
  if (held === "noctis") Noctis.tickAura(player, now);
  Eclipse.tickPlayer(player, now);
  if (now % HUD.EVERY === 0) Hud.update(player, held);
}

system.runInterval(() => {
  const now = system.currentTick;
  tickProjectiles();
  Noctis.tickFields(now);
  for (const player of world.getAllPlayers()) {
    try {
      tickPlayer(player, now);
    } catch (e) {
      console.warn(`[EclipseTwinSwords] tick error: ${e}`);
    }
  }
}, 1);

// ------------------------------------------------------------- lifecycle

world.afterEvents.worldLoad.subscribe(() => Eclipse.setupScoreboards());

world.afterEvents.playerSpawn.subscribe((ev) => {
  const st = getState(ev.player);
  st.stance = "";
  if (ev.initialSpawn) {
    Eclipse.onJoin(ev.player);
    resetStances(); // re-send stances so the newcomer sees everyone's dual blades
  }
});

world.afterEvents.playerDimensionChange.subscribe((ev) => {
  getState(ev.player).stance = "";
});

world.afterEvents.entityDie.subscribe((ev) => {
  const p = ev.deadEntity;
  if (!(p instanceof Player)) return;
  const st = getState(p);
  st.crownUntil = 0;
  Eclipse.endState(p, true);
  st.stance = "";
}, { entityTypes: ["minecraft:player"] });

world.afterEvents.playerLeave.subscribe((ev) => {
  forgetState(ev.playerId);
  Cooldown.forget(ev.playerId);
  Noctis.forgetPlayer(ev.playerId);
  tipped.delete(ev.playerId + "solaris");
  tipped.delete(ev.playerId + "noctis");
});
