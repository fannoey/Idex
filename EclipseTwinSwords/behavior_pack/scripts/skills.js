// Skill wheel: Sneak cycles the selected skill, Use (right click) casts it.
// Each blade has 3 skills; the two Eclipse skills join the wheel only while
// they can actually be used, so the player never cycles through dead slots.
import { system } from "@minecraft/server";
import * as Cooldown from "./cooldown.js";
import { SKILL } from "./config.js";
import * as Eclipse from "./eclipse.js";
import * as Noctis from "./noctis.js";
import * as Solaris from "./solaris.js";
import { getState } from "./state.js";

/**
 * @typedef {Object} Slot
 * @property {string} id        cooldown id
 * @property {string} name      HUD label
 * @property {string} color     section colour code
 * @property {(p: import("@minecraft/server").Player) => unknown} cast
 */

/** @type {Record<"solaris"|"noctis", Slot[]>} */
const BLADE_SLOTS = {
  solaris: [
    { id: SKILL.SOLAR_SLASH.id, name: "Solar Slash", color: "§6", cast: Solaris.solarSlash },
    { id: SKILL.RADIANT_SPEAR.id, name: "Radiant Spear", color: "§6", cast: Solaris.radiantSpear },
    { id: SKILL.SOLAR_CROWN.id, name: "Solar Crown", color: "§6", cast: Solaris.solarCrown },
  ],
  noctis: [
    { id: SKILL.VOID_CRESCENT.id, name: "Void Crescent", color: "§d", cast: Noctis.voidCrescent },
    { id: SKILL.ABYSS_FIELD.id, name: "Abyss Field", color: "§d", cast: Noctis.abyssField },
    { id: SKILL.MOONFALL.id, name: "Moonfall", color: "§d", cast: Noctis.moonfall },
  ],
};

/** @type {Slot} */
const ECLIPSE_STATE = { id: SKILL.ECLIPSE_STATE.id, name: "ECLIPSE STATE", color: "§e", cast: Eclipse.activate };
/** @type {Slot} */
const HEAVENS_ABYSS = { id: SKILL.HEAVENS_ABYSS.id, name: "HEAVEN'S ABYSS", color: "§e", cast: Eclipse.ultimate };

/**
 * Skills currently on the wheel for this blade.
 * @param {import("@minecraft/server").Player} player @param {"solaris"|"noctis"} blade
 * @returns {Slot[]}
 */
export function slots(player, blade) {
  const list = [...BLADE_SLOTS[blade]];
  if (Eclipse.canActivate(player)) list.push(ECLIPSE_STATE);
  if (Eclipse.canUltimate(player)) list.push(HEAVENS_ABYSS);
  return list;
}

/**
 * Index of the selected slot, clamped to the current wheel.
 * @param {import("@minecraft/server").Player} player @param {"solaris"|"noctis"} blade @param {Slot[]} list
 */
function index(player, blade, list) {
  const st = getState(player);
  const i = st.selected[blade] ?? 0;
  return i < list.length ? i : 0;
}

/** @param {import("@minecraft/server").Player} player @param {"solaris"|"noctis"} blade */
export function selected(player, blade) {
  const list = slots(player, blade);
  return { list, index: index(player, blade, list), slot: list[index(player, blade, list)] };
}

/**
 * Sneak pressed: move to the next skill.
 * @param {import("@minecraft/server").Player} player @param {"solaris"|"noctis"} blade
 */
export function cycle(player, blade) {
  const list = slots(player, blade);
  const st = getState(player);
  const next = (index(player, blade, list) + 1) % list.length;
  st.selected[blade] = next;
  const slot = list[next];
  const left = Cooldown.remaining(player, slot.id);
  st.notice = `§e▶ ${slot.color}§l${slot.name}§r ${left > 0 ? "§7" + Cooldown.seconds(left) : "§aREADY"}`;
  st.noticeUntil = system.currentTick + 30;
  return slot;
}

/**
 * Use pressed: cast the selected skill.
 * @param {import("@minecraft/server").Player} player @param {"solaris"|"noctis"} blade
 */
export function castSelected(player, blade) {
  const st = getState(player);
  const { slot } = selected(player, blade);
  slot.cast(player);
  // an Eclipse slot disappears once used -> fall back to the first skill
  if (slot === ECLIPSE_STATE || slot === HEAVENS_ABYSS) st.selected[blade] = 0;
}
