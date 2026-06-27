# type: ignore
from django.db import transaction
from django.db.models import F
from django.utils.text import slugify

from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import buildUniqueValue, decimalValue as money
from apps.common.responses import successResponse
from apps.customers.models import Customer, CustomerCoupon, CustomerGroup, CustomerReward
from apps.promotions.models import Coupon
from apps.rewards.models import (
    RewardSystemRule,
    RewardSystem,
)


def getRewardRules(system_id, request):
    return commonQuery.findAllRecords(
        RewardSystemRule,
        {"reward_system_id": system_id},
        {"attributes": ["id", "from_amount", "to_amount", "reward"], "order": ["from_amount"]},
        request=request,
        tenant_config=True,
    )


def attachRewardRule(system, request):
    data = dict(system)
    rules = getRewardRules(data["id"], request)
    first_rule = rules[0] if rules else None
    data["rules"] = rules
    data["rule"] = first_rule
    data["from_amount"] = first_rule.get("from_amount") if first_rule else 0
    data["to_amount"] = first_rule.get("to_amount") if first_rule else 0
    data["reward"] = first_rule.get("reward") if first_rule else 0
    data["rule_summary"] = f"{len(rules)} rule(s)" if rules else "-"
    return data


def attachRewardRules(systems, request):
    system_ids = [item["id"] for item in systems]
    if not system_ids:
        return systems

    rules = commonQuery.findAllRecords(
        RewardSystemRule,
        {"reward_system_id__in": system_ids},
        {
            "attributes": [
                "id",
                "reward_system_id",
                "from_amount",
                "to_amount",
                "reward",
            ],
            "order": ["from_amount"],
        },
        request=request,
        tenant_config=True,
    )
    rules_by_system = {}
    for rule in rules:
        rules_by_system.setdefault(rule["reward_system_id"], []).append(rule)

    enriched = []
    for system in systems:
        data = dict(system)
        system_rules = rules_by_system.get(data["id"], [])
        first_rule = system_rules[0] if system_rules else None
        data["rules"] = system_rules
        data["rule"] = first_rule
        data["from_amount"] = first_rule.get("from_amount") if first_rule else 0
        data["to_amount"] = first_rule.get("to_amount") if first_rule else 0
        data["reward"] = first_rule.get("reward") if first_rule else 0
        data["rule_summary"] = f"{len(system_rules)} rule(s)" if system_rules else "-"
        enriched.append(data)
    return enriched


def normalizeRules(data):
    return data.pop("rules", None) or []


def replaceRules(reward_system_id, rules, request):
    commonQuery.hardDeleteRecords(
        RewardSystemRule,
        {"reward_system_id": reward_system_id},
        request=request,
        tenant_config=True,
    )
    for rule in rules or []:
        from_amount = money(rule.get("from_amount") or 0)
        to_amount = money(rule.get("to_amount") or 0)
        reward = money(rule.get("reward") or 0)
        if reward <= 0:
            continue
        if to_amount > 0 and to_amount < from_amount:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Reward rule end amount must be greater than start amount.")
        commonQuery.createRecord(
            RewardSystemRule,
            {
                "reward_system_id": reward_system_id,
                "from_amount": from_amount,
                "to_amount": to_amount,
                "reward": reward,
            },
            request=request,
            tenant_config=True,
        )


def ensureCustomer(customer_id, request):
    customer = commonQuery.findOneRecord(
        Customer,
        customer_id,
        request=request,
        tenant_config=True,
    )
    if customer is None:
        raise api_error(404, ErrorCodes.NOT_FOUND, "Customer not found.")
    return customer


def ensureRewardSystem(reward_system_id, request):
    reward_system = commonQuery.findOneRecord(
        RewardSystem,
        reward_system_id,
        request=request,
        tenant_config=True,
    )
    if reward_system is None:
        raise api_error(404, ErrorCodes.NOT_FOUND, "Reward system not found.")
    return reward_system


def getCustomerRewardSystem(customer, request):
    group_id = customer.get("group_id")
    if not group_id:
        return None

    group = commonQuery.findOneRecord(
        CustomerGroup,
        group_id,
        request=request,
        tenant_config=True,
    )
    if not group or not group.get("reward_system_id"):
        return None

    return ensureRewardSystem(group["reward_system_id"], request)


