"""``python -m scripts.dup_dataset <build|validate|import|probe|guide>``"""

import sys


def main() -> int:
    cmd, rest = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("", [])
    if cmd == "build":
        from . import build

        return build.main()
    if cmd == "validate":
        from . import validate

        sys.argv = [sys.argv[0], *rest]
        return validate.main()
    if cmd == "import":
        from . import importer

        return importer.main(rest)
    if cmd == "guide":
        from . import guide

        print(guide.write())
        return 0
    if cmd == "probe":
        from . import probe

        return probe.main(rest)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
