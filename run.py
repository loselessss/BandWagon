#!/usr/bin/env pythonw
"""BandWagon 실행기 (콘솔 표시 — 디버그용).

이 폴더(run.pyw가 있는 곳) 안에 bandwagon 패키지 폴더가 함께 있으면
이 파일을 더블클릭하는 것만으로 실행됩니다. 위치를 옮기지 말고 폴더째로
이동/복사하세요.

콘솔이 없어도, 문제가 생기면 작은 오류 창을 띄워 원인을 보여줍니다.
"""
import sys, os, traceback

# 이 스크립트가 있는 폴더를 import 경로 맨 앞에 둔다 → 옆의 bandwagon 패키지를
# 작업 폴더와 무관하게 항상 찾는다.
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _show_error(title, msg):
    """콘솔이 없어도 오류를 보여준다. tkinter는 파이썬 표준 라이브러리라 별도
    설치가 필요 없다. 그래도 실패하면 stderr로라도 출력한다."""
    try:
        import tkinter
        from tkinter import messagebox
        root = tkinter.Tk(); root.withdraw()
        messagebox.showerror(title, msg)
        root.destroy()
    except Exception:
        pass
    print(f"[{title}] {msg}", file=sys.stderr)


def _run():
    try:
        from bandwagon.__main__ import main
    except ModuleNotFoundError as e:
        top = (e.name or "").split(".")[0]
        if top in ("PyQt5", "PIL", "numpy", "scipy", "cv2"):
            _show_error(
                "필요한 패키지가 없습니다",
                f"'{e.name}' 모듈을 찾을 수 없습니다.\n\n"
                "명령 프롬프트(cmd)에서 아래를 실행해 설치하세요:\n\n"
                "    pip install PyQt5 Pillow numpy scipy opencv-python")
        elif top == "bandwagon":
            _show_error(
                "bandwagon 폴더를 찾지 못했습니다",
                "run.pyw 와 같은 위치에 'bandwagon' 폴더가 있어야 합니다.\n\n"
                "폴더 구조:\n"
                "  BandWagon\\\n"
                "    ├─ run.pyw   ← 이 파일\n"
                "    └─ bandwagon\\  ← 패키지 폴더\n\n"
                f"현재 위치: {HERE}")
        else:
            _show_error("실행 오류", traceback.format_exc())
        return
    except Exception:
        _show_error("실행 오류 (불러오기 중)", traceback.format_exc())
        return

    try:
        main()
    except SystemExit:
        raise
    except Exception:
        _show_error("실행 오류 (실행 중)", traceback.format_exc())


if __name__ == "__main__":
    _run()
