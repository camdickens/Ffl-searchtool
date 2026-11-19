import os
import runpy

# Entry point shim: the real app lives in app.py
runpy.run_path(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py"),
    run_name="__main__",
)
