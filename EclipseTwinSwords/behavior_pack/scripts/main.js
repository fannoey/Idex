// ECLIPSE TWIN SWORDS - entry point.
// Reads input, finds the held blade, dispatches skills and runs the single
// per-tick loop (players only - never scans every entity in the world).
//
// Controls (mobile friendly, no combos):
//   SOLARIS  Use .................... Solar Slash
//            Sneak + Use ............ Radiant Spear
//            Jump + Use (airborne) .. Solar Crown
//   NOCTIS   Use .................... Void Crescent
//            Sneak + Use ............ Abyss Field
//            Jump + Use (airborne) .. Moonfall
//   ECLIPSE  Look up + Use .......... Eclipse State      (Eclipse Energy 100)
//            Look up + Sneak + Use .. Heaven's Abyss     (Energy 100 or during Eclipse State)
// The look-up gestures only take over when Eclipse is available; otherwise the
// blade's normal skill fires, so no input is ever dead or ambiguous.
import { EquipmentSlot, Player, system, world } from "@minecraft/server";
import * as Cooldown from "./cooldown.js";
import { ENERGY, HUD, INPUT, ITEM } from "./config.js";
import { bodyCenter } from "./damage.js";
import * as Eclipse from "./eclipse.js";
import * as Hud from "./hud.js";
import * as Noctis from "./noctis.js";
import { tickProjectiles } from "./projectile.js";
import * as Solaris from "./solaris.js";
import { forgetState, getState, resetStances } from "./state.js";
import { anim } from "./vfx.js";

const LORE = {
  solaris: [
    "§r§6The Blade of Dawn",
    "§r§eBearer of the Eternal Sun",
    "",
    "§r§7Use §8- §6Solar Slash",
    "§r§7Sneak + Use §8- §6Radiant Spear",
    "§r§7Jump + Use §8- §6Solar Crown",
    "§r§7Look up + Use §8- §dEclipse State",
    "§r§7Look up + Sneak + Use §8- §dHeaven's Abyss",
  ],
  noctis: [
    "§r§5The Blade of Night",
    "§r§dBearer of the Endless Void",
    "",
    "§r§7Use §8- §dVoid Crescent",
    "§r§7Sneak + Use §8- §dAbyss Field",
    "§r§7Jump + Use §8- §dMoonfall",
    "§r§7Look up + Use §8- §6Eclipse State",
    "§r§7Look up + Sneak + Use §8- §6Heaven's Abyss",
  ],
};

const TIPS = {
  solaris: "§6Use§7: Slash  §6Sneak§7: Spear  §6Jump§7: Crown",
  noctis: "§dUse§7: Crescent  §dSneak§7: Abyss  §dJump§7: Moonfall",
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

/** Jumping / falling (not flying, gliding, swimming, climbing or riding). @param {Player} player */
function isAirborne(player) {
  try {
    if (player.isFlying || player.isGliding || player.isInWater || player.isClimbing) return false;
    if (player.getComponent("minecraft:riding")) return false;
    return player.isJumping || !player.isOnGround;
  } catch {
    return false;
  }
}

/** @param {Player} player @param {"solaris"|"noctis"} weapon */
function handleUse(player, weapon) {
  const st = getState(player);
  if (system.currentTick < st.castLockUntil) return;
  const sneaking = player.isSneaking;

  if (player.getRotation().x <= INPUT.LOOK_UP_PITCH) {
    if (sneaking && Eclipse.canUltimate(player)) return Eclipse.ultimate(player);
    if (!sneaking && Eclipse.canActivate(player)) return Eclipse.activate(player);
  }

  if (weapon === "solaris") {
    if (sneaking) Solaris.radiantSpear(player);
    else if (isAirborne(player)) Solaris.solarCrown(player);
    else Solaris.solarSlash(player);
  } else {
    if (sneaking) Noctis.abyssField(player);
    else if (isAirborne(player)) Noctis.moonfall(player);
    else Noctis.voidCrescent(player);
  }
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

world.afterEvents.entityHitEntity.subscribe((ev) => {
  const player = ev.damagingEntity;
  if (!(player instanceof Player)) return;
  const held = heldWeapon(player);
  if (!held) return;
  try {
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
  anim(player, key, "eclipse.stance", `!query.is_item_name_any('slot.weapon.mainhand', 0, ${items})`, 0.3);
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
