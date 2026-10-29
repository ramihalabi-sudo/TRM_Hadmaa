"""Entry point of the frozen Windows application (PyInstaller).

freeze_support() must run first: the analyses start worker processes (analysis.Runner), which in a frozen
executable re-launch this file.  Without arguments the GUI starts; the command-line options of run_trm4.py work
as well (TRM_HADMAAv1.exe --cli 0 --out report.txt).
"""
import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()
    import run_trm4
    run_trm4.main()
