// Per-player runtime state (memory only; energy itself lives on the scoreboard).

/**
 * @typedef {Object} PlayerState
 * @property {number} castLockUntil   no new skill before this tick
 * @property {number} crownUntil      Solar Crown active until this tick
 * @property {number} eclipseUntil    Eclipse State active until this tick
 * @property {string} stance          stance animation currently applied ("" = none)
 * @property {string} hud             last actionbar text sent
 * @property {number} hudSentAt
 * @property {string} notice          short actionbar notice (cooldown / ready)
 * @property {number} noticeUntil
 * @property {number} lastGainAt      last tick energy was gained (decay timer)
 * @property {boolean} wasReady       energy reached 100 last check
 * @property {string} loreChecked     typeId whose lore was already verified this hold
 * @property {boolean} slashFlip      alternate Solar Slash tilt
 * @property {boolean} crescentFlip   alternate Void Crescent tilt
 * @property {string} held            weapon held last tick ("solaris" | "noctis" | "")
 * @property {{solaris?: number, noctis?: number}} selected  skill-wheel index per blade
 * @property {number} combo           melee hit counter (attack animation variety)
 * @property {number} comboAt         tick of the last melee hit
 */

/** @type {Map<string, PlayerState>} */
const states = new Map();

/** @param {{id:string}} player @returns {PlayerState} */
export function getState(player) {
  let s = states.get(player.id);
  if (!s) {
    s = {
      castLockUntil: 0, crownUntil: 0, eclipseUntil: 0, stance: "", hud: "", hudSentAt: 0,
      notice: "", noticeUntil: 0, lastGainAt: 0, wasReady: false, loreChecked: "",
      slashFlip: false, crescentFlip: false, held: "", selected: {}, combo: 0, comboAt: 0,
    };
    states.set(player.id, s);
  }
  return s;
}

/** Force every player's stance animation to be re-sent (e.g. somebody joined). */
export function resetStances() {
  for (const s of states.values()) s.stance = "";
}

/** @param {string} playerId */
export function forgetState(playerId) {
  states.delete(playerId);
}
