# scheduled_outages.py
#
# Step 5: Scheduled outage handling.
#
# The department publishes planned maintenance/load-shedding windows. If a
# pole is dark BECAUSE of one of these, it must NOT generate a fault ticket.
#
# Real-world caveat from the assignment: shutdowns overrun by 20-40 minutes
# routinely, and ~1 in 10 is cancelled without the feed being updated. So we
# treat the published window with a grace buffer rather than trusting it to
# the minute - being too strict here means we'd miss real faults that
# happen to start right as a scheduled window "should" have ended.

from datetime import datetime, timedelta, timezone

GRACE_MINUTES = 45  # covers the stated 20-40 min overrun with a small margin


class ScheduledOutageRegistry:
    def __init__(self):
        # In a real system this would be fetched from the department's API
        # (GET /scheduled-outages). Mocked here as an in-memory list.
        self.outages = []

    def load(self, outages):
        """outages: list of dicts with scope ('feeder'|'dt'), target_id, start, end (ISO strings)"""
        self.outages = outages

    def is_covered(self, target_id, scope, at_time=None):
        """
        Returns True if target_id (a dt_id or feeder_id, matching `scope`)
        is inside a scheduled outage window right now, including the grace
        buffer on the end time.
        """
        if at_time is None:
            at_time = datetime.now(timezone.utc)

        for outage in self.outages:
            if outage["scope"] != scope or outage["target_id"] != target_id:
                continue

            start = datetime.fromisoformat(outage["start"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(outage["end"].replace("Z", "+00:00"))
            end_with_grace = end + timedelta(minutes=GRACE_MINUTES)

            if start <= at_time <= end_with_grace:
                return True

        return False
