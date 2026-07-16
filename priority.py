from datetime import date
import math

def days_until(deadline):
    """
    Returns days from today until deadline (negative if overdue, 999 if no deadline).
    Accepts either a date object or a 'YYYY-MM-DD' string.
    """
    if deadline is None:
        return 999  # treat no deadline as far in the future

    if isinstance(deadline, str):
        year, month, day = map(int, deadline.split("-"))
        deadline = date(year, month, day)

    return (deadline - date.today()).days


def compute_priority_score(task, energy_level=3):
    """ 
    score(t)= (0.50 x U)+ (0.35 x I ) + (0.15 x E)
   
    penalty = keyword_penalty(task.get("title", ""))
    score = score * penalty

    return round(score, 4)
    
    U- Urgency: exponential decay on days remaining
    I- Importance: user priority (1-3) normalised to 0.0-1.0
    E- Energy Fit: today's energy (1-5) vs task size
    """

    # =====Semantic penalty layer =======
LOW_VALUE_KEYWORDS= {
    "sleep", "nap", "rest", "play"
    "travel", "commute", "drive","cycle","skating", "stroll", "walk"
    "tv", "netflix","movie", "cinema", "theater", "youtube", "watch", "radio", "entertain"
    "chat", "gossip", "call friend","hairdresser","barber","pedicure","manicure", 
    "social media", "instagram", "tiktok", "facebook", "twitter", "x","Tinder", 
    "scroll", "browse", "game", "gaming",
}

def keyword_penalty(title: str) -> float:
    """
    Return a penalty multiplier (0-1) based on task title content.
    Leisure/low-value activities are capped so they can never
    dominate the Top 3, regardless of deadline or priority set.
    """
    if not title:
        return 1.0

    lowered = title.lower()
    for keyword in LOW_VALUE_KEYWORDS:
        if keyword in lowered:
            return 0.25  # heavily discount, but don't fully hide the task
    return 1.0
    
    # ======U: Urgency via exponential decay ===
    
    deadline = task.get("deadline")

    if deadline is None:
        U = 0.50 # neutral for no-deadline tasks
    else:
        days_remaining = max(0, days_until(deadline))
        U = math.exp(-0.15 * days_remaining)
    # === I: importance
    priority = task.get("priority", 2)
    I = (priority -1) / 2
    
    #==== E: Energy Fit e.g High ener + big task is fine but not low ener + Low task ====
    energy_norm = ( energy_level - 1) / 4 # eg. 1 = 0 , 3 = 0.5, 5 =1
    est = task.get("estimate_mins") or 25
    if est <= 25:
        task_weight = 0.2 # quick task: suits all energy levels
    elif est <= 60:
        task_weight = 0.5
    else:
        task_weight = 1.0 # heavy task : needs high energy 
    # E is high when energy matches  task weight
    E = 1.0 - abs(energy_norm- task_weight)

    score = (0.50 * U) + (0.35 * I) + (0.15 * E)
    penalty = keyword_penalty(task.get("title", ""))
    score = score * penalty

    return round(score, 4)