def findMatchingRule(reward_system_id, cart_total, request):
    amount = money(cart_total)
    rules = getRewardRules(reward_system_id, request)
    for rule in rules:
        from_amount = money(rule.get("from_amount"))
        to_amount = money(rule.get("to_amount"))
        if amount >= from_amount and (to_amount <= 0 or amount <= to_amount):
            return rule
    return None


def getOrCreateBalance(customer_id, reward_system_id, request):
    balance = commonQuery.findOneRecord(
        CustomerReward,
        {"customer_id": customer_id, "reward_id": reward_system_id},
        request=request,
        tenant_config=True,
    )
    if balance:
        return balance

    reward_system = ensureRewardSystem(reward_system_id, request)
    return commonQuery.createRecord(
        CustomerReward,
        {
            "customer_id": customer_id,
            "reward_id": reward_system_id,
            "reward_name": reward_system.get("name") or "",
            "points": 0,
            "target": reward_system.get("target") or 0,
        },
        request=request,
        tenant_config=True,
    )


def buildCustomerCouponCode(coupon, customer_id, request):
    base = slugify(f"{coupon.get('code') or 'reward'}-{customer_id}").upper()
    return buildUniqueValue(CustomerCoupon, request, "code", base)


def issueEligibleRewardCoupons(customer_id, reward_system, balance, request, note=""):
    target = money(reward_system.get("target") or 0)
    current_points = money(balance.get("points") or 0)
    issued_coupons = []

    if target <= 0 or current_points < target:
        return {
            "balance": balance,
            "issued_coupons": issued_coupons,
            "redeemed_points": 0,
        }

    coupon = commonQuery.findOneRecord(
        Coupon,
        reward_system.get("coupon_id"),
        request=request,
        tenant_config=True,
    )
    if coupon is None:
        return {
            "balance": balance,
            "issued_coupons": issued_coupons,
            "redeemed_points": 0,
        }

    redeemed_points = 0
    while current_points >= target:
        customer_coupon = commonQuery.createRecord(
            CustomerCoupon,
            {
                "coupon_id": coupon["id"],
                "customer_id": customer_id,
                "name": coupon.get("name") or "",
                "limit_usage": coupon.get("limit_usage") or 0,
                "code": buildCustomerCouponCode(coupon, customer_id, request),
            },
            request=request,
            tenant_config=True,
        )
        commonQuery.branchScopedQueryset(CustomerReward, {"id": balance["id"]}, request).update(
            points=F("points") - target,
        )
        current_points -= target
        redeemed_points += target
        issued_coupons.append(customer_coupon)

    updated_balance = commonQuery.findOneRecord(
        CustomerReward,
        balance["id"],
        request=request,
        tenant_config=True,
    )
    return {
        "balance": updated_balance,
        "issued_coupons": issued_coupons,
        "redeemed_points": redeemed_points,
    }


