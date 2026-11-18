"""Draft state construction and validation (kutsal_amac.md §12.1)."""
from __future__ import annotations

from engine.contracts.records import DraftState, DraftSlot, STANDARD_DRAFT_ORDER
from engine.contracts.types import Role, ALL_ROLES
from engine.data.store import Dataset


class DraftError(ValueError):
    pass


def _split_names(s: str) -> list[str]:
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def build_draft_from_args(ds: Dataset, user_role: Role, ally: str, enemy: str,
                          bans: str, user_team: str = "BLUE",
                          side_known: bool = False) -> DraftState:
    ally_ids = []
    for name in _split_names(ally):
        cid = ds.resolve_id(name)
        if cid is None:
            raise DraftError(f"unknown ally champion: {name}")
        ally_ids.append(cid)
    enemy_ids = []
    for name in _split_names(enemy):
        cid = ds.resolve_id(name)
        if cid is None:
            raise DraftError(f"unknown enemy champion: {name}")
        enemy_ids.append(cid)
    ban_ids = []
    for name in _split_names(bans):
        cid = ds.resolve_id(name)
        if cid is None:
            raise DraftError(f"unknown ban: {name}")
        ban_ids.append(cid)
    return build_draft(ds, user_role, ally_ids, enemy_ids, ban_ids, user_team, side_known)


def build_draft(ds: Dataset, user_role: Role, ally_ids: list[int],
                enemy_ids: list[int], ban_ids: list[int],
                user_team: str = "BLUE", side_known: bool = False,
                enemy_roles: list[Role | None] | None = None) -> DraftState:
    all_ids = ally_ids + enemy_ids + ban_ids
    if len(set(all_ids)) != len(all_ids):
        raise DraftError("duplicate champion across picks/bans")
    if len(ally_ids) > 4 or len(enemy_ids) > 5:
        raise DraftError("too many picks (ally max 4 + user, enemy max 5)")

    other_team = "RED" if user_team == "BLUE" else "BLUE"
    slots: list[DraftSlot] = []
    # user team: allies fill first slots, user slot remains empty
    for i, cid in enumerate(ally_ids):
        slots.append(DraftSlot(team=user_team, index=i, actor="PICK", champion_id=cid))
    user_index = len(ally_ids)
    slots.append(DraftSlot(team=user_team, index=user_index, actor="PICK",
                           champion_id=None, role=user_role, is_user=True))
    for i in range(user_index + 1, 5):
        slots.append(DraftSlot(team=user_team, index=i, actor="PICK", champion_id=None))
    # enemy team
    for i in range(5):
        cid = enemy_ids[i] if i < len(enemy_ids) else None
        role = None
        if side_known and cid is not None:
            role = (enemy_roles[i] if enemy_roles and i < len(enemy_roles) else ALL_ROLES[i])
        slots.append(DraftSlot(team=other_team, index=i, actor="PICK",
                               champion_id=cid, role=role))
    for i, cid in enumerate(ban_ids[:10]):
        slots.append(DraftSlot(team=user_team if i % 2 == 0 else other_team,
                               index=i, actor="BAN", champion_id=cid))

    picked = [s.champion_id for s in slots if s.actor == "PICK" and s.champion_id]
    banned = [s.champion_id for s in slots if s.actor == "BAN" and s.champion_id]
    available = [cid for cid in ds.champions if cid not in picked and cid not in banned]

    # current step = user's pick; future steps = remaining empty PICK steps in order
    order = list(STANDARD_DRAFT_ORDER)
    pick_steps = [i for i, (team, actor) in enumerate(order) if actor == "PICK"]
    user_step_pos = user_index if user_team == "BLUE" else user_index + 1
    current_step = pick_steps[min(user_step_pos, len(pick_steps) - 1)]

    return DraftState(
        draft_id=f"draft-{user_team.lower()}-{user_role.value.lower()}",
        user_team=user_team, user_role=user_role,
        patch=ds.manifest.get("patch", "unknown"),
        order=order, slots=slots, picked_ids=picked, banned_ids=banned,
        current_step=current_step, available_ids=available,
    )


def future_steps(draft: DraftState) -> list[tuple[int, str, int]]:
    """[(order_index, team, slot_index)] for empty PICK slots after current step."""
    empty_by_team = {t: [s.index for s in draft.slots
                         if s.team == t and s.actor == "PICK" and s.champion_id is None
                         and not s.is_user]
                     for t in ("BLUE", "RED")}
    out = []
    counters = {"BLUE": 0, "RED": 0}
    for i in range(draft.current_step + 1, len(draft.order)):
        team, actor = draft.order[i]
        if actor != "PICK":
            continue
        lst = empty_by_team[team]
        if counters[team] < len(lst):
            out.append((i, team, lst[counters[team]]))
            counters[team] += 1
    return out


def enemy_known(draft: DraftState) -> list[tuple[int, Role | None]]:
    other = "RED" if draft.user_team == "BLUE" else "BLUE"
    return [(s.champion_id, s.role) for s in draft.slots
            if s.team == other and s.actor == "PICK" and s.champion_id]


def ally_known(draft: DraftState) -> list[tuple[int, Role | None]]:
    return [(s.champion_id, s.role) for s in draft.slots
            if s.team == draft.user_team and s.actor == "PICK"
            and s.champion_id and not s.is_user]
