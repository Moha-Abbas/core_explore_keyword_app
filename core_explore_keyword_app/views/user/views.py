"""Core Explore Keyword App views
"""
import json
from typing import Dict, Any, List

from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator

import core_explore_keyword_app.components.persistent_query_keyword.api as persistent_query_keyword_api
import core_main_app.components.template_version_manager.api as template_version_manager_api
import core_main_app.components.workspace.api as workspace_api
from core_explore_common_app.components.query import api as query_api
from core_explore_common_app.settings import DEFAULT_DATE_TOGGLE_VALUE
from core_explore_common_app.views.user.views import (
    ResultQueryRedirectView,
    ResultsView,
)
from core_explore_keyword_app.components.persistent_query_keyword.models import (
    PersistentQueryKeyword,
)
from core_explore_keyword_app.forms import KeywordForm
from core_explore_keyword_app.permissions import rights
from core_explore_keyword_app.settings import EXPLORE_KEYWORD_APP_EXTRAS
from core_explore_keyword_app.utils.keywords import (
    build_keyword_query,
    get_keywords_from_keyword_query,
)
from core_explore_keyword_app.utils.search_operators import (
    build_search_operator_query,
    get_keywords_from_search_operator_query,
)
from core_main_app.commons.exceptions import DoesNotExist, ApiError
from core_main_app.components.template import api as template_api
from core_main_app.settings import DATA_SORTING_FIELDS
from core_main_app.utils import decorators
from core_main_app.utils.rendering import render


def _get_accessible_workspaces(user):
    """Workspaces the user can read or write, used to populate the
    "Filter by Workspace" control.

    Args:
        user:

    Returns:
    """
    read_ws = list(
        workspace_api.get_all_workspaces_with_read_access_by_user(user)
    )
    write_ws = list(
        workspace_api.get_all_workspaces_with_write_access_by_user(user)
    )
    merged = read_ws + [ws for ws in write_ws if ws not in read_ws]
    workspaces = [
        {"id": ws.id, "title": ws.title, "is_public": ws.is_public}
        for ws in merged
    ]
    # Pseudo-entry for records with no workspace assigned at all. "None" is
    # the exact sentinel QueryBuilder.add_list_criteria already recognizes
    # and turns into a real None in the $in list - no new query logic
    # needed, just this one extra choice in the selector.
    workspaces.insert(
        0,
        {
            "id": "None",
            "title": "No Workspace",
            "is_public": False,
            "is_pseudo": True,
        },
    )
    return workspaces


