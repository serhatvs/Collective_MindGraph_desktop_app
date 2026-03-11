from collective_mindgraph_desktop.voice_command import VoiceCommandWorkflow


def test_voice_command_workflow_reaches_transcript_ready_state():
    workflow = VoiceCommandWorkflow()
    audio_path = "C:/tmp/voice_command_001.wav"

    assert workflow.state.stage == "idle"
    assert workflow.state.start_enabled is True
    assert workflow.state.transcribe_enabled is False

    recording_state = workflow.start_recording()
    assert recording_state.stage == "recording"
    assert recording_state.stop_enabled is True
    assert recording_state.transcript_text == ""
    assert recording_state.audio_path is None

    audio_ready_state = workflow.stop_recording(audio_path)
    assert audio_ready_state.stage == "audio_ready"
    assert audio_ready_state.audio_path == audio_path
    assert audio_ready_state.transcribe_enabled is True

    transcribing_state = workflow.transcribe()
    assert transcribing_state.stage == "transcribing"
    assert "local transcription backend" in transcribing_state.guidance_text
    assert transcribing_state.transcript_text == ""

    transcript_ready_state = workflow.complete_transcription("recognized speech")
    assert transcript_ready_state.stage == "transcript_ready"
    assert transcript_ready_state.transcript_text == "recognized speech"


def test_voice_command_workflow_invalid_transitions_are_noops():
    workflow = VoiceCommandWorkflow()

    idle_state = workflow.state
    assert workflow.stop_recording() == idle_state
    assert workflow.transcribe() == idle_state

    workflow.start_recording()
    workflow.clear()

    assert workflow.state.stage == "idle"
    assert workflow.state.clear_enabled is False


def test_voice_command_workflow_exposes_error_state_and_recovery():
    workflow = VoiceCommandWorkflow()

    error_state = workflow.set_error("No microphone input device is available.", "C:/tmp/audio.wav")
    assert error_state.stage == "error"
    assert error_state.start_enabled is True
    assert error_state.transcribe_enabled is True

    restarted_state = workflow.start_recording()
    assert restarted_state.stage == "recording"
