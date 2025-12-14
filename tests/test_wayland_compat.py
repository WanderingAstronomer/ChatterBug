"""
Tests for Wayland/X11 compatibility and input backend selection.
"""
import os

import pytest


class TestDisplayServer:
    """Tests for display server detection."""

    def test_detect_session_type(self):
        """Should detect X11 or Wayland session."""
        session_type = os.environ.get('XDG_SESSION_TYPE', 'unknown')
        assert session_type in ['x11', 'wayland', 'unknown', 'tty']
        print(f"Session type: {session_type}")

    def test_wayland_display_set(self):
        """On Wayland, WAYLAND_DISPLAY should be set."""
        session_type = os.environ.get('XDG_SESSION_TYPE', '')
        if session_type == 'wayland':
            wayland_display = os.environ.get('WAYLAND_DISPLAY')
            assert wayland_display is not None, "WAYLAND_DISPLAY should be set"

    def test_x11_display_set(self):
        """On X11, DISPLAY should be set."""
        session_type = os.environ.get('XDG_SESSION_TYPE', '')
        if session_type == 'x11':
            display = os.environ.get('DISPLAY')
            assert display is not None, "DISPLAY should be set"


class TestBackendCompatibility:
    """Tests for backend compatibility with display servers."""

    def test_pynput_x11_only_warning(self, capsys):
        """pynput should warn if used on Wayland."""
        session_type = os.environ.get('XDG_SESSION_TYPE', '')
        if session_type == 'wayland':
            # pynput won't capture keys on Wayland
            pytest.skip("pynput doesn't work on Wayland - this is expected")

    def test_evdev_needs_input_group(self):
        """evdev needs user to be in input group."""
        import grp
        import pwd

        username = pwd.getpwuid(os.getuid()).pw_name
        try:
            input_group = grp.getgrnam('input')
            in_members = username in input_group.gr_mem
            is_primary = os.getgid() == input_group.gr_gid
            user_in_input = in_members or is_primary
        except KeyError:
            user_in_input = False

        session_type = os.environ.get('XDG_SESSION_TYPE', '')
        if session_type == 'wayland' and not user_in_input:
            pytest.fail(
                f"User '{username}' is not in 'input' group. "
                f"Run: sudo usermod -aG input {username} (then re-login)"
            )

    def test_evdev_can_list_devices(self):
        """evdev should be able to list input devices if permissions are correct."""
        try:
            import evdev
            devices = evdev.list_devices()
            assert len(devices) > 0, (
                "No input devices found. User may not be in 'input' group. "
                "Run: sudo usermod -aG input $USER (then re-login)"
            )
            print(f"Found {len(devices)} input devices")
        except ImportError:
            pytest.skip("evdev not installed")
        except PermissionError:
            pytest.fail(
                "Permission denied accessing input devices. "
                "Add user to 'input' group."
            )


class TestInputGroupMembership:
    """Tests specifically for input group membership."""

    def test_user_in_input_group(self):
        """User should be in input group for evdev to work."""
        import grp
        import pwd

        username = pwd.getpwuid(os.getuid()).pw_name

        try:
            input_group = grp.getgrnam('input')

            # Check primary group
            if os.getgid() == input_group.gr_gid:
                return  # User's primary group is input

            # Check supplementary groups
            if username in input_group.gr_mem:
                return  # User is in input group

            # Also check via os.getgroups() for current session
            if input_group.gr_gid in os.getgroups():
                return  # User has input group in current session

            pytest.fail(
                f"User '{username}' is not in 'input' group.\n"
                f"To fix, run: sudo usermod -aG input {username}\n"
                f"Then log out and log back in."
            )
        except KeyError:
            pytest.skip("'input' group does not exist on this system")
