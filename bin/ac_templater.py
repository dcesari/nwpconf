#!/usr/bin/python

import sys
import os
import re

def ac_templater(fd_in, fd_out):
    """
    Replace values represented as @VAR@
    """
    RE_INCLUDE = re.compile(r"^ *@INCLUDE ([^@]+)@ *$")
    RE_LINE = re.compile(r"@([^@]+)@")

    
    def subst(mo):
#        try:
            return os.environ[mo.group(1)]
#        except:
#            return "None"

    for line in fd_in:
        mo = RE_INCLUDE.match(line)
        if mo is not None:
            fd_inc = open(mo.group(1))
            ac_templater(fd_inc, fd_out)
            fd_inc.close()
        else:
            fd_out.write(RE_LINE.sub(subst, line))


if len(sys.argv) > 1:
    fd_in = open(sys.argv[1])
else:
    fd_in = sys.stdin
ac_templater(fd_in, sys.stdout)