class RewardSystemService:
    @staticmethod
    def create(data, request):
        with transaction.atomic():
            rules = normalizeRules(data)
            system = commonQuery.createRecord(
                RewardSystem,
                data,
                request=request,
                tenant_config=True,
            )
            replaceRules(system["id"], rules, request)
            return successResponse(
                "Reward system created successfully.",
                data=attachRewardRule(system, request),
            )

    @staticmethod
    def getAll(data, request):
        fieldConfig = [["name", True, True]]
        options = {
            "attributes": ["id", "name", "coupon_id", "target", "description", "status", "created_at"],
        }
        result = commonQuery.fetchPaginatedData(
            RewardSystem,
            data,
            fieldConfig,
            options,
            request=request,
            tenant_config=True,
        )
        result["items"] = attachRewardRules(result["items"], request)

        # Batch-fetch coupon names for all coupon_ids in the page
        coupon_ids = [item["coupon_id"] for item in result["items"] if item.get("coupon_id")]
        coupon_name_map = {}
        if coupon_ids:
            coupons = commonQuery.findAllRecords(
                Coupon,
                {"id__in": coupon_ids},
                {"attributes": ["id", "name"]},
                request=request,
                tenant_config=True,
            )
            coupon_name_map = {c["id"]: c["name"] for c in coupons}

        # Enrich each item with coupon_name and rule count.
        for item in result["items"]:
            item["coupon_name"] = coupon_name_map.get(item.get("coupon_id")) or "-"
            rule_count = len(item.get("rules") or [])
            item["name"] = f"{item['name']} ({rule_count})"

        return successResponse("Reward systems retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(
            RewardSystem,
            {},
            {"attributes": ["id", "name", "target"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Dropdown list retrieved successfully.", data=data)

    @staticmethod
    def getById(reward_system_id, request):
        reward_system = ensureRewardSystem(reward_system_id, request)
        return successResponse(
            "Reward system retrieved successfully.",
            data=attachRewardRule(reward_system, request),
        )

    @staticmethod
    def update(data, request, reward_system_id):
        with transaction.atomic():
            has_rule_update = "rules" in data
            rules = normalizeRules(data) if has_rule_update else []
            ensureRewardSystem(reward_system_id, request)

            updated = commonQuery.updateRecordById(
                RewardSystem,
                reward_system_id,
                data,
                request=request,
                tenant_config=True,
            )
            if has_rule_update:
                replaceRules(reward_system_id, rules, request)
            return successResponse(
                "Reward system updated successfully.",
                data=attachRewardRule(updated, request),
            )

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(
            RewardSystem,
            data.get("ids"),
            request=request,
            tenant_config=True,
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Reward system not found.")
        return successResponse("Reward systems deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        count = commonQuery.updateStatusById(
            RewardSystem,
            data.get("ids"),
            status,
            request=request,
            tenant_config=True,
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Reward system not found.")
        return successResponse(
            "Reward system status updated successfully.",
            data={"updated_count": count, "status": status},
        )


class CustomerRewardService:
    @staticmethod
    def getBalances(data, request):
        result = commonQuery.fetchPaginatedData(
            CustomerReward,
            data,
            [["customer__first_name", True, True], ["customer__last_name", True, True], ["reward_name", True, True]],
            {
                "attributes": [
                    "id",
                    "customer_id",
                    "customer__first_name",
                    "customer__last_name",
                    "reward_id",
                    "reward_name",
                    "points",
                    "target",
                    "status",
                ],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Reward balances retrieved successfully.", data=result)

    @staticmethod
    def getRedemptions(data, request):
        result = commonQuery.fetchPaginatedData(
            CustomerCoupon,
            data,
            [["customer__full_name", True, True], ["name", True, True], ["code", True, True]],
            {
                "attributes": [
                    "id",
                    "customer_id",
                    "customer__full_name",
                    "coupon_id",
                    "coupon__name",
                    "code",
                    "usage",
                    "limit_usage",
                    "created_at",
                    "status",
                ],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Reward redemptions retrieved successfully.", data=result)

    @staticmethod
    def getBalance(customer_id, request):
        ensureCustomer(customer_id, request)
        systems = commonQuery.findAllRecords(
            RewardSystem,
            {},
            {"attributes": ["id", "name", "target"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        balances = [
            {
                **getOrCreateBalance(customer_id, system["id"], request),
                "reward_system_name": system["name"],
            }
            for system in systems
        ]
        return successResponse("Reward balance retrieved successfully.", data=balances)

    @staticmethod
    def earn(data, request):
        points = money(data.get("points") or 0)
        if points <= 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Points must be greater than 0.")
        ensureCustomer(data.get("customer_id"), request)
        reward_system = ensureRewardSystem(data.get("reward_system_id"), request)
        with transaction.atomic():
            balance = getOrCreateBalance(data["customer_id"], data["reward_system_id"], request)
            commonQuery.branchScopedQueryset(CustomerReward, {"id": balance["id"]}, request).update(
                points=F("points") + points,
            )
            updated = commonQuery.findOneRecord(
                CustomerReward,
                balance["id"],
                request=request,
                tenant_config=True,
            )
            issued = issueEligibleRewardCoupons(
                data["customer_id"],
                reward_system,
                updated,
                request,
                data.get("note") or "Reward points adjusted manually.",
            )
            return successResponse(
                "Reward points added successfully.",
                data={
                    "earned_points": points,
                    "balance": issued["balance"],
                    "issued_coupons": issued["issued_coupons"],
                    "redeemed_points": issued["redeemed_points"],
                },
            )

    @staticmethod
    def processSaleReward(data, request):
        customer = ensureCustomer(data.get("customer_id"), request)
        cart_total = money(data.get("cart_total"))
        if cart_total <= 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Cart total must be greater than 0.")

        reward_system = getCustomerRewardSystem(customer, request)
        if not reward_system:
            return {
                "earned_points": 0,
                "issued_coupons": [],
                "balance": None,
                "matched_rule": None,
                "reward_system": None,
                "sale_order_id": data.get("sale_order_id"),
                "message": "No reward system configured for this customer.",
            }

        rule = findMatchingRule(reward_system["id"], cart_total, request)
        if not rule:
            balance = getOrCreateBalance(customer["id"], reward_system["id"], request)
            return {
                "earned_points": 0,
                "issued_coupons": [],
                "balance": balance,
                "matched_rule": None,
                "reward_system": reward_system,
                "sale_order_id": data.get("sale_order_id"),
                "message": "No reward rule matched this cart value.",
            }

        earned_points = money(rule.get("reward") or 0)
        with transaction.atomic():
            balance = getOrCreateBalance(customer["id"], reward_system["id"], request)
            commonQuery.branchScopedQueryset(CustomerReward, {"id": balance["id"]}, request).update(
                points=F("points") + earned_points,
            )
            updated = commonQuery.findOneRecord(
                CustomerReward,
                balance["id"],
                request=request,
                tenant_config=True,
            )
            issued = issueEligibleRewardCoupons(
                customer["id"],
                reward_system,
                updated,
                request,
                data.get("note") or f"Reward earned from sale #{data.get('sale_order_id') or ''}".strip(),
            )

        return {
            "customer_id": customer["id"],
            "cart_total": cart_total,
            "earned_points": earned_points,
            "matched_rule": rule,
            "reward_system": reward_system,
            "balance": issued["balance"],
            "issued_coupons": issued["issued_coupons"],
            "redeemed_points": issued["redeemed_points"],
            "sale_order_id": data.get("sale_order_id"),
            "message": "Reward points processed successfully.",
        }

    @staticmethod
    def earnFromSale(data, request):
        result = CustomerRewardService.processSaleReward(data, request)
        return successResponse(result.get("message") or "Reward points processed successfully.", data=result)

    @staticmethod
    def redeem(data, request):
        points = money(data.get("points") or 0)
        if points <= 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Points must be greater than 0.")
        ensureCustomer(data.get("customer_id"), request)
        reward_system = ensureRewardSystem(data.get("reward_system_id"), request)
        with transaction.atomic():
            balance = getOrCreateBalance(data["customer_id"], data["reward_system_id"], request)
            if money(balance.get("points") or 0) < points:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Customer does not have enough reward points.")

            coupon = commonQuery.findOneRecord(
                Coupon,
                reward_system.get("coupon_id"),
                request=request,
                tenant_config=True,
            )
            if coupon is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Reward coupon not found.")

            customer_coupon = commonQuery.createRecord(
                CustomerCoupon,
                {
                    "coupon_id": coupon["id"],
                    "customer_id": data["customer_id"],
                    "name": coupon.get("name") or "",
                    "limit_usage": coupon.get("limit_usage") or 0,
                    "code": buildCustomerCouponCode(coupon, data["customer_id"], request),
                },
                request=request,
                tenant_config=True,
            )
            commonQuery.branchScopedQueryset(CustomerReward, {"id": balance["id"]}, request).update(
                points=F("points") - points,
            )
            updated_balance = commonQuery.findOneRecord(
                CustomerReward,
                balance["id"],
                request=request,
                tenant_config=True,
            )
            return successResponse(
                "Reward points redeemed successfully.",
                data={
                    "balance": updated_balance,
                    "issued_coupon": customer_coupon,
                },
            )

    @staticmethod
    def jobHandlers():
        return {
            "process_sale_reward": lambda data, job: CustomerRewardService.earnFromSale(
                data or {},
                CustomerRewardService.requestFromJob(job),
            ),
            "apply_customer_reward": lambda data, job: CustomerRewardService.earnFromSale(
                data or {},
                CustomerRewardService.requestFromJob(job),
            ),
            "redeem_customer_reward": lambda data, job: CustomerRewardService.redeem(
                data or {},
                CustomerRewardService.requestFromJob(job),
            ),
        }

    @staticmethod
    def requestFromJob(job):
        from apps.common.helpers import requestFromJobUser

        return requestFromJobUser(job)
