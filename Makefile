SHELL := /bin/bash
NULL := /dev/null

ifeq ($(COMMIT),)
  COMMIT := $(shell git rev-parse --short HEAD 2> $(NULL))
endif
ifeq ($(BUILD_TAG),)
  BUILD_TAG := $(shell git describe --always --dirty --abbrev=8 2> $(NULL))
endif

PACKAGE := simple-furigana-$(BUILD_TAG).zip

all: prepare document plugin

prepare:
	@mkdir -p build

# Convert the readme to an HTML file formatted to fit the add-on website's
# supported tags.
document: prepare
	pandoc --to=html < README.md | tail -n+3 | sed -E \
		-e 's,</?p>,,g' \
		-e 's,<em>(.*)</em>,<i>\1</i>,' \
		-e 's,<i>Current version: [0-9.]*,\0 (Commit <a href="https://github.com/jcsirot/anki-simple-furigana/tree/$(GIT_HASH)">$(GIT_HASH_SHORT)</a>),' \
		-e 's,<h2.*\">(.*)</h2>,|<b>\1</b>,g' | tr '|' '\n' \
		| awk '/\<\/?(ul|li)\>$$/ { printf("%s", $$0); next } 1' \
		> build/description.html

# The archive to be uploaded to the add-on repo.
plugin: prepare
	pushd src && zip -r ../build/$(PACKAGE) $(subst src/,,$(wildcard src/*)) && popd

clean:
	rm -rf build/

.PHONY: all clean plugin document prepare
