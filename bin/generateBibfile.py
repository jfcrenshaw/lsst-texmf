#!/usr/bin/env python3

"""This script generates a bibfile from the Rubin documentation search service,
which is hosted by Algolia.
Note: The front-end for this documentation metadata is https://www.lsst.io. The
data is supplied by Ook, https://github.com/lsst-sqre/ook.
"""

import argparse
import calendar
import sys
from datetime import datetime

import latexcodec  # noqa provides the latex+latin codec
from algoliasearch.search_client import SearchClient
from bibtools import BibEntry

MAXREC = 2000


def isCommitee(author):
    #  for DM-39724 decide if we have a non regular author
    # for Comittee and Working group papers we need to {} them
    # This is a way to decide if we have a committee

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


def generate_bibfile(outfile, query=""):
    """
    Query ook for the list of entries.
    Only returning meta data needed for bib entries.

    :param outfile: File to write
    :param query: Any word/query string you would put in lsst.io empty for all
    :return: the file will be writed contianing the entries.
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

    print(
        "## DO NOT EDIT THIS FILE. It is generated from generateBibfile.py\n"
        "## Add static entries in etc/static_entries.bib (or remove them if they clash.\n"
        "## This files should contain ALL entries on www.lsst.io",
        file=outfile,
    )

    bcount = 0
    for count, d in enumerate(res["hits"]):
        if "series" in d.keys() and d["series"] == "TESTN":
            continue
        bcount = bcount + 1
        if len(d["authorNames"]) == 1 and isCommitee(d["authorNames"][0]):
            authors = f"{{{d['authorNames'][0]}}}"
        else:
            authors = " and ".join(d["authorNames"])
        dt = d["sourceUpdateTimestamp"]
        date = datetime.fromtimestamp(dt)
        month = calendar.month_abbr[date.month].lower()
        url = f"https://{d['handle']}/lsst.io/"
        if "baseUrl" in d:
            url = d["baseUrl"]
        else:
            print(f"{url} did not have baseUrl set")
        be = BibEntry(
            checkFixAuthAndComma(fixTexSS(authors)),
            fixTex(d["h1"]),
            month,
            d["handle"],
            date.year,
            url=url,
        )
        be.write_latex_bibentry(outfile)
        print(file=outfile)

    print(f"Got {count} records max:{MAXREC} produced {bcount} bibentries to {outfile}")


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

    parser.add_argument("bibfile", help="Name of file to output bib entries to")
    parser.add_argument("-q", "--query", help="""Query string (optional)""")

    args = parser.parse_args()

    outfile = sys.stdout
    if args.bibfile:
        outfile = open(args.bibfile, "w")

    generate_bibfile(outfile, args.query)
    outfile.close()
