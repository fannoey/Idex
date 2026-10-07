// Actionbar HUD: the skill wheel of the held blade (selected skill marked),
// cooldowns and the ECLIPSE ENERGY bar.
//
//   ▶Slash READY  Spear 4.2s  Crown READY
//   SOL █████ VOID ███░░  80%
//   ECLIPSE READY  (Sneak to select)
import { system } from "@minecraft/server";
import * as Cooldown from "./cooldown.js";
import { ENERGY, HUD, SKILL } from "./config.js";
import { getEnergy } from "./eclipse.js";
import * as Skills from "./skills.js";
import { getState } from "./state.js";

const SHORT = {
  [SKILL.SOLAR_SLASH.id]: "Slash", [SKILL.RADIANT_SPEAR.id]: "Spear", [SKILL.SOLAR_CROWN.id]: "Crown",
  [SKILL.VOID_CRESCENT.id]: "Crescent", [SKILL.ABYSS_FIELD.id]: "Abyss", [SKILL.MOONFALL.id]: "Moon",
  [SKILL.ECLIPSE_STATE.id]: "ECLIPSE", [SKILL.HEAVENS_ABYSS.id]: "ABYSS ULT",
};

/** @param {import("@minecraft/server").Player} player @param {string} id */
function cd(player, id) {
  const left = Cooldown.remaining(player, id);
  return left <= 0 ? "§aREADY" : `§f${Cooldown.seconds(left)}`;
}

/** @param {number} value @param {number} max @param {number} cells @param {string} on */
function bar(value, max, cells, on) {
  const filled = Math.round((Math.max(0, Math.min(max, value)) / max) * cells);
  return `${on}${"█".repeat(filled)}§8${"░".repeat(cells - filled)}`;
}

/**
 * @param {import("@minecraft/server").Player} player
 * @param {"solaris"|"noctis"|""} held
 * @param {number} now
 */
function compose(player, held, now) {
  const st = getState(player);
  const lines = [];
  if (held) {
    const { list, index } = Skills.selected(player, held);
    const parts = list.map((slot, i) => {
      let status = cd(player, slot.id);
      if (slot.id === SKILL.SOLAR_CROWN.id && st.crownUntil > now) status = `§eON ${Cooldown.seconds(st.crownUntil - now)}`;
      if (slot.id === SKILL.ECLIPSE_STATE.id || slot.id === SKILL.HEAVENS_ABYSS.id) status = "";
      const label = SHORT[slot.id] ?? slot.name;
      return i === index ? `§e▶${slot.color}§l${label}§r ${status}` : `§7${label} ${status}`;
    });
    lines.push(parts.join(" §8| "));
  }

  const ult = Cooldown.remaining(player, SKILL.HEAVENS_ABYSS.id);
  if (st.eclipseUntil > now) {
    const left = st.eclipseUntil - now;
    lines.push(`§l§6ECLIPSE §dSTATE§r ${bar(left, SKILL.ECLIPSE_STATE.duration, 10, "§e")} §f${Cooldown.seconds(left)}`);
    lines.push(ult <= 0 ? "§dHeaven's Abyss §aREADY §7(Sneak to select)" : `§7Heaven's Abyss ${Cooldown.seconds(ult)}`);
  } else {
    const e = getEnergy(player);
    const pct = Math.round((e.total / ENERGY.MAX) * 100);
    lines.push(`§6SOL ${bar(e.solar, ENERGY.MAX_SIDE, 5, "§e")} §5VOID ${bar(e.void, ENERGY.MAX_SIDE, 5, "§d")} §f${pct}%`);
    if (e.total >= ENERGY.MAX) {
      lines.push(ult <= 0 ? "§l§6ECLIPSE §dREADY§r §7Sneak to select" : `§l§6ECLIPSE §dREADY§r §7Ult ${Cooldown.seconds(ult)}`);
    } else if (ult > 0) {
      lines.push(`§7Heaven's Abyss ${Cooldown.seconds(ult)}`);
    }
  }
  if (st.noticeUntil > now && st.notice) lines.unshift(st.notice);
  return lines.join("\n");
}

/**
 * Refresh the actionbar (only when the text changed, plus a keep-alive).
 * @param {import("@minecraft/server").Player} player
 * @param {"solaris"|"noctis"|""} held
 */
export function update(player, held) {
  const now = system.currentTick;
  const st = getState(player);
  const showing = held !== "" || st.eclipseUntil > now || st.crownUntil > now;
  if (!showing) {
    if (st.hud) {
      st.hud = "";
      try {
        player.onScreenDisplay.setActionBar(" ");
      } catch {
        // ignore
      }
    }
    return;
  }
  const text = compose(player, held, now);
  if (text === st.hud && now - st.hudSentAt < HUD.KEEPALIVE) return;
  st.hud = text;
  st.hudSentAt = now;
  try {
    player.onScreenDisplay.setActionBar(text);
  } catch {
    // ignore
  }
}
