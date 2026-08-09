import bisect
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

@dataclass(frozen=True, order=True)
class Block:
    start: float
    end: float = field(compare=False)
    btype: BlockType = field(compare=False)
    pairing_id: str | None = field(default=None, compare=False)
    reserve_call_type: str | None = field(default=None, compare=False)
    flight_mins: float = field(default=0.0, compare=False)

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

    def blocks_in(self, start: float, end: float) -> list[Block]:
        """Return all blocks that overlap the interval [start, end]."""
        # A block overlaps [start, end] if block.start < end and block.end > start
        # Find the first block that ends after `start`.
        # Since blocks are sorted by `start`, not `end`, we can't easily bisect on `end`.
        # But since blocks don't overlap with themselves in a valid calendar, 
        # we can just find the insertion point of `start` based on block.start, 
        # and step back by 1 to catch any block that started before `start` but ends after it.
        
        idx = bisect.bisect_right(self.calendar, start, key=lambda b: b.start)
        result = []
        
        # Check the block just before `start` in case it spans across `start`
        if idx > 0 and self.calendar[idx - 1].end > start:
            result.append(self.calendar[idx - 1])
            
        # Check all subsequent blocks that start before `end`
        for i in range(idx, len(self.calendar)):
            b = self.calendar[i]
            if b.start < end:
                result.append(b)
            else:
                break
                
        return result

    def get_rolling_counters(self, end_time: float, days: int) -> tuple[float, float]:
        """
        Calculate (duty_mins, flight_mins) in the rolling `days` prior to `end_time`.
        Accounts for partial overlap of blocks that cross the window boundaries.
        """
        window_start = end_time - (days * 24 * 60.0)
        duty_mins = 0.0
        flight_mins = 0.0
        
        # DUTY_BLOCKS as defined in legality.py
        duty_btypes = {
            BlockType.PAIRING, BlockType.RESERVE, BlockType.DRAFTED_DUTY, 
            BlockType.DEADHEAD, BlockType.SIMULATOR, BlockType.TRAINING
        }
        
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
