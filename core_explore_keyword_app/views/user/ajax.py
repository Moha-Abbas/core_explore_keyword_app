"""Explore keyword app Ajax views
"""
import json
import logging
import re

from django.http import HttpResponse, HttpResponseBadRequest
from django.utils.decorators import method_decorator
from django.views.generic import View

import core_main_app.components.template_version_manager.api as template_version_manager_api
from core_explore_common_app.components.query import api as query_api
from core_explore_common_app.rest.query.views import execute_local_query
from core_explore_common_app.utils.query.query import (
    create_local_data_source,
    serialize_query,
    is_local_data_source,
)
from core_explore_common_app.views.user.ajax import (
    CreatePersistentQueryUrlView,
)
from core_explore_keyword_app.components.persistent_query_keyword.models import (
    PersistentQueryKeyword,
)
from core_explore_keyword_app.forms import KeywordForm
from core_explore_keyword_app.permissions import rights
from core_explore_keyword_app.utils.keywords import build_keyword_query
from core_main_app.components.template import api as template_api
from core_main_app.utils import decorators
from core_main_app.utils.query.mongo.prepare import sanitize_value

logger = logging.getLogger("core_explore_keyword_app.views.user.ajax")


def _get_local_data_source(query):
    """Check if there is a data source that is local.

    Args:
        query:

    Returns:
    """
    # If we find a data source that is local
    for data_source in query.data_sources:
        # find local data source
        if is_local_data_source(data_source):
            return data_source
    return None


class SuggestionsKeywordSearchView(View):
    """Suggestions Keyword Search View"""

    @method_decorator(
        decorators.permission_required(
            content_type=rights.EXPLORE_KEYWORD_CONTENT_TYPE,
            permission=rights.EXPLORE_KEYWORD_ACCESS,
        )
    )
    def post(self, request, *args, **kwargs):
        """POST

        Args:
            request:
            *args:
            **kwargs:

        Returns:

        """
        suggestions = []
        search_form = KeywordForm(data=request.POST, request=request)
        keywords = request.POST.get("term")

        if not search_form.is_valid():
            error_message = (
                "Exception while generating suggestions: Search form is "
                "invalid"
            )
            logger.error(error_message)
            return HttpResponseBadRequest(error_message)

        try:
            sanitize_value(keywords)  # Ensure only valid keywords are passed

            # get form values
            query_id = search_form.cleaned_data.get("query_id", None)
            global_templates = search_form.cleaned_data.get(
                "global_templates", []
            )
            user_templates = search_form.cleaned_data.get("user_templates", [])

            # get all template version manager ids
            template_version_manager_ids = global_templates + user_templates

            # from ids, get all version manager
            version_manager_list = template_version_manager_api.get_by_id_list(
                template_version_manager_ids, request=request
            )

            # from all version manager, build a list of all version (template)
            template_ids = []
            list(
                [template_ids.extend(x.versions) for x in version_manager_list]
            )

            if query_id is not None and keywords is not None:
                # get query
                query = query_api.get_by_id(query_id, request.user)

                # Get local data source
                local_data_source = _get_local_data_source(query)

                if local_data_source:

                    # Prepare query
                    query = self._get_query_prepared(
                        keywords, query, request, template_ids
                    )

                    # Send query
                    json_query = serialize_query(query, local_data_source)
                    dict_results = execute_local_query(json_query, 1, request)

                    if dict_results.paginator.count > 0:
                        self._extract_suggestion_from_results(
                            dict_results.object_list, keywords, suggestions
                        )

            return HttpResponse(
                json.dumps({"suggestions": suggestions}),
                content_type="application/javascript",
            )
        except Exception as exception:
            error_message = (
                "Exception while generating suggestions: %s",
                str(exception),
            )
            logger.error(error_message)
            return HttpResponseBadRequest(error_message)

    def _get_query_prepared(self, keywords, query, request, template_ids):
        """Prepare the query for suggestions.

        Args:
            keywords:
            query:
            request:
            template_ids:
        Returns:
        """

        # update query
        query.templates.set(
            template_api.get_all_accessible_by_id_list(
                template_ids, request=request
            )
        )
        # Same matching as the search itself, so that a partially typed word
        # returns the records the suggestions are extracted from.
        query.content = json.dumps(build_keyword_query([keywords]) or {})
        # Data source is local
        query.data_sources = [create_local_data_source(request)]
        return query

    @staticmethod
    def _extract_suggestion_from_results(results, keywords, suggestions):
        """Extract suggestion from

        Args:
            results:
            keywords:
            suggestions:

        Returns:
        """
        # Prepare keywords
        word_list = re.sub(r"[^\w]", " ", keywords).split()
        # Suggest the whole words containing the typed term, matching the way
        # the search itself looks for substrings.
        if not word_list:
            return

        word_list = [r"\w*" + re.escape(x) + r"\w*" for x in word_list]
        word_list = "|".join(word_list)
        for result in results:
            # Extract suggestions from data
            list_whole_keywords = re.findall(
                "\\b(" + word_list + ")\\b",
                result.content,
                flags=re.IGNORECASE,
            )
            labels = list(set(list_whole_keywords))

            for label in labels:
                label = label.lower()
                result_json = dict()
                result_json["label"] = label
                result_json["value"] = label
                if result_json not in suggestions:
                    suggestions.append(result_json)


class CreatePersistentQueryUrlKeywordView(CreatePersistentQueryUrlView):
    """Create the persistent url from a Query"""

    view_to_reverse = "core_explore_keyword_results_redirect"

    @staticmethod
    def _create_persistent_query(query):
        # create the persistent query
        return PersistentQueryKeyword(
            user_id=query.user_id,
            content=query.content,
        )
