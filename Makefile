#
# Copyright (c) rPath, Inc.
#
# This program is distributed under the terms of the MIT License as found 
# in a file called LICENSE. If it is not present, the license
# is always available at http://www.opensource.org/licenses/mit-license.php.
#
# This program is distributed in the hope that it will be useful, but
# without any waranty; without even the implied warranty of merchantability
# or fitness for a particular purpose. See the MIT License for full details.
#

all: all-subdirs default-all

all-subdirs:
	for d in $(MAKEALLSUBDIRS); do make -C $$d DIR=$$d || exit 1; done

export TOPDIR = $(shell pwd)

SUBDIRS=crest
MAKEALLSUBDIRS=crest


.PHONY: all clean install all-subdirs default-all

subdirs: default-subdirs

install: install-subdirs

clean: clean-subdirs default-clean

doc: html

archive:
	hg archive  --exclude .hgignore -t tbz2 conary-rest-$(VERSION).tar.bz2

clean: clean-subdirs default-clean

include Make.rules
include Make.defs
 
# vim: set sts=8 sw=8 noexpandtab :
