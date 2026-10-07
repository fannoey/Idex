// Headless smoke test for the ECLIPSE TWIN SWORDS scripts.
// Runs the real behavior_pack/scripts against a small mock of @minecraft/server,
// fires every skill, advances game ticks and checks that:
//   - no script error is raised,
//   - every particle / sound / animation the scripts use exists in the packs,
//   - damage, pierce, pull, energy, Eclipse State and the ultimate behave.
// Usage: node tools/eclipse/smoke_test.mjs
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..", "..");
const BP = path.join(root, "EclipseTwinSwords", "behavior_pack");
const RP = path.join(root, "EclipseTwinSwords", "resource_pack");

// ---------------------------------------------------------------- mock API
const MOCK = String.raw`
export const log = { particles: [], sounds: [], anims: [], commands: [], damage: [], knock: [], effects: [], fades: [], actionbar: [], warnings: [] };
const timeouts = [];
const intervals = [];
export const system = {
  currentTick: 0,
  runInterval(fn, every = 1) { intervals.push({ fn, every }); return intervals.length; },
  runTimeout(fn, delay = 1) { timeouts.push({ fn, at: this.currentTick + delay }); return timeouts.length; },
  afterEvents: { scriptEventReceive: sig() },
  beforeEvents: { startup: sig() },
};
export function advance(n = 1) {
  for (let i = 0; i < n; i++) {
    system.currentTick++;
    for (const t of timeouts.filter((t) => t.at <= system.currentTick)) { timeouts.splice(timeouts.indexOf(t), 1); t.fn(); }
    for (const it of intervals) if (system.currentTick % it.every === 0) it.fn();
  }
}
function sig() { const subs = []; return { subs, subscribe(fn) { subs.push(fn); return fn; }, unsubscribe() {}, fire(ev) { for (const s of subs) s(ev); } }; }
export class MolangVariableMap {
  constructor() { this.vars = {}; }
  setFloat(n, v) { if (!n.startsWith("variable.")) throw new Error("bad var " + n); this.vars[n] = v; }
  setVector3(n, v) { if (!n.startsWith("variable.")) throw new Error("bad var " + n); this.vars[n] = v; }
}
export const EquipmentSlot = { Mainhand: "Mainhand", Offhand: "Offhand" };
export const GameMode = { Creative: "Creative", Spectator: "Spectator", Survival: "Survival", Adventure: "Adventure" };
export const EntityDamageCause = { entityAttack: "entityAttack" };
export const InputButton = { Jump: "Jump", Sneak: "Sneak" };
export const ButtonState = { Pressed: "Pressed", Released: "Released" };
const objectives = new Map();
class Objective { constructor(id) { this.id = id; this.scores = new Map(); }
  getScore(p) { return this.scores.get(p.id); } setScore(p, v) { this.scores.set(p.id, v); } }
const entities = [];
export class Entity {
  constructor(typeId, loc) { this.typeId = typeId; this.location = { ...loc }; this.id = String(Math.random()); this.isValid = true; this.tags = new Set(); this.hp = 40; this.dimension = dimension; }
  getHeadLocation() { return { x: this.location.x, y: this.location.y + 1.6, z: this.location.z }; }
  getComponent(id) { if (id === "minecraft:health") return { currentValue: this.hp }; return undefined; }
  applyDamage(a, o) { if (!(a > 0)) throw new Error("bad damage " + a); this.hp -= a; log.damage.push({ id: this.id, a, by: o?.damagingEntity?.id }); return true; }
  applyKnockback(h, v) { if (typeof h !== "object" || h.x === undefined || h.z === undefined || !isFinite(h.x) || !isFinite(v)) throw new Error("bad knockback"); log.knock.push({ id: this.id, h, v }); }
  addEffect(t, d, o) { log.effects.push({ id: this.id, t, d, o }); return {}; }
  addTag(t) { this.tags.add(t); return true; } removeTag(t) { return this.tags.delete(t); }
}
export class Player extends Entity {
  constructor(loc) { super("minecraft:player", loc); this.rot = { x: 0, y: 0 }; this.isSneaking = false; this.isOnGround = true; this.isJumping = false;
    this.isFlying = false; this.isGliding = false; this.isInWater = false; this.isClimbing = false; this.vel = { x: 0, y: 0, z: 0 };
    this.mainhand = undefined; this.offhand = undefined;
    const self = this;
    this.camera = { fade(o) { log.fades.push(o); } };
    this.onScreenDisplay = { setActionBar(t) { log.actionbar.push(t); } };
    this.equip = { getEquipment(s) { return s === "Mainhand" ? self.mainhand : self.offhand; }, setEquipment(s, it) { if (s === "Mainhand") self.mainhand = it; else self.offhand = it; return true; } };
  }
  getRotation() { return this.rot; }
  getViewDirection() { const p = this.rot.x * Math.PI / 180, y = this.rot.y * Math.PI / 180; return { x: -Math.sin(y) * Math.cos(p), y: -Math.sin(p), z: Math.cos(y) * Math.cos(p) }; }
  getVelocity() { return this.vel; }
  getComponent(id) { if (id === "minecraft:equippable") return this.equip; if (id === "minecraft:health") return { currentValue: 20 }; return undefined; }
  playAnimation(name, o) { log.anims.push({ name, o }); }
  runCommand(c) { log.commands.push(c); return { successCount: 1 }; }
  getGameMode() { return "Survival"; }
}
export class ItemStack { constructor(typeId) { this.typeId = typeId; this.lore = []; } getLore() { return this.lore; } setLore(l) { this.lore = l ?? []; } }
function dist(a, b) { return Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z); }
export const dimension = {
  id: "minecraft:overworld",
  spawnParticle(name, loc, map) { if (![loc.x, loc.y, loc.z].every(Number.isFinite)) throw new Error("bad particle loc"); log.particles.push({ name, loc, vars: map?.vars }); },
  playSound(id, loc, o) { log.sounds.push({ id, o }); },
  getEntities(q) {
    let out = entities.filter((e) => e.isValid);
    if (q.location && q.maxDistance !== undefined) out = out.filter((e) => dist(e.location, q.location) <= q.maxDistance);
    if (q.excludeTypes) out = out.filter((e) => !q.excludeTypes.includes(e.typeId));
    if (q.excludeTags) out = out.filter((e) => !q.excludeTags.some((t) => e.tags.has(t)));
    if (q.location) out.sort((a, b) => dist(a.location, q.location) - dist(b.location, q.location));
    if (q.closest) out = out.slice(0, q.closest);
    return out;
  },
  getPlayers(q) { return this.getEntities(q).filter((e) => e instanceof Player); },
  getBlockFromRay(origin, dir, o) {
    if (dir.y < -0.05) { const t = (64 - origin.y) / dir.y; if (t >= 0 && t <= (o?.maxDistance ?? 999)) {
      const p = { x: origin.x + dir.x * t, y: 64, z: origin.z + dir.z * t };
      return { block: { location: { x: Math.floor(p.x), y: 63, z: Math.floor(p.z) } }, faceLocation: { x: p.x - Math.floor(p.x), y: 1, z: p.z - Math.floor(p.z) }, face: "Up" }; } }
    return undefined;
  },
  getEntitiesFromRay() { return []; },
};
export function spawn(e) { entities.push(e); return e; }
export const world = {
  afterEvents: { itemUse: sig(), entityHitEntity: sig(), playerButtonInput: sig(), worldLoad: sig(), playerSpawn: sig(), playerDimensionChange: sig(), entityDie: sig(), playerLeave: sig() },
  scoreboard: { getObjective(id) { return objectives.get(id); }, addObjective(id) { const o = new Objective(id); objectives.set(id, o); return o; } },
  gameRules: { pvp: true },
  getAllPlayers() { return entities.filter((e) => e instanceof Player && e.isValid); },
};
const origWarn = console.warn;
console.warn = (...a) => { log.warnings.push(a.join(" ")); };
`;

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "eclipse-smoke-"));
fs.mkdirSync(path.join(tmp, "node_modules", "@minecraft", "server"), { recursive: true });
fs.writeFileSync(path.join(tmp, "node_modules", "@minecraft", "server", "package.json"), JSON.stringify({ name: "@minecraft/server", type: "module", main: "index.js" }));
fs.writeFileSync(path.join(tmp, "node_modules", "@minecraft", "server", "index.js"), MOCK);
fs.writeFileSync(path.join(tmp, "package.json"), JSON.stringify({ type: "module" }));
fs.mkdirSync(path.join(tmp, "scripts"));
for (const f of fs.readdirSync(path.join(BP, "scripts"))) fs.copyFileSync(path.join(BP, "scripts", f), path.join(tmp, "scripts", f));

