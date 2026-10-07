// Actionbar HUD: skill cooldowns of the held blade + ECLIPSE ENERGY bar.
//
//   Slash READY | Spear 4.2s | Crown READY
//   SOL █████ VOID ███░░  80%
//   ECLIPSE READY  (Look up + Use)
import { system } from "@minecraft/server";
import * as Cooldown from "./cooldown.js";
import { ENERGY, HUD, SKILL } from "./config.js";
import { getEnergy } from "./eclipse.js";
import { getState } from "./state.js";

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
  if (held === "solaris") {
    const crown = st.crownUntil > now
      ? `§eON ${Cooldown.seconds(st.crownUntil - now)}`
      : cd(player, SKILL.SOLAR_CROWN.id);
    lines.push(`§6Slash ${cd(player, SKILL.SOLAR_SLASH.id)} §8| §6Spear ${cd(player, SKILL.RADIANT_SPEAR.id)} §8| §6Crown ${crown}`);
  } else if (held === "noctis") {
    lines.push(`§dCrescent ${cd(player, SKILL.VOID_CRESCENT.id)} §8| §dAbyss ${cd(player, SKILL.ABYSS_FIELD.id)} §8| §dMoon ${cd(player, SKILL.MOONFALL.id)}`);
  }

  const ult = Cooldown.remaining(player, SKILL.HEAVENS_ABYSS.id);
  if (st.eclipseUntil > now) {
    const left = st.eclipseUntil - now;
    lines.push(`§l§6ECLIPSE §dSTATE§r ${bar(left, SKILL.ECLIPSE_STATE.duration, 10, "§e")} §f${Cooldown.seconds(left)}`);
    lines.push(ult <= 0 ? "§dHeaven's Abyss §aREADY §7(Look up + Sneak + Use)" : `§7Heaven's Abyss ${Cooldown.seconds(ult)}`);
  } else {
    const e = getEnergy(player);
    const pct = Math.round((e.total / ENERGY.MAX) * 100);
    lines.push(`§6SOL ${bar(e.solar, ENERGY.MAX_SIDE, 5, "§e")} §5VOID ${bar(e.void, ENERGY.MAX_SIDE, 5, "§d")} §f${pct}%`);
    if (e.total >= ENERGY.MAX) {
      lines.push(ult <= 0 ? "§l§6ECLIPSE §dREADY§r §7Look up + Use" : `§l§6ECLIPSE §dREADY§r §7Ult ${Cooldown.seconds(ult)}`);
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
