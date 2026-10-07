import { SKILLS, CHARGE, COMBO_MAX } from "./config.js";
import { now } from "./util.js";
import { cdLeft, gaugesFull, inIgnition } from "./state.js";

function bar(value, max, on, off, cells = 20) {
    const n = Math.max(0, Math.min(cells, Math.round((value / max) * cells)));
    return `${on}${"|".repeat(n)}${off}${"|".repeat(cells - n)}`;
}

function skillStatus(st, sk) {
    if (sk.key === "ult") return gaugesFull(st) ? "§a§lREADY" : "§8LOCKED";
    if (sk.key === "charge" && st.charge) {
        const lvl = Math.min(1, (now() - st.charge.start) / CHARGE.fullTicks);
        return lvl >= 1 ? "§b§lFULL" : `${bar(lvl, 1, "§9", "§8", 10)}`;
    }
    const left = cdLeft(st, sk.key);
    return left > 0 ? `§7${(left / 20).toFixed(1)}s` : "§aREADY";
}

/** Actionbar HUD shown while holding the weapon. */
export function drawHud(p, st) {
    const t = now();
    const sk = SKILLS[st.sel];
    const lines = [];
    lines.push(`§8[${st.sel + 1}/${SKILLS.length}] ${sk.color}§l${sk.name}§r  ${skillStatus(st, sk)}`);
    lines.push(`§cINFERNO ${bar(st.inferno, 100, "§c", "§8")} §f${st.inferno}   §5VOID ${bar(st.void, 100, "§d", "§8")} §f${st.void}`);
    const extra = [];
    if (inIgnition(st)) extra.push(`§l§dABYSS IGNITION §r§f${((st.ignitionUntil - t) / 20).toFixed(1)}s`);
    if (gaugesFull(st)) extra.push("§l§6ULTIMATE READY");
    if (st.combo > 0) {
        const bonus = st.combo >= 10 ? " §e+15%" : st.combo >= 3 ? " §e+5%" : "";
        extra.push(`§6COMBO §l${st.combo}§r§6/${COMBO_MAX}${bonus}`);
    }
    if (st.msg && t < st.msgUntil) extra.push(st.msg);
    if (extra.length) lines.push(extra.join("   "));
    try {
        p.onScreenDisplay.setActionBar(lines.join("\n"));
    } catch {
        // ignore
    }
}
