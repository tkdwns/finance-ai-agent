"""리포트 웹 대시보드 실행 스크립트.

사용법 (프로젝트 루트에서):
    python -m scripts.run_dashboard                  # http://127.0.0.1:5000
    python -m scripts.run_dashboard --port 8080
"""

import argparse

from src.web.dashboard import create_app


def main():
    parser = argparse.ArgumentParser(description="리포트 웹 대시보드 실행")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    app = create_app()
    print(f"대시보드 실행 중: http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
