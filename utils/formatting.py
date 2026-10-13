from datetime import datetime, timezone

def discord_time(iso_string):
    expiry_dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    
    # Calculate the remaining time difference
    diff = expiry_dt - now
    total_seconds = int(diff.total_seconds())
    
    # Handle already expired items gracefully
    if total_seconds <= 0:
        return "종료됨"
        
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    
    # Build a clean readable string
    parts = []
    if hours > 0:
        parts.append(f"{hours}시간")
    if minutes > 0 or hours == 0:
        parts.append(f"{minutes}분")
        
    return f"{' '.join(parts)} 남음"

def is_expired(expiry_str: str) -> bool:
    expiry_dt = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))

    return datetime.now(timezone.utc) > expiry_dt