const api = await import(pathToFileURL(path.join(tmp, "node_modules", "@minecraft", "server", "index.js")).href);
await import(pathToFileURL(path.join(tmp, "scripts", "main.js")).href);
const { log, advance, world, Player, Entity, ItemStack, spawn, system } = api;

// --------------------------------------------------------------- fixtures
const particleIds = new Set(fs.readdirSync(path.join(RP, "particles")).map((f) => JSON.parse(fs.readFileSync(path.join(RP, "particles", f))).particle_effect.description.identifier));
const soundIds = new Set(Object.keys(JSON.parse(fs.readFileSync(path.join(RP, "sounds", "sound_definitions.json"))).sound_definitions));
const animIds = new Set(Object.keys(JSON.parse(fs.readFileSync(path.join(RP, "animations", "eclipse_player.animation.json"))).animations));

let failures = 0;
function check(cond, msg) { if (!cond) { failures++; console.log("  FAIL", msg); } else console.log("  ok  ", msg); }

world.afterEvents.worldLoad.fire({});
const p = spawn(new Player({ x: 0, y: 64, z: 0 }));
world.afterEvents.playerSpawn.fire({ player: p, initialSpawn: true });
const zombies = [6, 9, 12, 15].map((z) => spawn(new Entity("minecraft:zombie", { x: 0, y: 64, z })));
const objective = (id) => world.scoreboard.getObjective(id);
const use = () => world.afterEvents.itemUse.fire({ source: p, itemStack: p.mainhand });
const sneak = () => { world.afterEvents.playerButtonInput.fire({ player: p, button: "Sneak", newButtonState: "Pressed" }); advance(1); };
const selectedName = () => ((log.actionbar.at(-1) ?? "").split("\n").find((l) => l.includes(" §8| ")) ?? "").split(" §8| ").find((x) => x.includes("▶")) ?? "";
const dmgOf = (e) => log.damage.filter((d) => d.id === e.id).reduce((s, d) => s + d.a, 0);

