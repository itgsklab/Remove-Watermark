import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from wmrm.desktop import main

    raise SystemExit(main())
