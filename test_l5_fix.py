from crewsim.engine.state import CrewMember, Block, BlockType, OpenTimeItem
from crewsim.engine.legality import check_l5_duty_free_day

c = CrewMember("C1", "YUL", {"A330"}, "CA", 1, [
    Block(start=0, end=7*24*60 + 60, btype=BlockType.PAIRING) # 7 days and 1 hour
])

item = OpenTimeItem(uid=1, pairing_id="P1", base="YUL", fleet="A330", position="CA", start=20*24*60, end=20*24*60 + 120, deadline=0, origin="SICK_CALL", root_event_uid=1, flight_mins=0.0)

print(check_l5_duty_free_day(c, item))