console.log("SOLARIS");
p.mainhand = new ItemStack("eclipse:solaris");
advance(4);
check(p.mainhand.getLore().length > 0, "lore written on first hold");
for (const n of ["idle_solaris", "walk", "run", "attack"]) check(log.anims.some((a) => a.name === "animation.eclipse." + n), `layer ${n} applied`);
check(selectedName().includes("Slash"), "Solar Slash selected by default");
use(); advance(30);
const hitZ = zombies.filter((z) => dmgOf(z) > 0).length;
check(hitZ === 3, `Use casts Solar Slash, pierces 2 and stops at the 3rd target (hit ${hitZ})`);
check(objective("eclipse_solar")?.getScore(p) >= 6, "Solar energy gained");
sneak(); advance(4);
check(selectedName().includes("Spear"), "Sneak cycles to Radiant Spear");
check(log.anims.some((a) => a.name === "animation.eclipse.skill_select"), "skill switch flourish");
check(log.sounds.some((s) => s.id === "eclipse.select"), "skill switch sound");
p.rot = { x: 30, y: 0 }; use(); advance(30); p.rot = { x: 0, y: 0 };
check(log.particles.some((x) => x.name === "eclipse:solar_spear_fall"), "Use casts Radiant Spear");
check(log.knock.length > 0, "Radiant Spear knocks back");
sneak(); use(); advance(20);
check(log.effects.some((e) => e.id === p.id && e.t === "speed"), "Solar Crown grants speed");
check(log.particles.filter((x) => x.name === "eclipse:solar_crown_halo").length >= 5, "Solar Crown halo follows the player");
sneak(); advance(4);
check(selectedName().includes("Slash"), "wheel wraps back to Solar Slash (no Eclipse slots without energy)");
const hurtZ = zombies[3];
for (let i = 0; i < 3; i++) { world.afterEvents.entityHitEntity.fire({ damagingEntity: p, hitEntity: hurtZ }); advance(2); }
check(log.anims.some((a) => a.name === "animation.eclipse.attack_left") && log.anims.some((a) => a.name === "animation.eclipse.attack_cross"), "melee hits alternate blades");

