"""RE-PLAN-V Main Entry Point.

Supports running the API server or CLI execution for research benchmarks.
"""

from __future__ import annotations

import argparse
import sys
from configs.default import default_config
from core.logger import get_logger

logger = get_logger("replan_v_main")


def main() -> int:
    parser = argparse.ArgumentParser(description="RE-PLAN-V Research & Demo Platform")
    parser.add_argument("--mode", choices=["server", "cli", "benchmark"], default="cli", help="Execution mode")
    parser.add_argument("--host", default=default_config.app.host, help="Server host")
    parser.add_argument("--port", type=int, default=default_config.app.port, help="Server port")
    parser.add_argument("--algorithm", choices=["A*", "BFS", "BEST_FIRST"], default="A*", help="Planning algorithm")
    
    args = parser.parse_args()
    logger.info("Initializing RE-PLAN-V Platform", extra_data={"mode": args.mode, "algorithm": args.algorithm})
    
    if args.mode == "server":
        import uvicorn
        logger.info(f"Starting RE-PLAN-V API Server on {args.host}:{args.port}")
        uvicorn.run("app.main:create_app", host=args.host, port=args.port, reload=default_config.app.debug, factory=True)
    elif args.mode == "cli":
        print("RE-PLAN-V Symbolic Core CLI Ready.")
        print(f"Default Algorithm: {args.algorithm}")
    elif args.mode == "benchmark":
        print("Benchmark mode placeholder.")
        
    return 0


def create_app():
    from fastapi import FastAPI
    app = FastAPI(title=default_config.app.title)
    
    @app.get("/health")
    def health():
        return {"status": "ok", "app": "RE-PLAN-V"}
        
    return app


if __name__ == "__main__":
    sys.exit(main())
