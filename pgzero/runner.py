from . import storage
from . import clock
from . import loaders
from .game import PGZeroGame, DISPLAY_FLAGS
from types import ModuleType
from optparse import OptionParser
import warnings
import sys
import os
import pygame
pygame.mixer.pre_init(frequency=22050, size=-16, channels=2)
pygame.init()


def _check_python_ok_for_pygame():
    """If we're on a Mac, is this a full Framework python?

    There is a problem with PyGame on Macs running in a virtual env.
    If the Python used is from the venv, it will not allow full window and
    keyboard interaction. Instead, we need the original framework Python
    to get PyGame working properly.

    The problem doesn't occur on Linux and Windows.
    """
    if sys.platform == 'darwin':  # This is a Mac
        return 'Library/Frameworks' in sys.executable
    else:
        return True


def _substitute_full_framework_python():
    """Need to change the OS/X Python executable to the full Mac version,
    while maintaining the virtualenv environment, so things still run
    in an encapsulated way.

    We do this by extract the paths that virtualenv has added to the system
    path, and prefixing them to the current PYTHONPATH.

    Then we use os.execv() to start a replacement process that uses the
    same environment as the previous one.
    """
    PYVER = '{}.{}'.format(*sys.version_info[:2])
    base_fw = '/Library/Frameworks/Python.framework/Versions/'
    framework_python = base_fw + '{pv}/bin/python{pv}'.format(pv=PYVER)
    venv_base = os.environ.get('VIRTUAL_ENV')
    if not venv_base or not os.path.exists(framework_python):
        # Do nothing if virtual env hasn't been set up or if we can't
        # find the framework Python interpreter
        return
    venv_paths = [p for p in sys.path if p.startswith(venv_base)]
    # Need to allow for PYTHONPATH not already existing in environment
    os.environ['PYTHONPATH'] = ':'.join(venv_paths + [
        os.environ.get('PYTHONPATH', '')]).rstrip(':')
    # Pass command line args to the new process
    os.execv(framework_python, ['python', '-m', 'pgzero'] + sys.argv[1:])


def main():

    # Pygame won't run from a normal virtualenv copy of Python on a Mac
    if not _check_python_ok_for_pygame():
        _substitute_full_framework_python()

    parser = OptionParser()
    options, args = parser.parse_args()

    if len(args) != 1:
        parser.error("You must specify which module to run.")

    if __debug__:
        warnings.simplefilter('default', DeprecationWarning)
    path = path = args[0]
    load_and_run(path)


def load_and_run(path):
    """Load and run the given Python file as the main PGZero game module.

    Note that the 'import pgzrun' IDE mode doesn't pass through this entry
    point, as the module is already loaded.

    """
    with open(path, 'rb') as f:
        src = f.read()

    code = compile(src, os.path.basename(path), 'exec', dont_inherit=True)

    name, _ = os.path.splitext(os.path.basename(path))
    mod = ModuleType(name)
    mod.__file__ = path
    mod.__name__ = name
    sys.modules[name] = mod

    # Indicate that we're running with the pgzrun runner
    # This disables the 'import pgzrun' module
    sys._pgzrun = True

    prepare_mod(mod)
    exec(code, mod.__dict__)

    pygame.display.init()
    try:
        run_mod(mod)
    finally:
        # Clean some of the state we created, useful in testing
        pygame.display.quit()
        clock.clock.clear()
        del sys.modules[name]


def prepare_mod(mod):
    """Prepare to execute the module code for Pygame Zero.

    To allow the module to load assets, we configure the loader path to
    load relative to the module's __file__ path.

    When executing the module some things need to already exist:

    * Our extra builtins need to be defined (by copying them into Python's
      `builtins` module)
    * A screen needs to be created (because we use convert_alpha() to convert
      Sprite surfaces for blitting to the screen).

    """
    storage.storage._set_filename_from_path(mod.__file__)
    loaders.set_root(mod.__file__)

    # An icon needs to exist before the window is created.
    PGZeroGame.show_default_icon()
    pygame.display.set_mode((100, 100), DISPLAY_FLAGS)

    # Copy pgzero builtins into system builtins
    from . import builtins as pgzero_builtins
    import builtins as python_builtins
    for k, v in vars(pgzero_builtins).items():
        python_builtins.__dict__.setdefault(k, v)


def run_mod(mod):
    """Run the module."""
    PGZeroGame(mod).run()
