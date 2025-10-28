# filepath: app/__main__.py
import importlib
import sys

def _run():
    pkg = importlib.import_module(__package__ or "app")
    main = getattr(pkg, "main", None)
    if callable(main):
        argv = sys.argv[1:]
        try:
            return main(argv)
        except TypeError:
            return main()
    print("Package 'app' does not define a callable main(argv=None).", file=sys.stderr)
    return 2

if __name__ == "__main__":
    raise SystemExit(_run())