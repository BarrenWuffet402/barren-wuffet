import os
import json
from datetime import datetime

KILLSWITCH_FILE = os.path.expanduser("~/barren-wuffet/KILLSWITCH")

def is_killed() -> bool:
    """Check if kill switch is active."""
    return os.path.exists(KILLSWITCH_FILE)

def kill():
    """Activate kill switch — halts all Barren activity."""
    with open(KILLSWITCH_FILE, "w") as f:
        json.dump({
            "activated": datetime.now().isoformat(),
            "reason": "Manual kill switch activated"
        }, f)
    print("🛑 KILL SWITCH ACTIVATED — Barren is stopped.")

def revive():
    """Deactivate kill switch — resumes Barren activity."""
    if os.path.exists(KILLSWITCH_FILE):
        os.remove(KILLSWITCH_FILE)
        print("✅ Kill switch cleared — Barren is back online.")
    else:
        print("ℹ️  Kill switch was not active.")

def check_message_for_killswitch(message: str) -> bool:
    """
    Call this on every incoming message.
    Returns True if kill switch was triggered.
    """
    if "STOP ALL IMMEDIATELY" in message.upper():
        kill()
        return True
    return False

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        status = "🛑 KILLED" if is_killed() else "✅ ACTIVE"
        print(f"Barren status: {status}")
    elif sys.argv[1] == "kill":
        kill()
    elif sys.argv[1] == "revive":
        revive()
    elif sys.argv[1] == "status":
        status = "🛑 KILLED" if is_killed() else "✅ ACTIVE"
        print(f"Barren status: {status}")