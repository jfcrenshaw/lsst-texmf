#!/usr/bin/env python3

"""Script to generate a bibfile from the Rubin documentation search service,
which is hosted by Algolia.

Note: The front-end for this documentation metadata is https://www.lsst.io. The
data is supplied by Ook, https://github.com/lsst-sqre/ook.
"""

import argparse
import calendar
from datetime import datetime

import latexcodec  # noqa provides the latex+latin codec
import pybtex.database
from algoliasearch.search_client import SearchClient
from bibtools import BibDict, BibEntry
from pybtex.database import BibliographyData

MAXREC = 2000


def isCommittee(author):
    """Guess if this is a committee or working group paper.

    For DM-39724 decide if we have a non regular author
    for Committee and Working group papers we need to {} them
    This is a way to decide if we have a committee.
    """
    if "," in author:
        # assume if there is Author, A.N  it is regular
        return False
    authorl = author.lower()
    if "committee" in authorl:
        return True
    if "group" in authorl:
        return True
    words = author.split()
    # if there are 5 words its probably not a person
    # an alternative wll be to list explicit groups here.
    return len(words) > 5


def sort_by_handle(key):
    """Allow Document-11 to come before Document-8."""
    try:
        hdl, num = key.split("-")
    except ValueError:
        # Doesn't look like a handle so return it directly.
        return key
    num = num.lstrip("0")
    try:
        num = int(num)
    except ValueError:
        # Not a number.
        return key
    return f"{hdl.upper()}-{num:09d}"


def generate_bibfile(query: str = "", external: list[str] | None = None) -> str:
    """
    Query ook for the list of entries.
    Only returning meta data needed for bib entries.

    Parameters
    ----------
    query : `str`
        Any word/query string you would put in lsst.io empty for all.
    external : `str`, optional
        External bib files to seed the results. They are merged together in
        order (the final one takes priority) and then the results from
        the query are copied in, over-writing any previous entries.

    Returns
    -------
    result : `str`
        Formatted bib file string ready to be printed.
    """
    if query is None:
        query = ""  # Algolia take None as string literal None
    client = SearchClient.create("0OJETYIVL5", "b7bd2f1080a5c4fe5eee502462bcc9d3")
    index = client.init_index("document_dev")

    params = {
        "attributesToRetrieve": [
            "handle",
            "series",
            "h1",
            "baseUrl",
            "sourceUpdateTime",
            "sourceUpdateTimestamp",
            "authorNames",
        ],
        "hitsPerPage": MAXREC,
    }

    res = index.search(query, params)
    print(f"Total hits: {len(res['hits'])}, Query:'{query}'")

    search_data = create_bibentries(res)
    print(f"Got {len(res['hits'])} records max:{MAXREC} produced {len(search_data.entries)} bibentries.")

    # Read the external files that will be merged with the search results.
    # Do not use a BilbiographyData because duplicate key overwriting is
    # not allowed. BibTeX is case insensitive so use a special
    # case-insensitive but case-preserving dict. This is needed else pybtex
    # will complain if it finds Document-123 and document-123 in the dict.
    all_data: BibDict[str, pybtex.database.Entry] = BibDict()
    if external:
        for bibfile in external:
            with open(bibfile) as fd:
                this_bib = BibliographyData.from_string(fd.read(), "bibtex")
            all_data.update(this_bib.entries)

    # Overwrite the entries from the search.
    all_data.update(search_data.entries)

    # Rebuild the final bib collection with sorting.
    bibdata = BibliographyData(entries={k: all_data[k] for k in sorted(all_data, key=sort_by_handle)})

    result = """## DO NOT EDIT THIS FILE. It is generated from generateBibfile.py
## Add static entries in etc/static_entries.bib (or remove them if they clash.
## This files should contain ALL entries on www.lsst.io

"""
    result += bibdata.to_string("bibtex")
    return result


