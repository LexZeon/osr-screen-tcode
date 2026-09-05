import sys


if __name__ == "__main__":
    from osr_screen_tcode.gpu_runtime import run_background_command

    if run_background_command(sys.argv[1:]):
        raise SystemExit(0)
    from osr_screen_tcode.app import main

    main()
