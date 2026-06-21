# type: ignore
from datetime import datetime
from functools import lru_cache
import json
import logging

from django.db.models import Q, Sum, Min, Max, F
from django.utils import timezone
from ninja.errors import HttpError
from apps.common.helpers import getAuthContext, jsonsafe, serializeModelInstance

logger = logging.getLogger(__name__)


def safeAuthContext(request):
    if not request:
        return {}
    try:
        return getAuthContext(request)
    except HttpError:
        return {}
    except Exception:
        return {}


@lru_cache(maxsize=None)
def modelFieldNames(model):
    field_names = set()
    for field in model._meta.get_fields():
        field_names.add(field.name)
        attname = getattr(field, "attname", None)
        if attname:
            field_names.add(attname)
    return frozenset(field_names)


def hasStatusFilter(filter_kwargs):
    return any(str(k).startswith("status") for k in filter_kwargs.keys())


def normalizeWhereInput(where_input):
    if isinstance(where_input, list):
        return {"id__in": where_input}
    if isinstance(where_input, (str, int)):
        return {"id": where_input}
    if isinstance(where_input, dict):
        return dict(where_input)
    if where_input is None:
        return {}
    raise ValueError("Invalid where clause provided")


def buildWhere(model, where_input=None, tenant_config=True, request=None):

    filter_kwargs = normalizeWhereInput(where_input)
    model_fields = modelFieldNames(model)

    q = Q(**filter_kwargs) if filter_kwargs else Q()

    # Default status filter (exclude deleted)
    if "status" in model_fields and not hasStatusFilter(filter_kwargs):
        q &= ~Q(status=2)

    is_obj = isinstance(tenant_config, dict)
    is_empty_obj = is_obj and len(tenant_config.keys()) == 0

    ctx = {}
    if not is_empty_obj:
        ctx = safeAuthContext(request)

    # Strict tenant
    if tenant_config is True:
        if "company" in model_fields and ctx.get("company_id"):
            q &= Q(company_id=ctx["company_id"])
        if "branch" in model_fields and ctx.get("branch_id"):
            q &= Q(branch_id=ctx["branch_id"])
        if "user" in model_fields and ctx.get("user_id"):
            q &= Q(user_id=ctx["user_id"])
    # Explicit toggles
    elif is_obj and not is_empty_obj:
        if tenant_config.get("company_id") and ctx.get("company_id"):
            q &= Q(company_id=ctx["company_id"])
        if tenant_config.get("branch_id") and ctx.get("branch_id"):
            q &= Q(branch_id=ctx["branch_id"])
        if tenant_config.get("user_id") and ctx.get("user_id"):
            q &= Q(user_id=ctx["user_id"])

    return q


