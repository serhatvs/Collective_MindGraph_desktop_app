from array import array

from collective_mindgraph_desktop.audio_capture import AutoStopConfig, SilenceWindowTracker, _read_incremental_pcm_level


def test_silence_window_tracker_requires_speech_before_auto_stop():
    tracker = SilenceWindowTracker(
        AutoStopConfig(
            min_speech_seconds=0.3,
            silence_seconds=1.0,
            silence_threshold=0.01,
        )
    )

    assert tracker.observe(0.0, 0.5) is False
    assert tracker.heard_speech is False

    assert tracker.observe(0.02, 0.2) is False
    assert tracker.heard_speech is False
    assert tracker.observe(0.02, 0.2) is False
    assert tracker.heard_speech is True

    assert tracker.observe(0.0, 0.4) is False
    assert tracker.observe(0.0, 0.7) is True


def test_read_incremental_pcm_level_reads_only_new_samples(tmp_path):
    audio_path = tmp_path / "sample.wav"
    header = b"RIFF" + b"\x00" * 40
    samples = array("h", [0, 0, 12000, 12000, 0, 0])
    audio_path.write_bytes(header + samples.tobytes())

    rms_level, duration_seconds, consumed_bytes = _read_incremental_pcm_level(audio_path, byte_offset=0)

    assert rms_level > 0.0
    assert round(duration_seconds, 6) == round(len(samples) / 16000.0, 6)
    assert consumed_bytes == len(samples) * 2

    next_rms, next_duration, next_consumed = _read_incremental_pcm_level(audio_path, byte_offset=consumed_bytes)

    assert next_rms == 0.0
    assert next_duration == 0.0
    assert next_consumed == 0
