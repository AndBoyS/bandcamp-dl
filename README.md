# bandcamp-dl

Download audio from [bandcamp.com](https://www.bandcamp.com).

## Synopsis

```console
bandcamp-dl URL
```

## Installation

### From PyPI

```console
pip3 install bandcamp-downloader
```

Some Linux distros may require that `python3-pip` is installed first.

### From Wheel

1. Download the wheel (`.whl`) from PyPI or the Releases page.
2. `cd` to the directory containing the `.whl` file.
3. `pip install <filename.whl>`.

### [OSX] From Homebrew

```console
brew install bandcamp-dl
```

### [Arch] From the AUR

```console
yay -S bandcamp-dl-git
```

### From Source

1. Clone the project or [download and extract the zip](https://github.com/evolution0/bandcamp-dl/archive/master.zip).
2. `cd` to the project directory.
3. Run `pip install .`.

## Description

bandcamp-dl is a small command-line app to download audio from bandcamp.com. It requires the Python interpreter, version 3.10-3.14 and is not platform specific. It is released to the public domain, which means you can modify it, redistribute it or use it how ever you like.

## Details

```text
Usage:
    bandcamp-dl [options] [URL...]

Arguments:
    URL         One or more Bandcamp album/track URLs
```

## Options

```text
usage: bandcamp-dl [-h] [-v] [--artist ARTIST] [--track TRACK] [--album ALBUM]
                   [--template TEMPLATE] [--base-dir BASE_DIR] [-f] [--cover-quality {0,10,16}]
                   [-c OK_CHARS] [-s SPACE_CHAR] [-x {lower,upper,camel,none}]
                   [--truncate-album LENGTH] [--truncate-track LENGTH] [--max-retries MAX_RETRIES]
                   [--ignore-errors] [-d] [-o] [--art-mode {none,file,embed,file-embed}] [-n] [-r]
                   [--art-as-file] [-e] [-g] [--untitled-path-from-slug] [-y] [-a] [-k]
                   [--no-confirm] [--embed-genres]
                   [URL ...]

positional arguments:
  URL                   One or more Bandcamp album/track URLs

options:
  -h, --help            show this help message and exit
  -v, --version         Show version
  --artist ARTIST       Specify an artist's slug to download their full discography.
  --track TRACK         Specify a track's slug to download a single track. Must be used with
                        --artist.
  --album ALBUM         Specify an album's slug to download a single album. Must be used with
                        --artist.
  --template TEMPLATE   Output filename template
  --base-dir BASE_DIR   Base location of which all files are downloaded
  -f, --full-album      Download only if all tracks are available
  --cover-quality {0,10,16}
                        Set the cover art quality
  -c OK_CHARS, --ok-chars OK_CHARS
                        Specify allowed chars in slugify
  -s SPACE_CHAR, --space-char SPACE_CHAR
                        Specify the char to use in place of spaces
  -x {lower,upper,camel,none}, --case-convert {lower,upper,camel,none}
                        Specify the char case conversion logic
  --truncate-album LENGTH
                        Truncate album title; 0 for no limit
  --truncate-track LENGTH
                        Truncate track title; 0 for no limit
  --max-retries MAX_RETRIES
                        Maximum retries per failed download; 0 for a single attempt
  --ignore-errors       Continue downloading when an parsing/downloading error occurs
  -d, --debug           Verbose logging
  -o, --overwrite       Overwrite tracks that already exist
  --art-mode {none,file,embed,file-embed}
                        Album art handling: 'none' skips art, 'file' downloads cover.jpg
                        (default), 'embed' embeds it in tags and removes the file, 'file-embed'
                        combines both
  -n, --no-art          Alias for --art-mode none
  -r, --embed-art       Alias for --art-mode embed
  --art-as-file         Alias for --art-mode file
  -e, --embed-lyrics    Embed track lyrics (If available)
  -g, --group           Use album/track Label as iTunes grouping
  --untitled-path-from-slug
                        Use the URL slug for untitled album paths
  -y, --no-slugify      Disable slugification of track, album, and artist names
  -a, --ascii-only      Only allow ASCII chars
  -k, --keep-spaces     Retain whitespace in filenames
  --no-confirm          Override confirmation prompts. Use with caution
  --embed-genres        Embed album/track genres
```

## Filename Template

The `--template` option allows users to indicate a template for the output file names and directories. Templates can be built using special tokens with the format of `%{artist}`. Here is a list of allowed tokens:

- `trackartist`: The artist name.
- `artist`: The album artist name.
- `album`: The album name.
- `track`: The track number.
- `title`: The track title.
- `date`: The album date.
- `label`: The album label.

The default template is: `%{artist}/%{album}/%{track} - %{title}`.

## Bugs

Bugs should be reported [here](https://github.com/evolution0/bandcamp-dl/issues). Please include the URL and/or options used as well as the output when using the `--debug` option.

For discussions, join us in [Discord](https://discord.gg/nwdT4MP).

When you submit a request, please re-read it once to avoid a couple of mistakes (you can and should use this as a checklist):

### Are you using the latest version?

This should report that you're up-to-date. About 20% of the reports we receive are already fixed, but people are using outdated versions. This goes for feature requests as well.

### Is the issue already documented?

Make sure that someone has not already opened the issue you're trying to open. Search at the top of the window or at [Issues](https://github.com/evolution0/bandcamp-dl/search?type=Issues). If there is an issue, feel free to write something along the lines of "This affects me as well, with version 2015.01.01. Here is some more information on the issue: ...". While some issues may be old, a new post into them often spurs rapid activity.

### Why are existing options not enough?

Before requesting a new feature, please have a quick peek at [the list of supported options](README.md#synopsis). Many feature requests are for features that actually exist already! Please, absolutely do show off your work in the issue report and detail how the existing similar options do *not* solve your problem.

### Does the issue involve one problem, and one problem only?

Some of our users seem to think there is a limit of issues they can or should open. There is no limit of issues they can or should open. While it may seem appealing to be able to dump all your issues into one ticket, that means that someone who solves one of your issues cannot mark the issue as closed. Typically, reporting a bunch of issues leads to the ticket lingering since nobody wants to attack that behemoth, until someone mercifully splits the issue into multiple ones.

### Is anyone going to need the feature?

Only post features that you (or an incapable friend you can personally talk to) require. Do not post features because they seem like a good idea. If they are really useful, they will be requested by someone who requires them.

### Is your question about bandcamp-dl?

It may sound strange, but some bug reports we receive are completely unrelated to bandcamp-dl and relate to a different or even the reporter's own application. Please make sure that you are actually using bandcamp-dl. If you are using a UI for bandcamp-dl, report the bug to the maintainer of the actual application providing the UI. On the other hand, if your UI for bandcamp-dl fails in some way you believe is related to bandcamp-dl, by all means, go ahead and report the bug.

## Dependencies

- [BeautifulSoup4](https://pypi.python.org/pypi/beautifulsoup4) - HTML Parsing
- [Demjson](https://pypi.python.org/pypi/demjson) - JavaScript dict to JSON conversion
- [Mutagen](https://pypi.python.org/pypi/mutagen) - ID3 Encoding
- [Requests](https://pypi.python.org/pypi/requests) - for retrieving the HTML

## Copyright

bandcamp-dl is released into the public domain by the copyright holders.

This README file was inspired by the [youtube-dl](https://github.com/rg3/youtube-dl/blob/master/README.md) docs and is likewise released into the public domain.
