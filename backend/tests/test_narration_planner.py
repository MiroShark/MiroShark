from app.services.narration_planner import plan_narration


def test_plan_narration_creates_plain_english_script():
    infographic_plan = {
        "sequence": [
            {"slide_type": "overview", "title": "Should gas companies pay more tax?"},
            {"slide_type": "tax_context", "title": "Where government money comes from"},
            {"slide_type": "recommendation", "title": "Sensible middle path"},
        ]
    }

    script = plan_narration(infographic_plan, target_seconds=45)

    assert script["schema_version"] == "narration-script/v1"
    assert script["format"] == "short_video_narration"
    assert len(script["slides"]) == 3
    assert "Should gas companies pay more tax" in script["full_voiceover"]
    assert script["slides"][0]["duration_seconds"] >= 4
    assert script["tts_notes"]["provider_candidate"] == "k2-fsa/OmniVoice on Hugging Face Spaces"


def test_plan_narration_keeps_each_slide_beat_short_and_stitched():
    infographic_plan = {
        "sequence": [
            {"slide_type": "overview", "title": "Overview"},
            {"slide_type": "country_success_cases", "title": "Where it worked"},
            {"slide_type": "campaign_influence", "title": "Campaigns"},
            {"slide_type": "recommendation", "title": "Recommendation"},
        ]
    }

    script = plan_narration(infographic_plan, target_seconds=40)

    assert all(len(slide["voiceover"].split()) <= 14 for slide in script["slides"])
    assert script["full_voiceover"] == " ".join(slide["voiceover"] for slide in script["slides"])
