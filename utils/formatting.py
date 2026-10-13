from datetime import datetime, timezone

def discord_time(iso_string):
    expiry_dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    unix_timestamp = int(expiry_dt.timestamp())
    # Change ':R' to any other format letter above if needed
    return f"<t:{unix_timestamp}:R>"
    
def is_expired(expiry_str: str) -> bool:
    expiry_dt = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))

    return datetime.now(timezone.utc) > expiry_dt