class commonQuery:

    @staticmethod
    def enrichTenantData(model, data=None, request=None, tenant_config=True):
        enriched = dict(data or {})
        model_fields = modelFieldNames(model)

        is_obj = isinstance(tenant_config, dict)
        is_empty_obj = is_obj and len(tenant_config.keys()) == 0

        ctx = {}
        if not is_empty_obj:
            ctx = safeAuthContext(request)

        def _inject(field_name, ctx_key):
            if field_name in model_fields and enriched.get(f"{field_name}_id") is None:
                if ctx.get(ctx_key) is not None:
                    enriched[f"{field_name}_id"] = ctx[ctx_key]

        if tenant_config is True:
            _inject("company", "company_id")
            _inject("branch", "branch_id")
            _inject("user", "user_id")
        elif is_obj and not is_empty_obj:
            if tenant_config.get("company_id"):
                _inject("company", "company_id")
            if tenant_config.get("branch_id"):
                _inject("branch", "branch_id")
            if tenant_config.get("user_id"):
                _inject("user", "user_id")

        return enriched

    @staticmethod
    def createRecord(model, data, request=None, tenant_config=True):
        enriched = commonQuery.enrichTenantData(model, data, request, tenant_config)
        instance = model.objects.create(**enriched)
        return serializeModelInstance(instance)

    @staticmethod
    def normalizeInclude(include):
        if not include:
            return []
        if not isinstance(include, list):
            include = [include]
        normalized = []
        for inc in include:
            if isinstance(inc, str):
                normalized.append({"path": inc, "fields": None, "include": []})
                continue
            if isinstance(inc, dict):
                path = inc.get("path") or inc.get("as") or inc.get("relation")
                if not path:
                    continue
                normalized.append(
                    {
                        "path": path,
                        "fields": inc.get("fields") or inc.get("attributes"),
                        "include": commonQuery.normalizeInclude(inc.get("include")),
                    }
                )
        return normalized

    @staticmethod
    def resolveRelatedField(model, name):
        try:
            return model._meta.get_field(name)
        except Exception:
            for f in model._meta.get_fields():
                if f.is_relation and f.auto_created and not f.concrete:
                    if hasattr(f, "get_accessor_name") and f.get_accessor_name() == name:
                        return f
            return None

    @staticmethod
    def collectRelatedPaths(model, include_specs, prefix=""):
        select_related = []
        prefetch_related = []
        for inc in include_specs:
            path = inc.get("path")
            if not path:
                continue
            full_path = f"{prefix}__{path}" if prefix else path
            field = commonQuery.resolveRelatedField(model, path)
            related_model = None
            if field is not None:
                related_model = getattr(field, "related_model", None)
                if field.many_to_many or field.one_to_many or (field.auto_created and not field.concrete):
                    prefetch_related.append(full_path)
                else:
                    select_related.append(full_path)
            # Recurse for nested includes
            if related_model and inc.get("include"):
                sr, pr = commonQuery.collectRelatedPaths(related_model, inc.get("include"), full_path)
                select_related.extend(sr)
                prefetch_related.extend(pr)
        return select_related, prefetch_related

    @staticmethod
    def applyFieldFilter(data, fields):
        if not fields:
            return data
        return {k: data.get(k) for k in fields if k in data}

    @staticmethod
    def serializeWithInclude(obj, include_specs, base_fields=None):
        if obj is None:
            return None
        if isinstance(obj, dict):
            base = commonQuery.applyFieldFilter(obj, base_fields)
            return base

        data = serializeModelInstance(obj)
        data = commonQuery.applyFieldFilter(data, base_fields)

        for inc in include_specs:
            path = inc.get("path")
            if not path:
                continue
            try:
                rel_val = getattr(obj, path)
            except Exception:
                data[path] = None
                continue

            if hasattr(rel_val, "all"):
                data[path] = [
                    commonQuery.serializeWithInclude(
                        child, inc.get("include") or [], inc.get("fields")
                    )
                    for child in rel_val.all()
                ]
            else:
                data[path] = commonQuery.serializeWithInclude(
                    rel_val, inc.get("include") or [], inc.get("fields")
                )

        return data

    @staticmethod
    def bulkCreate(model, data_array, extra_fields=None, request=None, tenant_config=True):
        if not isinstance(data_array, list) or not data_array:
            return []

        extra_fields = extra_fields or {}
        model_fields = modelFieldNames(model)

        is_obj = isinstance(tenant_config, dict)
        is_empty_obj = is_obj and len(tenant_config.keys()) == 0
        ctx = {}
        if not is_empty_obj:
            ctx = safeAuthContext(request)

        def _inject(item):
            if tenant_config is True or (is_obj and not is_empty_obj):
                if (tenant_config is True or tenant_config.get("company_id")) and "company" in model_fields:
                    if item.get("company_id") is None and ctx.get("company_id") is not None:
                        item["company_id"] = ctx["company_id"]
                if (tenant_config is True or tenant_config.get("branch_id")) and "branch" in model_fields:
                    if item.get("branch_id") is None and ctx.get("branch_id") is not None:
                        item["branch_id"] = ctx["branch_id"]
                if (tenant_config is True or tenant_config.get("user_id")) and "user" in model_fields:
                    if item.get("user_id") is None and ctx.get("user_id") is not None:
                        item["user_id"] = ctx["user_id"]
            return item

        enriched = []
        for item in data_array:
            new_item = {**item, **extra_fields}
            enriched.append(_inject(new_item))

        objs = model.objects.bulk_create([model(**item) for item in enriched])
        return [serializeModelInstance(obj) for obj in objs]

    @staticmethod
    def updateRecordById(model, where_input, data, request=None, tenant_config=True, force_reload=False):
        if where_input is None or data is None:
            raise ValueError("Invalid params for update")

        q = buildWhere(model, where_input, tenant_config, request)
        obj = model.objects.filter(q).first()
        if not obj:
            return None

        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)

        obj.save()
        if force_reload:
            obj.refresh_from_db()
        return serializeModelInstance(obj)

    @staticmethod
    def softDeleteById(model, where_input, request=None, tenant_config=True):
        q = buildWhere(model, where_input, tenant_config, request)
        model_fields = modelFieldNames(model)
        ctx = safeAuthContext(request)

        update_kwargs = {"status": 2}
        if "deleted_at" in model_fields:
            update_kwargs["deleted_at"] = timezone.now()
        if "user" in model_fields and ctx.get("user_id") is not None:
            update_kwargs["user_id"] = ctx["user_id"]

        return model.objects.filter(q).update(**update_kwargs)

    @staticmethod
    def updateStatusById(model, where_input, status, request=None, tenant_config=True):
        q = buildWhere(model, where_input, tenant_config, request)
        update_kwargs = {"status": status}
        return model.objects.filter(q).update(**update_kwargs)

    @staticmethod
    def hardDeleteRecords(model, where_input, request=None, tenant_config=True):
        q = buildWhere(model, where_input, tenant_config, request)
        return model.objects.filter(q).delete()

    @staticmethod
    def findAllRecords(model, filters=None, options=None, request=None, tenant_config=True):
        filters = filters or {}
        options = options or {}

        q = buildWhere(model, filters, tenant_config, request)
        queryset = model.objects.filter(q)

        # Ordering
        order = options.get("order")
        if order:
            if isinstance(order, list):
                queryset = queryset.order_by(*order)
            else:
                queryset = queryset.order_by(order)

        include_specs = commonQuery.normalizeInclude(options.get("include"))

        select_related, prefetch_related = commonQuery.collectRelatedPaths(model, include_specs)
        if options.get("select_related"):
            select_related.extend(options["select_related"])
        if options.get("prefetch_related"):
            prefetch_related.extend(options["prefetch_related"])

        if select_related:
            queryset = queryset.select_related(*select_related)
        if prefetch_related:
            queryset = queryset.prefetch_related(*prefetch_related)

        # Pagination
        skip = options.get("skip", 0)
        limit = options.get("limit")
        if limit is not None:
            queryset = queryset[int(skip) : int(skip) + int(limit)]
        elif skip:
            queryset = queryset[int(skip) :]

        base_fields = options.get("attributes")
        if base_fields and not include_specs:
            return list(queryset.values(*base_fields))

        return [
            commonQuery.serializeWithInclude(obj, include_specs, base_fields)
            for obj in queryset
        ]

    @staticmethod
    def findOneRecord(model, where_input=None, options=None, request=None, tenant_config=True, force_reload=False):
        options = options or {}
        q = buildWhere(model, where_input, tenant_config, request)
        queryset = model.objects.filter(q)

        include_specs = commonQuery.normalizeInclude(options.get("include"))

        select_related, prefetch_related = commonQuery.collectRelatedPaths(model, include_specs)
        if options.get("select_related"):
            select_related.extend(options["select_related"])
        if options.get("prefetch_related"):
            prefetch_related.extend(options["prefetch_related"])

        if select_related:
            queryset = queryset.select_related(*select_related)
        if prefetch_related:
            queryset = queryset.prefetch_related(*prefetch_related)

        base_fields = options.get("attributes")
        if base_fields and not include_specs:
            obj = queryset.values(*base_fields).first()
            return obj

        obj = queryset.first()
        if obj and force_reload:
            obj.refresh_from_db()

        return jsonsafe(commonQuery.serializeWithInclude(obj, include_specs, base_fields)) if obj else None

    @staticmethod
    def findOneInstance(model, where_input=None, options=None, request=None, tenant_config=True, for_update=False):
        options = options or {}
        q = buildWhere(model, where_input, tenant_config, request)
        queryset = model.objects
        if for_update:
            queryset = queryset.select_for_update()
        queryset = queryset.filter(q)

        if options.get("select_related"):
            queryset = queryset.select_related(*options["select_related"])
        if options.get("prefetch_related"):
            queryset = queryset.prefetch_related(*options["prefetch_related"])
        if options.get("order"):
            order = options["order"]
            queryset = queryset.order_by(*order) if isinstance(order, list) else queryset.order_by(order)

        return queryset.first()

    @staticmethod
    def existsRecord(model, where_input=None, request=None, tenant_config=True):
        q = buildWhere(model, where_input, tenant_config, request)
        return model.objects.filter(q).exists()

    @staticmethod
    def getOrCreateRecord(model, where_input=None, defaults=None, request=None, tenant_config=True, return_plain=True):
        filters = commonQuery.enrichTenantData(model, where_input, request, tenant_config)
        default_values = commonQuery.enrichTenantData(model, defaults or {}, request, tenant_config)
        instance, created = model.objects.get_or_create(**filters, defaults=default_values)
        return (serializeModelInstance(instance) if return_plain else instance), created

    @staticmethod
    def firstValueRecord(model, where_input=None, options=None, request=None, tenant_config=True):
        options = options or {}
        q = buildWhere(model, where_input, tenant_config, request)
        queryset = model.objects.filter(q)
        order = options.get("order")
        if order:
            queryset = queryset.order_by(*order) if isinstance(order, list) else queryset.order_by(order)
        attributes = options.get("attributes")
        if attributes:
            return queryset.values(*attributes).first()
        return queryset.values().first()

    @staticmethod
    def countRecords(model, filters=None, request=None, tenant_config=True):
        q = buildWhere(model, filters or {}, tenant_config, request)
        return model.objects.filter(q).count()

    @staticmethod
    def sumRecords(model, field, filters=None, request=None, tenant_config=True):
        q = buildWhere(model, filters or {}, tenant_config, request)
        result = model.objects.filter(q).aggregate(total=Sum(field))
        return result.get("total") or 0

    @staticmethod
    def incrementRecords(model, field, by=1, where_input=None, request=None, tenant_config=True):
        q = buildWhere(model, where_input, tenant_config, request)
        return model.objects.filter(q).update(**{field: F(field) + by})

    @staticmethod
    def decrementRecords(model, field, by=1, where_input=None, request=None, tenant_config=True):
        q = buildWhere(model, where_input, tenant_config, request)
        return model.objects.filter(q).update(**{field: F(field) - by})

    @staticmethod
    def minRecords(model, field, where_input=None, request=None, tenant_config=True):
        q = buildWhere(model, where_input, tenant_config, request)
        result = model.objects.filter(q).aggregate(val=Min(field))
        return result.get("val")

    @staticmethod
    def maxRecords(model, field, where_input=None, request=None, tenant_config=True):
        q = buildWhere(model, where_input, tenant_config, request)
        result = model.objects.filter(q).aggregate(val=Max(field))
        return result.get("val")

    @staticmethod
    def fetchPaginatedData(
        model,
        req_body,
        field_config,
        options=None,
        request=None,
        tenant_config=True,
        date_field="created_at",
        custom_where=None,
    ):
        try:
            options = options or {}
            req_body = req_body or {}
            custom_where = custom_where or {}

            # Handle JSON parsing if req_body is empty and request is available
            if (not req_body or len(req_body) == 0) and request and hasattr(request, 'body'):
                
                try:
                    parsed_body = json.loads(request.body.decode('utf-8'))
                    if isinstance(parsed_body, dict):
                        req_body = parsed_body
                except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
                    pass

            standardized_config = []
            for item in field_config:
                key = item[0]
                searchable = item[1] if len(item) > 1 else False
                sortable = item[2] if len(item) > 2 else False
                standardized_config.append(
                    {"key": key, "searchable": searchable, "sortable": sortable}
                )

            page = max(int(req_body.get("page", 1)), 1)
            limit_val = req_body.get("limit")
            is_fetch_all = limit_val in ["all", "All"]
            limit = None if is_fetch_all else (int(limit_val) if limit_val else 10)
            offset = 0 if is_fetch_all else (page - 1) * limit

            model_fields = modelFieldNames(model)

            # Base filters (dict form)
            base_filters = {}

            # Status
            status = req_body.get("status")
            if status is not None and status != "All" and "status" in model_fields:
                if isinstance(status, list) and status:
                    base_filters["status__in"] = status
                else:
                    if status in ["Active", "0", 0]:
                        base_filters["status"] = 0
                    elif status in ["Deactive", "Inactive", "1", 1]:
                        base_filters["status"] = 1
                    elif status in ["Deleted", "2", 2]:
                        base_filters["status"] = 2
                    else:
                        base_filters["status"] = status

            # Filter object
            req_filters = req_body.get("filter")
            if req_filters and isinstance(req_filters, dict):
                for k, v in req_filters.items():
                    if "__" not in k and k not in model_fields:
                        continue
                    if isinstance(v, list) and v:
                        base_filters[f"{k}__in"] = v
                    elif v is not None and v != "":
                        base_filters[k] = v

            # Explicit tenant overrides
            if req_body.get("company_id") and "company" in model_fields:
                base_filters["company_id"] = req_body["company_id"]
            if req_body.get("branch_id") and "branch" in model_fields:
                base_filters["branch_id"] = req_body["branch_id"]
            if req_body.get("user_id") and "user" in model_fields:
                base_filters["user_id"] = req_body["user_id"]

            # Date range
            start_date = req_body.get("startDate")
            end_date = req_body.get("endDate")
            if (start_date or end_date) and date_field in model_fields:
                try:
                    from dateutil.parser import parse
                except Exception:
                    parse = None

                if start_date:
                    if isinstance(start_date, str):
                        if parse:
                            try:
                                start_date = parse(start_date)
                            except Exception:
                                pass
                        else:
                            try:
                                start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                            except Exception:
                                pass
                    if start_date:
                        base_filters[f"{date_field}__gte"] = start_date
                if end_date:
                    if isinstance(end_date, str):
                        if parse:
                            try:
                                end_date = parse(end_date)
                            except Exception:
                                pass
                        else:
                            try:
                                end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                            except Exception:
                                pass
                    if end_date:
                        base_filters[f"{date_field}__lte"] = end_date

            # Build base Q with tenant + status defaults
            q = buildWhere(model, base_filters, tenant_config, request)

            # Search
            allowed_searchable = [f for f in standardized_config if f["searchable"]]
            req_search_fields = req_body.get("searchFields")
            if req_search_fields:
                search_keys = [
                    key
                    for key in req_search_fields
                    if any(f["key"] == key for f in allowed_searchable)
                ]
            else:
                search_keys = [f["key"] for f in allowed_searchable]

            search_term = req_body.get("search")
            if search_term and search_keys:
                search_q = Q()
                for key in search_keys:
                    key_path = key.replace(".", "__")
                    search_q |= Q(**{f"{key_path}__icontains": search_term})
                q &= search_q

            # Custom where (Q or dict)
            if isinstance(custom_where, Q):
                q &= custom_where
            elif isinstance(custom_where, dict) and custom_where:
                q &= Q(**custom_where)

            queryset = model.objects.filter(q)

            # Sorting
            sort_by = req_body.get("sortBy")
            sort_dir = req_body.get("sortDirection", "descending")
            sortable_keys = [f["key"] for f in standardized_config if f["sortable"]]

            if sort_by and sort_by in sortable_keys:
                prefix = "-" if sort_dir == "descending" else ""
                queryset = queryset.order_by(f"{prefix}{sort_by}")
            elif "created_at" in model_fields:
                queryset = queryset.order_by("-created_at")

            # Totals
            totals = {}
            sum_fields = options.get("sumField")
            if sum_fields:
                aggs = {}
                if isinstance(sum_fields, str):
                    aggs[sum_fields] = Sum(sum_fields)
                elif isinstance(sum_fields, list):
                    for f in sum_fields:
                        aggs[f] = Sum(f)
                if aggs:
                    totals = queryset.aggregate(**aggs)

            total_count = queryset.count()

            if not is_fetch_all:
                queryset = queryset[offset : offset + limit]

            if options.get("attributes"):
                queryset = queryset.values(*options["attributes"])

            data = [serializeModelInstance(obj) for obj in list(queryset)]

            return {
                "items": data,
                "total": total_count,
                "totals": totals,
                "currentPage": 1 if is_fetch_all else page,
                "pageSize": total_count if is_fetch_all else limit,
                "totalPages": 1 if is_fetch_all else (total_count + (limit - 1)) // (limit or 1),
                "hasNextPage": False if is_fetch_all else (offset + limit) < total_count,
                "hasPreviousPage": False if is_fetch_all else page > 1,
                "appliedFilters": {
                    **req_body,
                    "searchFields": [f["key"] for f in allowed_searchable],
                    "sortableFields": sortable_keys,
                    "filters": len(base_filters.keys()),
                },
            }
        except Exception:
            logger.exception("Failed to fetch paginated data for %s", model._meta.label)
            raise
