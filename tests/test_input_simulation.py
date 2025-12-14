"""
Tests for input simulation (text injection).
"""


class TestInputSimulator:
    """Tests for InputSimulator class."""

    def test_input_simulator_initializes(self, config_manager):
        """InputSimulator should initialize without error."""
        from input_simulation import InputSimulator

        sim = InputSimulator()
        assert sim is not None
        assert sim.input_method in ['pynput', 'ydotool', 'dotool']
        sim.cleanup()

    def test_typewrite_empty_string(self, config_manager):
        """Typing empty string should not crash."""
        from input_simulation import InputSimulator

        sim = InputSimulator()
        # Should not raise
        sim.typewrite("")
        sim.typewrite(None)  # Should handle None gracefully
        sim.cleanup()

    def test_cleanup_can_be_called_multiple_times(self, config_manager):
        """Cleanup should be safe to call multiple times."""
        from input_simulation import InputSimulator

        sim = InputSimulator()
        sim.cleanup()
        sim.cleanup()  # Should not raise
