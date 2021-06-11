import sys
import os
import pkg_resources
from pprint import pprint

# The purpose of this script is to check system info and specifically system path info.


pprint({
    'sys.version_info': sys.version_info,
    'sys.prefix': sys.prefix,
    'sys.path': sys.path,
    'pkg_resources.working_set': list(pkg_resources.working_set),
    'PATH': os.environ['PATH'].split(os.pathsep),
})