def create_bibentries(res) -> BibliographyData:
    """Create the bibtex entries."""
    bcount = 0
    entries: dict[str, pybtex.database.Entry] = {}
    for count, d in enumerate(res["hits"]):
        if "series" in d.keys() and d["series"] == "TESTN":
            continue
        bcount = bcount + 1
        if len(d["authorNames"]) == 1 and isCommittee(d["authorNames"][0]):
            authors = f"{{{d['authorNames'][0]}}}"
        else:
            authors = " and ".join(d["authorNames"])
        dt = d["sourceUpdateTimestamp"]
        date = datetime.fromtimestamp(dt)
        month = calendar.month_abbr[date.month].lower()
        if "baseUrl" in d:
            url = d["baseUrl"]
        else:
            # Use ls.st as fallback since that works for docushare handles
            # in case those turn up.
            url = f"https://ls.st/{d['handle']}"
            print(f"{url} did not have baseUrl set")
        be = BibEntry(
            checkFixAuthAndComma(fixTexSS(authors)),
            fixTex(d["h1"]),
            month,
            d["handle"],
            date.year,
            url=url,
            publisher="Vera C. Rubin Observatory",
        )
        entry = be.get_pybtex()
        entries[entry.key] = entry

    # Sort by key on creation since BibliographyData doesn't have
    # a sort method internally.
    return BibliographyData(entries={k: entries[k] for k in sorted(entries)})


def fixTex(text):
    """
    Escape special TeX chars.
    :param text:
    :return: modified text
    """
    specialChars = "_$&%^#"
    for c in specialChars:
        text = text.replace(c, f"\\{c}")
    return text


def checkFixAuthAndComma(authors):
    """
    Soem people used comm seperated author lists - bibtex does not like that.
    Here we replave the comma with and.
    And someone put an & in the author list - that is not allowed either.

    :param authors:
    :return: authors in and format
    """
    if "," in authors:
        # a bit heavy handed but
        authors = authors.replace(",", " and")
    if "&" in authors:
        authors = authors.replace("&", " and")
    return authors


def fixTexSS(text):
    """
    There are several UTF special chars in lsst.io which need to be TeXified.
    This routing catches them and replaces them with TeX versions (or nothing).
    :param text:
    :return: modified text
    """
    try:
        text.encode("ascii")
        # If three are no non ascii chars i have nothing to do !!
        # the encoding here is only to see if there are any UTF-8s
        # the result is not used.
    except UnicodeEncodeError:
        # Some of these came from RHL's HSC code - I do not understand them all
        for ci, co in [
            ("’", "'"),
            ("…", "..."),
            ("“", '"'),  # double quote unicode 8221 (LEFT)
            ("”", '"'),  # and 8220 (RIGHT) The may look the same
            ("´", "'"),
            (" ", " "),
            ("–", "-"),  # en-dash
            ("—", "-"),  # em-dash
            ("\U0010fc0e", "?"),  # '?' in a square
            ("？", "?"),
            ("à", "\\`{a}"),  # grave
            ("á", "\\'{a}"),  # acute
            ("â", "\\r{a}"),
            ("Ç", "\\c{C}"),
            ("ć", "\\'{c}"),
            ("ç", "\\c{c}"),
            ("ë", '\\"{e}'),
            ("é", "\\'{e}"),
            ("è", "\\`{e}"),
            ("ê", "\\r{e}"),
            ("¡", "i"),
            ("í", "\\'{i}"),
            ("ó", "\\'{o}"),
            ("ñ", "\\~{n}"),
            ("ö", '\\"{o}'),
            ("û", "\\r{u}"),
            ("ü", '\\"{u}'),
            ("ù", "\\`{u}"),
            ("ž", "{\\v z}"),
            ("Ž", "{\\v Z}"),
            ("􏰎", " "),
            ("ï", '\\"{i}'),  # really i dieresis
            ("ô", "\\r{o}"),
            ("‘", "'"),
            ("ʻ", "'"),
            ("¹", ""),
            ("²", ""),
            ("³", ""),
            ("²", ""),
            ("⁴", ""),
            ("⁵", ""),
            ("⁶", ""),
            ("⁷", ""),
            ("⁸", ""),
        ]:
            text = text.replace(ci, co)
    return text


if __name__ == "__main__":
    description = __doc__
    formatter = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(description=description, formatter_class=formatter)

    parser.add_argument("bibfile", help="Name of file to output bib entries to", nargs="?")
    parser.add_argument("-q", "--query", help="""Query string (optional)""")
    parser.add_argument(
        "--external",
        help="""Reference bib to use to obtain bib entries that have disappeared.""",
        action="append",
        nargs="?",
    )

    args = parser.parse_args()
    result = generate_bibfile(args.query, args.external)

    if args.bibfile:
        with open(args.bibfile, "w") as outfile:
            print(result, file=outfile)
    else:
        print(result)
