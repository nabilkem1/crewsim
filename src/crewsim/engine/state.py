from dataclasses import dataclass, field
from enum import Enum


class BlockType(Enum):
    PAIRING = "PAIRING"
    RESERVE = "RESERVE"
    DAY_OFF = "DAY_OFF"
    VACATION = "VACATION"
    TRAINING = "TRAINING"
    SIMULATOR = "SIMULATOR"
    REST = "REST"
    DEADHEAD = "DEADHEAD"
    DRAFTED_DUTY = "DRAFTED_DUTY"
    # AUD-02: a sick/absent crew member's unavailability, inserted by
    # sick_calls.apply_sick_call / apply_named_absence for the absence
    # duration. Engine-internal -- D2 never carries it. In
    # legality.OCCUPYING_BLOCKS (an absent crew member cannot be assigned
    # anything) but NOT in DUTY_BLOCKS (absence is not duty and accrues no
    # rolling-limit hours).
    ABSENCE = "ABSENCE"

# AUD-06: full-field equality, no ordering. This used to be
# @dataclass(frozen=True, order=True) with every field except `start` marked
# compare=False -- so PAIRING[100,200] == VACATION[100,500] was True and
# `calendar.remove(block)` deleted whichever block happened to share a start
# minute. Every sort in the engine passes an explicit key, so order=True was
# never needed; equality now means "the same block".
@dataclass(frozen=True)
class Block:
    start: float
    end: float
    btype: BlockType
    pairing_id: str | None = None
    reserve_call_type: str | None = None
    flight_mins: float = 0.0

@dataclass
class DutyPeriod:
    report: float
    release: float

@dataclass
class Pairing:
    pairing_id: str
    base: str
    fleet: str
    position_complement: dict[str, int]
    duty_periods: list[DutyPeriod]
    credit_hours: float

@dataclass(frozen=True)
class OpenTimeItem:
    uid: int
    pairing_id: str
    base: str
    fleet: str
    position: str
    start: float          # report time
    end: float            # release time
    deadline: float       # cancel if not covered by this time
    origin: str           # "SICK_CALL" | "CASCADE" | "DELAY"
    root_event_uid: int   # for cost attribution across cascade levels
    flight_mins: float = 0.0

@dataclass
class StateDelta:
    crew_id: str
    added_blocks: list[Block] = field(default_factory=list)
    removed_blocks: list[Block] = field(default_factory=list)

@dataclass
class CrewMember:
    crew_id: str
    base: str
    fleet_quals: set[str]
    position: str
    seniority: int
    calendar: list[Block] = field(default_factory=list)
    # Set by roster_loader.load_rosters when it carves the reserve pool. A
    # real field, not an attribute stuck on at runtime: as a dynamic attr it
    # was invisible to mypy AND silently dropped by dataclasses.replace
    # (which is why des.py deep-copies instead), so the split between line
    # holders and reserves could vanish in a refactor with nothing failing.
    _is_reserve: bool = False
    # S1b-02 AC2: the PAIRING blocks this crew member gave up by bidding
    # reserve. Kept alongside the crew rather than returned separately so
    # load_rosters' signature (ten call sites) is unchanged, and so the flying
    # stays attributable to whose line it was.
    _displaced_pairings: list[Block] = field(default_factory=list)
    # S1c-07: this reserve belongs to a base OTHER than cfg.scope.base, and can
    # only cover an in-scope item by being deadheaded to it (§5.3's XB -> DH).
    # A real field for the same reason as _is_reserve: the whole cross-base cost
    # hinges on this flag, and as a runtime attribute it would be invisible to
    # mypy and silently dropped by dataclasses.replace.
    _is_cross_base: bool = False

    def blocks_in(self, start: float, end: float) -> list[Block]:
        """Return all blocks that overlap the interval [start, end):
        every block with b.start < end and b.end > start.

        AUD-01: this is an exact linear scan, deliberately. The previous
        bisect-on-start implementation looked back only one position for a
        block spanning the query start, on the assumption that calendars
        never hold overlapping blocks -- but the engine CREATES overlapping
        blocks by design (a draft inserts DRAFTED_DUTY and REST over the
        untouched DAY_OFF/VACATION beneath them), after which the look-back
        could miss an occupying block and L0 approved a duty in the middle
        of mandatory rest. Calendars are tens of blocks over a 42-day
        horizon, so the exact scan costs nothing that matters; correctness
        of every legality/tier/eligibility read sits on this one function.
        """
        return [b for b in self.calendar if b.start < end and b.end > start]

    def get_rolling_counters(
        self, end_time: float, days: int, count_reserve_as_duty: bool = True
    ) -> tuple[float, float]:
        """
        Calculate (duty_mins, flight_mins) in the rolling `days` prior to `end_time`.
        Accounts for partial overlap of blocks that cross the window boundaries.

        `count_reserve_as_duty` (AUD-24) decides whether hours spent ON CALL
        BUT NOT FLYING accrue toward the rolling limits. It is a
        [CONFIRM: Labour Relations] question, so callers pass
        `cfg.legality.reserve_counts_as_duty` rather than this module
        assuming an answer. Takes a bool, not a block set, because legality.py
        imports from this module and not the other way round.
        """
        window_start = end_time - (days * 24 * 60.0)
        duty_mins = 0.0
        flight_mins = 0.0

        # DUTY_BLOCKS as defined in legality.py
        duty_btypes = {
            BlockType.PAIRING, BlockType.RESERVE, BlockType.DRAFTED_DUTY,
            BlockType.DEADHEAD, BlockType.SIMULATOR, BlockType.TRAINING
        }
        if not count_reserve_as_duty:
            duty_btypes.discard(BlockType.RESERVE)

        for b in self.blocks_in(window_start, end_time):
            if b.btype in duty_btypes:
                overlap_start = max(b.start, window_start)
                overlap_end = min(b.end, end_time)
                overlap_mins = max(0.0, overlap_end - overlap_start)
                duty_mins += overlap_mins
                
                if b.btype in {BlockType.PAIRING, BlockType.DRAFTED_DUTY} and b.end > b.start:
                    ratio = overlap_mins / (b.end - b.start)
                    flight_mins += (b.flight_mins or 0.0) * ratio
                    
        return duty_mins, flight_mins
