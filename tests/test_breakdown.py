from unittest.mock import patch, MagicMock
from breakdown import get_task_breakdown, _parse_steps, _fallback_steps

def test_fallback_steps_low_energy_has_three_steps():
    steps= _fallback_steps("Write essay", energy_level=1)
    assert len(steps) == 3

def test_fallback_steps_high_energy_has_four_steps():
    steps = _fallback_steps("Write essay", energy_level=4)
    assert len(steps) == 4

def test_parse_steps_valid_json():
    raw= '[{"step": 1, "action": "Open the file", "duration_mins": 5}]'
    steps = _parse_steps(raw)
    assert steps[0]["action"] == "Open the file"

def test_parse_steps_strips_markdown_fences():
    raw = '```json\n[{"step": 1, "action": "Do X", "duration_mins": 5}]\n```'
    steps = _parse_steps(raw)
    assert len(steps) == 1


@patch("breakdown._get_client")
def test_get_task_breakdown_uses_fallback_on_api_error(mock_get_client):
    mock_get_client.side_effect = Exception("API down")
    result = get_task_breakdown("Test task", None, 2, 25, energy_level=2)
    assert result["source"] == "fallback"
    assert len(result["steps"]) > 0
@patch("breakdown._get_client")
def test_get_task_breakdown_success(mock_get_client):
    # 1. Create fake client and sub-attributes
    mock_client= MagicMock()
    mock_response = MagicMock()
    
    # 2. Program the mock response to return fake JSON text when .text is accessed
    fake_json_payload = '[{"step": 1, "action": "Mocked Action", "duration_mins": 10}]'
    mock_response.text = fake_json_payload
    
    # 3. Chain them together: client.models.generate_content() returns our mock_response
    mock_get_client.return_value = mock_client
    mock_client.models.generate_content.return_value = mock_response

    # 4. Run the function
    result = get_task_breakdown("Test task", None, 2, 25, energy_level=3)

    # 5. Assertions
    assert result["source"] == "gemini"
    assert result["steps"][0]["action"] == "Mocked Action"
    # Verify that our code actually tried to talk to the model correctly
    mock_client.models.generate_content.assert_called_once()