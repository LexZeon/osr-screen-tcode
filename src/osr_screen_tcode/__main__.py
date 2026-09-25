import sys


if __name__ == "__main__":
    from osr_screen_tcode.runtime_check import run_runtime_check

    run_runtime_check(sys.argv[1:])
    from osr_screen_tcode.preview_lab_launcher import run_preview_lab

    if run_preview_lab(sys.argv[1:]):
        raise SystemExit(0)
    from osr_screen_tcode.gpu_runtime import run_background_command

    if run_background_command(sys.argv[1:]):
        raise SystemExit(0)
    from osr_screen_tcode.app import main

    main()