console.log("NOCTIS");
p.mainhand = new ItemStack("eclipse:noctis");
advance(45);
check(log.anims.some((a) => a.name === "animation.eclipse.idle_noctis"), "stance switches to Noctis");
const knockBefore = log.knock.length;
use(); advance(30);
check(log.knock.length > knockBefore, "Void Crescent pulls targets");
sneak(); p.rot = { x: 40, y: 0 }; use(); p.rot = { x: 0, y: 0 };
const fieldStart = log.damage.length; advance(130);
check(log.damage.length - fieldStart >= 6, `Abyss Field pulses damage (${log.damage.length - fieldStart} hits)`);
sneak(); p.rot = { x: 30, y: 0 }; use(); advance(40); p.rot = { x: 0, y: 0 };
check(log.particles.some((x) => x.name === "eclipse:void_moon"), "Moonfall summons the black moon");
check(objective("eclipse_void")?.getScore(p) > 0, "Void energy gained");

console.log("ECLIPSE");
objective("eclipse_solar").setScore(p, 50); objective("eclipse_void").setScore(p, 50);
advance(8);
check(log.sounds.some((s) => s.id === "eclipse.ready"), "ECLIPSE READY notification");
sneak(); advance(4);
check(selectedName().includes("ECLIPSE"), "Eclipse State joins the wheel at 100 energy");
use(); advance(30);
check(p.tags.has("eclipse_state"), "Eclipse State active");
check(log.particles.some((x) => x.name === "eclipse:eclipse_halo"), "Eclipse halo aura");
check(log.anims.some((a) => a.name === "animation.eclipse.eclipse_idle"), "Eclipse stance");
let guard = 0;
while (!selectedName().includes("ABYSS ULT") && guard++ < 6) { sneak(); advance(4); }
check(selectedName().includes("ABYSS ULT"), "Heaven's Abyss selectable during Eclipse State");
use();
const ultDmg = log.damage.length; advance(100);
check(!p.tags.has("eclipse_state"), "ultimate consumes the Eclipse State");
check(log.commands.some((c) => c.startsWith("fog @s push eclipse:black_eclipse")), "Black Eclipse fog pushed");
check(log.commands.some((c) => c.startsWith("fog @s remove eclipse_ult")), "fog removed afterwards");
check(log.damage.length > ultDmg, "Heaven's Abyss deals area damage");
check(log.fades.length >= 2, "camera flashes");
advance(4);
check(selectedName().includes("Crescent"), "selection falls back to the first skill after the ultimate");

console.log("REFERENCES");
const usedP = new Set(log.particles.map((x) => x.name));
const missingP = [...usedP].filter((n) => !particleIds.has(n));
check(missingP.length === 0, `all ${usedP.size} spawned particles exist ${missingP.join(",")}`);
const usedS = new Set(log.sounds.map((s) => s.id));
const missingS = [...usedS].filter((n) => !soundIds.has(n));
check(missingS.length === 0, `all ${usedS.size} played sounds exist ${missingS.join(",")}`);
const usedA = new Set(log.anims.map((a) => a.name));
const missingA = [...usedA].filter((n) => !animIds.has(n));
check(missingA.length === 0, `all ${usedA.size} animations exist ${missingA.join(",")}`);
check(log.warnings.length === 0, `no script warnings ${log.warnings.slice(0, 3).join(" | ")}`);
const perTick = {};
for (const x of log.particles) perTick[x.tick] = (perTick[x.tick] ?? 0) + 1;
console.log(`  stats: ${log.particles.length} particle emitters over ${system.currentTick} ticks, ${log.damage.length} damage events`);
console.log("  last HUD:", JSON.stringify(log.actionbar.at(-1)));
fs.rmSync(tmp, { recursive: true, force: true });
if (failures) { console.log(`${failures} check(s) failed`); process.exit(1); }
console.log("SMOKE TEST PASSED");
