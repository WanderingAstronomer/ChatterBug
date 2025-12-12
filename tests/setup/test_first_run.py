"""Tests for first-run setup module."""



class TestFirstRunState:
    """Tests for first-run state management."""

    def test_is_first_run_true_when_marker_missing(self, tmp_path):
        """is_first_run should return True when marker file doesn't exist."""
        from vociferous.setup import first_run
        
        # Temporarily override the cache dir
        original_marker = first_run.SETUP_MARKER
        first_run.SETUP_MARKER = tmp_path / ".setup_complete"
        
        try:
            assert first_run.is_first_run() is True
        finally:
            first_run.SETUP_MARKER = original_marker

    def test_is_first_run_false_when_marker_exists(self, tmp_path):
        """is_first_run should return False when marker file exists."""
        from vociferous.setup import first_run
        
        marker = tmp_path / ".setup_complete"
        marker.touch()
        
        original_marker = first_run.SETUP_MARKER
        first_run.SETUP_MARKER = marker
        
        try:
            assert first_run.is_first_run() is False
        finally:
            first_run.SETUP_MARKER = original_marker

    def test_mark_setup_complete_creates_marker(self, tmp_path):
        """mark_setup_complete should create the marker file."""
        from vociferous.setup import first_run
        
        cache_dir = tmp_path / "cache"
        marker = cache_dir / ".setup_complete"
        
        original_cache = first_run.CACHE_DIR
        original_marker = first_run.SETUP_MARKER
        first_run.CACHE_DIR = cache_dir
        first_run.SETUP_MARKER = marker
        
        try:
            assert not marker.exists()
            first_run.mark_setup_complete()
            assert marker.exists()
        finally:
            first_run.CACHE_DIR = original_cache
            first_run.SETUP_MARKER = original_marker

    def test_reset_setup_state_removes_marker(self, tmp_path):
        """reset_setup_state should remove the marker file."""
        from vociferous.setup import first_run
        
        marker = tmp_path / ".setup_complete"
        marker.touch()
        
        original_marker = first_run.SETUP_MARKER
        first_run.SETUP_MARKER = marker
        
        try:
            assert marker.exists()
            first_run.reset_setup_state()
            assert not marker.exists()
        finally:
            first_run.SETUP_MARKER = original_marker


class TestFirstRunManager:
    """Tests for FirstRunManager class."""

    def test_is_first_run_delegates_to_module_function(self, tmp_path):
        """Manager.is_first_run should use module-level function."""
        from vociferous.setup import first_run
        from vociferous.setup.first_run import FirstRunManager
        
        marker = tmp_path / ".setup_complete"
        original_marker = first_run.SETUP_MARKER
        first_run.SETUP_MARKER = marker
        
        try:
            manager = FirstRunManager(cache_dir=tmp_path)
            assert manager.is_first_run() is True
            
            marker.touch()
            assert manager.is_first_run() is False
        finally:
            first_run.SETUP_MARKER = original_marker

    def test_check_dependencies_returns_dict(self):
        """_check_dependencies should return a dict with expected keys."""
        from vociferous.setup.first_run import FirstRunManager
        
        manager = FirstRunManager()
        result = manager._check_dependencies()
        
        assert isinstance(result, dict)
        assert "ffmpeg" in result
        assert "cuda" in result
        assert "python_version" in result
        assert isinstance(result["ffmpeg"], bool)
        assert isinstance(result["cuda"], bool)

    def test_check_gpu_returns_dict(self):
        """_check_gpu should return a dict with GPU info."""
        from vociferous.setup.first_run import FirstRunManager
        
        manager = FirstRunManager()
        result = manager._check_gpu()
        
        assert isinstance(result, dict)
        assert "available" in result
        assert "name" in result
        assert "memory_gb" in result
        assert isinstance(result["available"], bool)

    def test_run_first_time_setup_with_skips(self, tmp_path):
        """Setup should complete with all steps skipped."""
        from vociferous.setup import first_run
        from vociferous.setup.first_run import FirstRunManager
        
        cache_dir = tmp_path / "cache"
        marker = cache_dir / ".setup_complete"
        
        original_cache = first_run.CACHE_DIR
        original_marker = first_run.SETUP_MARKER
        first_run.CACHE_DIR = cache_dir
        first_run.SETUP_MARKER = marker
        
        try:
            manager = FirstRunManager(cache_dir=cache_dir)
            
            # Run with all expensive steps skipped
            result = manager.run_first_time_setup(
                skip_model_download=True,
                skip_warmup=True,
            )
            
            assert result is True
            assert marker.exists()  # Marker should be created
        finally:
            first_run.CACHE_DIR = original_cache
            first_run.SETUP_MARKER = original_marker


class TestEnsureSetupComplete:
    """Tests for the ensure_setup_complete convenience function."""

    def test_skips_when_already_complete(self, tmp_path):
        """Should skip setup when marker exists and skip_if_complete=True."""
        from vociferous.setup import first_run
        from vociferous.setup.first_run import ensure_setup_complete
        
        marker = tmp_path / ".setup_complete"
        marker.touch()
        
        original_marker = first_run.SETUP_MARKER
        first_run.SETUP_MARKER = marker
        
        try:
            result = ensure_setup_complete(skip_if_complete=True)
            assert result is True
        finally:
            first_run.SETUP_MARKER = original_marker

    def test_runs_setup_when_not_complete(self, tmp_path):
        """Should run setup when marker doesn't exist."""
        from vociferous.setup import first_run
        from vociferous.setup.first_run import ensure_setup_complete
        
        cache_dir = tmp_path / "cache"
        marker = cache_dir / ".setup_complete"
        
        original_cache = first_run.CACHE_DIR
        original_marker = first_run.SETUP_MARKER
        first_run.CACHE_DIR = cache_dir
        first_run.SETUP_MARKER = marker
        
        try:
            result = ensure_setup_complete(
                skip_if_complete=True,
                skip_model_download=True,
                skip_warmup=True,
            )
            
            assert result is True
            assert marker.exists()
        finally:
            first_run.CACHE_DIR = original_cache
            first_run.SETUP_MARKER = original_marker
