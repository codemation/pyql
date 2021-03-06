#!/usr/bin/env python
if __name__=='__main__':
    import os, sys
    #Check for bin path - install in venv/bin/ if active - else /usr/bin/
    env = sys.prefix
    version = f'python{sys.version_info[0]}.{sys.version_info[1]}'
    installDir = f'{env}/lib/{version}/pyql'
    if 'install' in sys.argv:
        try:
            os.makedirs(installDir)
            os.system(f'cp pyql/*.py README.md {installDir}')
            print("pyql successfully installed - see https://github.com/codemation/pyql for usage")
        except Exception as e:
            error = repr(e)
            if 'Permission denied' in error:
                print(f'{error} - try sudo ./setup.py install')
            else:
                print(error)
    elif 'remove' in sys.argv:
        try:
            os.system(f'rm -rf {installDir}')
        except Exception as e:
            error = repr(e)
            if 'Permission denied' in error:
                print(f'{error} - try sudo ./setup.py remove')
            else:
                print(error)
    else:
        print("missing flag - install|remove")