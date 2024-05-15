""" Keyword query utilities

Defines what a keyword typed in the search bar is matched against, and how to
read the keywords back out of a stored query (persistent queries, shared links,
reloading a search).
"""
import re

from django.conf import settings

from core_main_app.commons.constants import DATA_TEXT_FIELD as TEXT_CONTENT_FIELD

# One lookahead per keyword, so a record has to contain all of them, in any
# order and anywhere in its text. Matching is a case-insensitive substring:
# "marsh" finds "Marshall" and "202" finds "2023".
_LOOKAHEAD = r"(?=[\s\S]*{})"
_LOOKAHEAD_PATTERN = re.compile(r"\(\?=\[\\s\\S\]\*((?:\\.|[^\\)])*)\)")


def _clean_keyword(keyword):
    """Strip a keyword and remove the MongoDB operator prefix, which is
    rejected further down the query pipeline.

    Args:
        keyword:

    Returns:
    """
    return keyword.replace("$", "").strip()


def build_keyword_query(keyword_list):
    """Build the query matching every given keyword against the full text of a
    record.

    Args:
        keyword_list:

    Returns:
        dict: the query, or None if no usable keyword was given.
    """
    keyword_list = [
        keyword for keyword in map(_clean_keyword, keyword_list) if keyword
    ]

    if not keyword_list:
        return None

    if not getattr(settings, "MONGODB_INDEXING", False):
        # Without the MongoDB index there is no flattened field to match on,
        # fall back to the word based full text search of the storage backend.
        return {
            "$text": {
                "$search": " ".join(
                    '"{}"'.format(keyword) for keyword in keyword_list
                )
            }
        }

    pattern = "(?i)^" + "".join(
        _LOOKAHEAD.format(re.escape(keyword)) for keyword in keyword_list
    )
    return {TEXT_CONTENT_FIELD: {"$regex": pattern}}


def get_keywords_from_keyword_query(query):
    """Read the keywords back from a query built by build_keyword_query.

    Args:
        query:

    Returns:
        list: the keywords, empty if the query is not a keyword query.
    """
    if "$text" in query:
        return [
            keyword
            for keyword in query["$text"]["$search"].split('"')
            if keyword.strip()
        ]

    criteria = query.get(TEXT_CONTENT_FIELD)

    if not isinstance(criteria, dict):
        return []

    pattern = criteria.get("$regex", "")
    return [
        re.sub(r"\\(.)", r"\1", escaped_keyword)
        for escaped_keyword in _LOOKAHEAD_PATTERN.findall(pattern)
    ]