class KeywordSearchView(ResultsView):
    """Keyword Search View"""

    query_builder_interface = "core_explore_keyword_app/user/search_bar.html"

    @method_decorator(
        decorators.permission_required(
            content_type=rights.EXPLORE_KEYWORD_CONTENT_TYPE,
            permission=rights.EXPLORE_KEYWORD_ACCESS,
        )
    )
    def get(self, request, **kwargs):
        """GET

        Args:
            request:
            **kwargs:

        Returns:

        """
        query_id = str(kwargs["query_id"]) if "query_id" in kwargs else None

        # assets / modals / forms
        context = self._get(request, query_id)
        context.update({"page_title": "Database"})

        return render(
            request,
            "core_explore_keyword_app/user/index.html",
            assets=self.assets,
            modals=self.modals,
            context=context,
        )

    @method_decorator(
        decorators.permission_required(
            content_type=rights.EXPLORE_KEYWORD_CONTENT_TYPE,
            permission=rights.EXPLORE_KEYWORD_ACCESS,
        )
    )
    def post(self, request):
        """POST

        Args:
            request:

        Returns:

        """

        # assets / modals / forms
        context = self._post(request)

        # Set page title
        context.update({"page_title": "Search By Keyword"})

        # if any errors or warning detected
        if context["error"] or context["warning"]:
            # render form again
            return render(
                request,
                "core_explore_keyword_app/user/index.html",
                assets=self.assets,
                modals=self.modals,
                context=context,
            )
        # no errors, redirect to search form
        return HttpResponseRedirect(
            reverse(
                "core_explore_keyword_app_search",
                kwargs={"query_id": context["query_id"]},
            )
        )

    @staticmethod
    def _parse_query(query_content):
        query_json = json.loads(query_content)

        if "$and" in query_json:
            # parse all the sub_queries
            parsed_sub_queries = [
                KeywordSearchView._parse_query(json.dumps(sub_query))
                for sub_query in query_json["$and"]
            ]

            return ",".join(
                parsed_sub_query
                for parsed_sub_query in parsed_sub_queries
                if parsed_sub_query
            )

        keyword_list = get_keywords_from_keyword_query(query_json)

        if not keyword_list and len(query_json.keys()) != 0:
            # Avoid parsing empty query
            keyword = get_keywords_from_search_operator_query(query_json)

            if keyword is not None:
                keyword_list.append(keyword)

        return ",".join(keyword_list)

    def _get(self, request, query_id):
        """Prepare the GET context

        Args:
            query_id:

        Returns:

        """
        try:
            error = None
            # set the correct default ordering for the context
            default_order = ",".join(DATA_SORTING_FIELDS)
            if query_id is None:
                # create query
                query = query_api.create_default_query(request, [])
                # No template selected == no template restriction == every
                # test is already included in the results. Pre-check every
                # box so the pills reflect that from the start, instead of
                # showing "nothing selected" for a search that actually
                # covers everything.
                all_global_templates = [
                    str(template_version_manager.id)
                    for template_version_manager in template_version_manager_api.get_active_global_version_manager(
                        request=request
                    )
                ]
                all_user_templates = [
                    str(template_version_manager.id)
                    for template_version_manager in template_version_manager_api.get_active_version_manager_by_user_id(
                        request=request
                    )
                ]
                # create keyword form
                # create all data for select values in forms
                keywords_data_form = {
                    "query_id": str(query.id),
                    "user_id": query.user_id,
                    "global_templates": all_global_templates,
                    "user_templates": all_user_templates,
                }
            else:  # query_id is not None
                # get the query id
                query = query_api.get_by_id(query_id, request.user)
                user_id = query.user_id

                # get all keywords back
                keywords = self._parse_query(query.content)

                # get all version managers
                version_managers = []
                for template in query.templates.all():
                    version_managers.append(str(template.version_manager.id))
                # restore the previously selected workspaces, if any
                workspace_ids = []
                if query.data_sources:
                    workspace_ids = query.data_sources[0].get(
                        "query_options", {}
                    ).get("workspaces", [])
                # create all data for select values in forms
                keywords_data_form = {
                    "query_id": str(query.id),
                    "user_id": user_id,
                    "keywords": keywords,
                    "global_templates": version_managers,
                    "order_by_field": super().build_sorting_context_array(
                        query
                    ),
                    "user_templates": version_managers,
                    "workspaces": ",".join(str(w) for w in workspace_ids),
                }
                # set the correct ordering for the context
                if keywords_data_form["order_by_field"] != 0:
                    default_order = keywords_data_form["order_by_field"]

        except Exception as exception:
            error = "An unexpected error occurred while loading the query: {}.".format(
                str(exception)
            )
            return {"error": error}

        search_form = KeywordForm(data=keywords_data_form, request=request)
        return self._format_keyword_search_context(
            search_form, error, None, default_order, request
        )

    def _post(self, request):
        """Prepare the POST context

        Args:
            request:

        Returns:

        """
        error = None
        warning = None
        search_form = KeywordForm(data=request.POST, request=request)
        # validate form
        if search_form.is_valid():
            try:
                # get form values
                query_id = search_form.cleaned_data.get("query_id", None)
                keywords = search_form.cleaned_data.get("keywords", None)
                global_templates = search_form.cleaned_data.get(
                    "global_templates", []
                )
                user_templates = search_form.cleaned_data.get(
                    "user_templates", []
                )
                order_by_field_array = (
                    search_form.cleaned_data.get("order_by_field", "")
                    .strip()
                    .split(";")
                )
                workspace_ids = []
                for workspace_id in search_form.cleaned_data.get(
                    "workspaces", ""
                ).split(","):
                    workspace_id = workspace_id.strip()
                    if not workspace_id:
                        continue
                    try:
                        workspace_ids.append(int(workspace_id))
                    except ValueError:
                        workspace_ids.append(workspace_id)
                # get all template version manager ids
                template_version_manager_ids = (
                    global_templates + user_templates
                )
                # from ids, get all version manager
                version_manager_list = (
                    template_version_manager_api.get_by_id_list(
                        template_version_manager_ids, request=request
                    )
                )
                # from all version manager, build a list of all version (template)
                template_ids = []
                list(
                    [
                        template_ids.extend(x.versions)
                        for x in version_manager_list
                    ]
                )
                if query_id is None or keywords is None:
                    error = "Expected parameters are not provided"
                else:
                    # get query
                    query = query_api.get_by_id(query_id, request.user)
                    if len(query.data_sources) == 0:
                        warning = "Please select at least 1 data source."
                    else:
                        # update query
                        query.templates.set(
                            template_api.get_all_accessible_by_id_list(
                                template_ids, request=request
                            )
                        )
                        keywords_list = keywords.split(",") if keywords else []
                        query.content = self._build_query(keywords_list)
                        # set the data-sources filter value according to the POST request field
                        for data_sources_index in range(
                            len(query.data_sources)
                        ):
                            # update the data-source filter only if it's not a new data-source
                            # (the default filter value is already added when the data-source
                            # is created)
                            if data_sources_index in range(
                                0, len(order_by_field_array)
                            ):
                                query.data_sources[data_sources_index][
                                    "order_by_field"
                                ] = order_by_field_array[data_sources_index]
                            query.data_sources[data_sources_index].setdefault(
                                "query_options", {}
                            )["workspaces"] = workspace_ids

                        query_api.upsert(query, request.user)
            except DoesNotExist:
                error = (
                    "An unexpected error occurred while retrieving the query."
                )
            except Exception as exception:
                error = "An unexpected error occurred: {}.".format(
                    str(exception)
                )
        else:
            error = "An unexpected error occurred: the form is not valid."

        return self._format_keyword_search_context(
            search_form,
            error,
            warning,
            search_form.cleaned_data.get("order_by_field", "").strip(),
            request,
        )

    @staticmethod
    def _build_query(initial_keyword_list):
        """Build query content with correct keywords and search operators

        Args:
            initial_keyword_list:

        Returns:
        """
        main_query = list()
        keyword_list = list()

        for keyword in initial_keyword_list:
            if ":" in keyword:
                try:
                    split_keyword = keyword.split(":")

                    main_query.append(
                        build_search_operator_query(
                            split_keyword[0], split_keyword[1]
                        )
                    )
                    continue
                except ApiError:
                    # Not a registered operator, search it as a plain keyword
                    pass

            keyword_list.append(keyword)

        keyword_query = build_keyword_query(keyword_list)

        if keyword_query:
            main_query.append(keyword_query)

        # If the query is empty, match all documents
        if len(main_query) == 0:
            return json.dumps({})
        if (
            len(main_query) == 1
        ):  # If there is one query item, match one this item.
            return json.dumps(main_query[0])

        # For multiple items, a "$and" query is needed.
        return json.dumps({"$and": main_query})

    def _load_assets(self):
        """Return assets structure

        Returns:

        """
        assets = super()._load_assets()
        extra_assets: Dict[str, List[Any]] = {
            "js": [
                {
                    "path": "core_explore_keyword_app/libs/tag-it/2.0/js/tag-it.js",
                    "is_raw": True,
                },
                {
                    "path": "core_explore_keyword_app/libs/stretchy/stretchy.min.js",
                    "is_raw": False,
                },
                {
                    "path": "core_explore_keyword_app/user/js/search/search.js",
                    "is_raw": False,
                },
                {
                    "path": "core_explore_keyword_app/user/js/search/autocomplete_source.js",
                    "is_raw": False,
                },
                {
                    "path": "core_explore_keyword_app/user/js/search/template_filter_pills.js",
                    "is_raw": False,
                },
                {
                    "path": "core_explore_keyword_app/user/js/search/workspace_filter.js",
                    "is_raw": False,
                },
                {
                    "path": "core_explore_keyword_app/user/js/persistent_query.raw.js",
                    "is_raw": True,
                },
                {
                    "path": "core_dashboard_app/common/js/download_workspace.js",
                    "is_raw": False,
                },
                {
                    "path": "core_main_app/common/js/wait/waiting.js",
                    "is_raw": False,
                },
            ],
            "css": [
                "core_explore_keyword_app/libs/tag-it/2.0/css/jquery.tagit.css",
                "core_explore_keyword_app/user/css/search/search.css",
                "core_main_app/common/css/wait/waiting.css"
            ],
        }

        assets["js"].extend(extra_assets["js"])
        assets["css"].extend(extra_assets["css"])
        for extra_app in EXPLORE_KEYWORD_APP_EXTRAS:
            assets["js"].extend(extra_app.get_extra_js())
            assets["css"].extend(extra_app.get_extra_css())

        return assets

    def _load_modals(self):
        """Return modals structure

        Returns:

        """
        return super()._load_modals()

    def _format_keyword_search_context(
        self, search_form, error, warning, query_order="", request=None
    ):
        """Format the context for the keyword research page

        Args:
            search_form:
            error:
            warning:
            query_order:
            request:

        Returns:

        """
        accessible_workspaces = (
            _get_accessible_workspaces(request.user) if request else []
        )
        context = {
            "search_form": search_form,
            "query_id": search_form.data["query_id"],
            "error": error,
            "warning": warning,
            "default_date_toggle_value": DEFAULT_DATE_TOGGLE_VALUE,
            "data_sources_selector_template": "core_explore_common_app/user/selector/data_sources_selector.html",
            "data_sorting_fields": query_order,
            "default_data_sorting_fields": ",".join(DATA_SORTING_FIELDS),
            "query_builder_interface": self.query_builder_interface,
            "accessible_workspaces": accessible_workspaces,
            "accessible_workspaces_json": json.dumps(accessible_workspaces),
            "EXPLORE_KEYWORD_APP_EXTRAS_HTML": [
                path
                for extra in EXPLORE_KEYWORD_APP_EXTRAS
                for path in extra.get_extra_html()
            ],
        }

        return context


