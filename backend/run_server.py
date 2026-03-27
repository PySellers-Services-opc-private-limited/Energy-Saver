#!/usr/bin/env python3
"""
Energy Saver AI Backend Server.

This module starts the FastAPI backend server using Uvicorn.

Example:
    Run with default settings:
        $ python backend/run_server.py

    Run with custom settings:
        $ python backend/run_server.py --host localhost --port 8080 --reload

    Run with multiple workers:
        $ python backend/run_server.py --workers 4
"""

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import uvicorn


# ============================================================================
# Path Setup
# ============================================================================

_HERE = Path(__file__).parent.resolve()
_ROOT = _HERE.parent
_BACKEND_DIR = str(_HERE)

# Ensure project root is on the path
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


# ============================================================================
# Logging Setup
# ============================================================================

def _setup_logging(log_level: str = "info") -> logging.Logger:
    """Configure logging for the application.
    
    Args:
        log_level: Logging level (debug, info, warning, error, critical).
    
    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger("energy_saver_ai")
    logger.setLevel(log_level.upper())
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger


logger = _setup_logging()


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class ServerConfig:
    """Configuration for the Uvicorn server.
    
    Attributes:
        host: Bind address for the server.
        port: Port number for the server.
        reload: Enable auto-reload on file changes (dev mode).
        workers: Number of worker processes.
        log_level: Logging level for the server.
    """
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    workers: int = 1
    log_level: str = "info"
    
    @property
    def effective_workers(self) -> int:
        """Get the effective number of workers.
        
        When reload is enabled, only 1 worker is used (best practice for dev mode).
        
        Returns:
            Effective number of workers.
        """
        return 1 if self.reload else self.workers


# ============================================================================
# Argument Parsing
# ============================================================================

def _parse_arguments() -> ServerConfig:
    """Parse command-line arguments and return server configuration.
    
    Returns:
        ServerConfig instance with parsed arguments.
    
    Raises:
        SystemExit: If argument parsing fails.
    """
    parser = argparse.ArgumentParser(
        description="Energy Saver AI Backend API Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example: python backend/run_server.py --port 8080 --reload",
    )
    
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Bind host address (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Bind port number (default: 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on file changes (dev mode)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)",
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error", "critical"],
        default="info",
        help="Logging level (default: info)",
    )
    
    args = parser.parse_args()
    
    return ServerConfig(
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers,
        log_level=args.log_level,
    )


# ============================================================================
# Server Start
# ============================================================================

def _start_server(config: ServerConfig) -> None:
    """Start the Uvicorn server with the given configuration.
    
    Args:
        config: ServerConfig instance with server settings.
    
    Raises:
        Exception: If server startup fails.
    """
    logger.info("Starting Energy Saver AI Backend Server")
    logger.info(f"Configuration: host={config.host}, port={config.port}")
    logger.info(f"Reload: {config.reload}, Workers: {config.effective_workers}")
    
    try:
        uvicorn.run(
            "app.main:app",
            host=config.host,
            port=config.port,
            reload=config.reload,
            workers=config.effective_workers,
            app_dir=_BACKEND_DIR,
            log_level=config.log_level,
        )
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        raise


# ============================================================================
# Main Entry Point
# ============================================================================

def main() -> None:
    """Main entry point for the application."""
    config = _parse_arguments()
    _start_server(config)


if __name__ == "__main__":
    main()
