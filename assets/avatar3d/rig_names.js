/*
 * Understands humanoid bone names from the common conventions, so the stage can
 * pose any of them without a per-rig table:
 *
 *   Mixamo / Ready Player Me   mixamorig:LeftArm, LeftForeArm, Spine2, Head ...
 *   VRM / VRoid                J_Bip_L_UpperArm, J_Bip_C_Spine, J_Bip_C_Head ...
 *   Unreal mannequin           upperarm_l, lowerarm_l, spine_03, head ...
 *   Blender / Rigify style     upper_arm.L, forearm.L, spine.003, head ...
 *   Character Creator          CC_Base_L_Upperarm, CC_Base_Spine02 ...
 *   Daz / Poser                lShldrBend, lForearmBend, chestUpper, head ...
 *
 * classify(name) -> { part, side }
 *   part: hips | spine | clavicle | upperarm | forearm | hand | neck | head | null
 *   side: 'L' | 'R' | null
 * Pure functions, no dependencies (unit-tested with node).
 */
export function sideOf(raw) {
  const n = String(raw || '').toLowerCase();
  if (/left/.test(n)) return 'L';
  if (/right/.test(n)) return 'R';
  if (/(^|[^a-z0-9])l([^a-z0-9]|$)/.test(n)) return 'L';        // _l_  .l  space-L
  if (/(^|[^a-z0-9])r([^a-z0-9]|$)/.test(n)) return 'R';
  if (/^l[A-Z]/.test(raw)) return 'L';                            // Daz: lShldr
  if (/^r[A-Z]/.test(raw)) return 'R';
  return null;
}

export function partOf(raw) {
  const n = String(raw || '').toLowerCase();
  if (!n) return null;
  if (/twist|roll|helper|ik$|_ik|target|pole/.test(n)) return null;
  if (/(top|nub)(_?end)?$|_end$|headtop/.test(n)) return null;   // tip helpers
  // strip index / side suffixes so `hand_l`, `hand.L`, `neck_01`, `spine.003` end on the part name
  const base = n.replace(/[._\- ]?\d+$/, '').replace(/[._\- ](l|r)$/, '');
  if (/fore.?arm|lower.?arm/.test(n)) return 'forearm';
  if (/upper.?arm|shldr/.test(n)) return 'upperarm';
  if (/(left|right)arm$|(^|[^a-z])arm([^a-z]|$)/.test(base)) return 'upperarm';
  if (/clavicle|collar|shoulder/.test(n)) return 'clavicle';
  if (/hand$/.test(base)) return 'hand';
  if (/hips|pelvis/.test(n)) return 'hips';
  if (/neck$/.test(base)) return 'neck';
  if (/(^|[^a-z]|rig)head$/.test(base) && !/forehead/.test(n)) return 'head';
  if (/spine|chest/.test(n)) return 'spine';
  return null;
}

export function classify(raw) {
  const part = partOf(raw);
  if (!part) return { part: null, side: null };
  const arm = part === 'upperarm' || part === 'forearm' || part === 'hand' || part === 'clavicle';
  return { part, side: arm ? sideOf(raw) : null };
}