class ResultQueryRedirectKeywordView(ResultQueryRedirectView):
    """Result Query Redirect Keyword View"""

    model_name = PersistentQueryKeyword.__name__
    object_name = "persistent_query_keyword"
    redirect_url = "core_explore_keyword_app_search"

    @method_decorator(
        decorators.permission_required(
            content_type=rights.EXPLORE_KEYWORD_CONTENT_TYPE,
            permission=rights.EXPLORE_KEYWORD_ACCESS,
        )
    )
    def get(self, request, *args, **kwargs):
        return super().get(self, request, *args, **kwargs)

    @staticmethod
    def _get_persistent_query_by_id(persistent_query_id, user):
        return persistent_query_keyword_api.get_by_id(
            persistent_query_id, user
        )

    @staticmethod
    def _get_persistent_query_by_name(persistent_query_name, user):
        return persistent_query_keyword_api.get_by_name(
            persistent_query_name, user
        )

    @staticmethod
    def get_url_path():
        return reverse(
            ResultQueryRedirectKeywordView.redirect_url,
            kwargs={"query_id": "query_id"},
        ).split("query_id")[0]

    @staticmethod
    def _get_reversed_url(query):
        return reverse(
            ResultQueryRedirectKeywordView.redirect_url,
            kwargs={"query_id": query.id},
        )

    @staticmethod
    def _get_reversed_url_if_failed():
        return reverse("core_explore_keyword_app_search")
