from enum import Enum
from dataclasses import dataclass, field
import bisect

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

@dataclass
class CrewMember:
    crew_id: str
    base: str
    fleet_quals: set[str]
    position: str
    seniority: int
    calendar: list[Block] = field(default_factory=list)

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
