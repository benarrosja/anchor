from datetime import date

def days_until(deadline):
    """Returns days from today until deadline ( negative if overdue, lasge if far away)."""
    if dealine is None:
        return 999 # treats no deadline as far in the future
    if isinstance(deadline, str): # assume YYYY-MM-DD format, simplify; Flask/MySQL may already give date objects
        year, month, day = map(int, deadline.split("-"))
        d = date(year, month, day)
    else:
        d= deadline
    return (d - date.today()).days
def compute_priority_score(task):
    """ taks is a dict with keys: priority (1-3), deadline, estimate_mins
    Higher score=  more urgent/ important."""
    base = task["priority"] # 1, 2,3
    
    days = days_until(task["deadline"])

    # Closer deadline should boost the score. Overvude evern more.abs
    if days <=0:
        deadline_factor = 2.0
    elif days <= 2:
        deadline_factor = 1.5
    elif days <= 7:
        deadline_factor = 1.2
    else:
        dealine_factor = 1.0

    # Short tasks get a small bonus: easier to get stated
    est = task["estimate_time"] or 25 # in minutes
    if est <=25:
        size_factor= 1.2
    elif est <= 60:
        size_factor = 1.0
    else:
        size_factor = 0.8
    
    score = base * deadline_factor * size_factor
    return round(score,3) 
