"""Dependency management commands for Vociferous.

This module provides explicit commands for checking and provisioning
engine dependencies and model weights, following the fail-loud principle.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from vociferous.config import load_config
from vociferous.domain.model import EngineKind

console = Console()


def _extract_package_name(package_spec: str) -> str:
    """Extract base package name from a package specification.
    
    Args:
        package_spec: Package spec like 'torch>=2.0.0' or 'pkg>=1.0,<2.0'
    
    Returns:
        Base package name without version specifiers
    """
    # Split on common version operators to extract package name
    for sep in [">=", "==", "<=", "!=", "~=", "<", ">", "["]:
        if sep in package_spec:
            return package_spec.split(sep)[0].strip()
    return package_spec.strip()


def _check_package_installed(package_name: str) -> tuple[bool, str | None]:
    """Check if a Python package is installed.
    
    Args:
        package_name: Package name (may include version specifier like 'torch>=2.0.0')
    
    Returns:
        Tuple of (is_installed, version_or_none)
    """
    # Extract base package name without version specifier
    base_name = _extract_package_name(package_name)
    
    try:
        mod = importlib.import_module(base_name)
        version = getattr(mod, "__version__", "unknown")
        return True, version
    except (ImportError, OSError, RuntimeError):
        # ImportError: not installed
        # OSError/RuntimeError: installed but broken (e.g., missing shared libraries)
        return False, None


def _get_engine_requirements(engine: str) -> tuple[list[str], list[dict[str, str]]]:
    """Get requirements for a specific engine without importing heavy dependencies.
    
    Note: Requirements are defined inline here rather than imported from engine modules
    to avoid triggering heavy imports (torch, transformers, etc.) which may fail if
    dependencies are missing. This is the whole point of the deps check command.
    
    Maintenance: When adding new engines or changing requirements, update both:
    1. Engine module metadata functions (required_packages, required_models)
    2. This function's inline definitions
    
    Args:
        engine: Engine name (e.g., 'canary_qwen', 'whisper_turbo')
    
    Returns:
        Tuple of (required_packages, required_models)
    """
    # Define requirements inline to avoid importing engine modules
    # which have heavy dependencies (torch, transformers, etc.)
    
    if engine == "canary_qwen":
        packages = ["transformers>=4.38.0", "torch>=2.0.0", "accelerate>=0.28.0"]
        models = [
            {
                "name": "nvidia/canary-qwen-2.5b",
                "repo_id": "nvidia/canary-qwen-2.5b",
                "description": "NVIDIA Canary-Qwen 2.5B ASR model (default)",
            }
        ]
    elif engine == "whisper_turbo":
        packages = ["faster-whisper>=1.0.0", "ctranslate2>=4.0.0"]
        models = [
            {
                "name": "Systran/faster-whisper-large-v3",
                "repo_id": "Systran/faster-whisper-large-v3",
                "description": "Faster-Whisper Large V3 model (default)",
            }
        ]
    else:
        packages = []
        models = []
    
    return packages, models


def _check_model_cached(model_name: str, cache_dir: Path) -> bool:
    """Check if a model is present in the cache directory.
    
    Args:
        model_name: Model name or repo ID
        cache_dir: Cache directory path
    
    Returns:
        True if model appears to be cached
    """
    if not cache_dir.exists():
        return False
    
    # Look for model directories or files matching the model name
    # This is a heuristic check - we look for any subdirectory that might contain the model
    model_slug = model_name.replace("/", "--")
    
    # Check for Hugging Face style cache structure
    hf_cache = cache_dir / "hub"
    if hf_cache.exists():
        # Look for model snapshot directories
        for item in hf_cache.iterdir():
            if model_slug in item.name:
                return True
    
    # Check for direct model directories
    for item in cache_dir.iterdir():
        if model_slug in item.name or model_name.split("/")[-1] in item.name:
            return True
    
    return False


def register_deps(app: typer.Typer) -> None:
    """Register the deps command and its subcommands."""
    
    deps_app = typer.Typer(
        help="Manage engine dependencies and model weights",
        no_args_is_help=True,
    )
    
    @deps_app.command("check")
    def check_cmd(
        engine: str = typer.Option(
            "canary_qwen",
            "--engine",
            "-e",
            help="Engine to check (canary_qwen, whisper_turbo)",
        ),
    ) -> None:
        """Check for missing Python dependencies and model weights.
        
        This command detects missing requirements and provides actionable
        installation commands. It does not modify your environment.
        
        Exit codes:
          0 - All dependencies present
          2 - Missing dependencies or models
        
        Examples:
          vociferous deps check
          vociferous deps check --engine whisper_turbo
        """
        config = load_config()
        cache_dir = Path(config.model_cache_dir).expanduser() if config.model_cache_dir else None
        
        # Get requirements for the engine
        packages, models = _get_engine_requirements(engine)
        
        if not packages and not models:
            console.print(
                Panel(
                    f"[yellow]No dependency metadata available for engine: {engine}[/yellow]",
                    title="Unknown Engine",
                    border_style="yellow",
                )
            )
            raise typer.Exit(code=0)
        
        # Check packages
        missing_packages: list[str] = []
        installed_packages: list[tuple[str, str]] = []
        
        for pkg in packages:
            is_installed, version = _check_package_installed(pkg)
            if is_installed:
                installed_packages.append((_extract_package_name(pkg), version or "unknown"))
            else:
                missing_packages.append(pkg)
        
        # Check models
        missing_models: list[dict[str, str]] = []
        cached_models: list[str] = []
        
        if cache_dir:
            for model in models:
                model_name = model.get("name", "")
                if _check_model_cached(model_name, cache_dir):
                    cached_models.append(model_name)
                else:
                    missing_models.append(model)
        else:
            missing_models = models  # All models are "missing" if no cache configured
        
        # Build status table
        table = Table(title=f"Dependency Check: {engine}", show_header=True, header_style="bold cyan")
        table.add_column("Component", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Details", style="dim")
        
        # Add package rows
        for pkg_name, version in installed_packages:
            table.add_row(pkg_name, "[green]OK[/green]", f"v{version}")
        
        for pkg in missing_packages:
            pkg_name = _extract_package_name(pkg)
            table.add_row(pkg_name, "[red]MISSING[/red]", pkg)
        
        # Add model rows
        for model_name in cached_models:
            table.add_row(f"Model: {model_name.split('/')[-1]}", "[green]CACHED[/green]", model_name)
        
        for model in missing_models:
            model_name = model.get("name", "unknown")
            table.add_row(
                f"Model: {model_name.split('/')[-1]}", 
                "[yellow]NOT CACHED[/yellow]", 
                model.get("description", model_name)
            )
        
        console.print(table)
        
        # Show action steps if anything is missing
        if missing_packages or missing_models:
            action_text = "[bold]Actions needed:[/bold]\n\n"
            
            if missing_packages:
                pkg_list = " ".join(f'"{pkg}"' for pkg in missing_packages)
                action_text += f"[cyan]Install packages:[/cyan]\n  pip install {pkg_list}\n\n"
            
            if missing_models:
                if cache_dir:
                    action_text += f"[cyan]Model cache:[/cyan] {cache_dir}\n"
                else:
                    action_text += "[yellow]Model cache:[/yellow] Not configured\n"
                action_text += "[dim]Models will be downloaded automatically on first use.[/dim]\n"
            
            console.print()
            console.print(
                Panel(
                    action_text.strip(),
                    title="Missing Dependencies",
                    border_style="yellow",
                )
            )
            
            raise typer.Exit(code=2)
        else:
            console.print()
            console.print("[bold green]✓ All dependencies satisfied[/bold green]")
            raise typer.Exit(code=0)
    
    # Mark as developer-tier command
    check_cmd.dev_only = True  # type: ignore[attr-defined]
    
    app.add_typer(deps_app, name="deps", rich_help_panel="Utilities")
