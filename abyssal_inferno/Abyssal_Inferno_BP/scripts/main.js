// ABYSSAL INFERNO - Black Flame / Void / Abyss combat power
//   Sneak (press)     -> switch selected skill
//   Use (right click) -> cast selected skill (hold for Void Combustion)
//   Left click enemy  -> Black Flame Combo (5 hits)
import { world, system } from "@minecraft/server";
import { ITEM_ID, COMPONENT_ID, SKILLS, LORE } from "./config.js";
import { safe, now, fx, onGround, chest, playAnim, effect } from "./util.js";
import {
    getState, peekState, dropState, savePlayer, syncPlayerScores, initScoreboards, inIgnition,
} from "./state.js";
import { validTarget, tickStatus, onDeath, isValid } from "./combat.js";
import {
    castBasic, handleUse, tickCharge, cancelCharge, castIntro, castOutro, tickAura, flash,
} from "./skills.js";
import { drawHud } from "./hud.js";

// ------------------------------------------------------------ item custom component (right click)
const weaponComponent = {
    onUse(e) {
        const p = e.source;
        system.run(() => safe(() => isValid(p) && heldItem(p) && handleUse(p)));
    },
    onUseOn(e) {
        const p = e.source;
        system.run(() => safe(() => isValid(p) && heldItem(p) && handleUse(p)));
    },
};
function registerComponents(registry) {
    registry.registerCustomComponent(COMPONENT_ID, weaponComponent);
}
if (system.beforeEvents && system.beforeEvents.startup) {
    system.beforeEvents.startup.subscribe((e) => registerComponents(e.itemComponentRegistry));
} else {
    world.beforeEvents.worldInitialize.subscribe((e) => registerComponents(e.itemComponentRegistry));
}

// ------------------------------------------------------------ helpers
function heldItem(p) {
    try {
        const it = p.getComponent("minecraft:equippable").getEquipment("Mainhand");
        return it && it.typeId === ITEM_ID ? it : undefined;
    } catch {
        return undefined;
    }
}

function ensureLore(p, item) {
    try {
        const cur = item.getLore();
        if (cur.length === LORE.length && cur.every((l, i) => l === LORE[i])) return;
        item.setLore(LORE);
        p.getComponent("minecraft:equippable").setEquipment("Mainhand", item);
    } catch {
        // ignore
    }
}

function switchSkill(p, st, t) {
    st.sel = (st.sel + 1) % SKILLS.length;
    st.lastSwitch = t;
    st.dirty = true;
    const sk = SKILLS[st.sel];
    const dim = p.dimension;
    fx(dim, "abyss:ring_wave", onGround(dim, p.location), { radius: 1.2, life: 0.35 });
    fx(dim, st.sel % 2 ? "abyss:void_mote" : "abyss:ember", chest(p));
    playAnim(p, "animation.abyss.switch", 0.15);
    try {
        p.playSound("random.click", { volume: 0.6, pitch: 1.6 });
        p.playSound("fire.ignite", { volume: 0.4, pitch: 1.4 });
        p.onScreenDisplay.setTitle(" ", {
            subtitle: `${sk.color}§l« ${sk.name} »`,
            fadeInDuration: 0,
            stayDuration: 14,
            fadeOutDuration: 6,
        });
    } catch {
        // ignore
    }
    flash(st, `§7${sk.hint}`, 40);
    drawHud(p, st);
}

function buffs(p, st) {
    // Combo 5: attack speed +10%, Abyss Ignition: +15% (Bedrock: haste speeds up the swing)
    const amp = inIgnition(st) ? 1 : st.combo >= 5 ? 0 : -1;
    if (amp >= 0) effect(p, "haste", 30, amp);
}

// ------------------------------------------------------------ per player tick
function tickPlayer(p, t) {
    const item = heldItem(p);
    if (!item && !peekState(p.id)) return;
    const st = getState(p);
    const holding = !!item;

    if (holding && !st.holding) {
        st.holding = true;
        st.wasSneaking = p.isSneaking;
        ensureLore(p, item);
        castIntro(p, st);
    } else if (!holding && st.holding) {
        st.holding = false;
        cancelCharge(p, st);
        castOutro(p, st);
    }

    if (st.combo > 0 && t > st.comboExpire) st.combo = 0;

    if (holding) {
        if (st.charge) tickCharge(p, st);
        const sneaking = p.isSneaking;
        if (sneaking && !st.wasSneaking && t - st.lastSwitch >= 4 && !st.charge) switchSkill(p, st, t);
        st.wasSneaking = sneaking;
        tickAura(p, st, t, inIgnition(st));
        if (t % 4 === 0) drawHud(p, st);
    }
    if (t % 20 === 0) {
        buffs(p, st);
        syncPlayerScores(p, st);
    }
    if (t % 40 === 0) savePlayer(p, st);
}

let ready = false;
system.runInterval(() => {
    if (!ready) {
        ready = true;
        safe(initScoreboards);
    }
    const t = now();
    for (const p of world.getAllPlayers()) safe(() => tickPlayer(p, t));
    safe(tickStatus);
}, 1);

// ------------------------------------------------------------ events
world.afterEvents.entityHitEntity.subscribe((ev) => {
    const p = ev.damagingEntity;
    if (!p || p.typeId !== "minecraft:player" || !heldItem(p)) return;
    const target = ev.hitEntity;
    if (!validTarget(target, p)) return;
    safe(() => castBasic(p, getState(p), target));
});

world.afterEvents.entityDie.subscribe((ev) => {
    safe(() => onDeath(ev.deadEntity, ev.damageSource));
});

world.afterEvents.playerLeave.subscribe((ev) => {
    dropState(ev.playerId);
});
