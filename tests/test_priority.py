# tests/test_priority.py
import pytest
from datetime import date, timedelta
from priority import compute_priority_score,days_until

def test_days_until_no_deadline():
    assert days_until(None)== 999

def test_days_until_future_date():
    future= (date.today()+ timedelta(days=5)).isoformat()
    assert days_until(future)== 5

def test_urgency_due_today_is_high():
    task= {"priority": 2, "deadline":date.today().isoformat(),"estimate_mins": 25}
    score= compute_priority_score(task, energy_level=3)
    assert score > 0.4  # urgency more when due today

def test_urgency_far_future_is_low():
    far= (date.today() + timedelta(days=30)).isoformat()
    task = {"priority": 2, "deadline": far, "estimate_mins": 25}
    score= compute_priority_score(task, energy_level=3)
    assert score < 0.5

def test_energy_penalises_heavy_task_when_exhausted():
    task= {"priority": 2, "deadline": None, "estimate_mins": 90}
    low_energy_score = compute_priority_score(task, energy_level=1)
    high_energy_score = compute_priority_score(task, energy_level=5)
    assert high_energy_score > low_energy_score

@pytest.mark.parametrize("priority,expected_low_bound", [(1, 0.0), (2, 0.3), (3, 0.6)])
def test_importance_scales_with_priority(priority, expected_low_bound):
    task= {"priority": priority, "deadline": None, "estimate_mins": 25}
    score = compute_priority_score(task, energy_level=3)
    assert score >= expected_low_bound