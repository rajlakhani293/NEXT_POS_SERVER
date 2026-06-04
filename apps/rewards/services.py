# type: ignore
from django.db import transaction
from django.db.models import F

from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.responses import successResponse
from apps.customers.models import Customer
from apps.rewards.models import (
    CustomerRewardBalance,
    RewardRedemption,
    RewardRule,
    RewardSystem,
)


def getRewardRules(system_id, request):
    return commonQuery.findAllRecords(
        RewardRule,
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


def normalizeRules(data):
    if "rules" in data:
        return data.pop("rules") or []
    legacy_rule = {
        "from_amount": data.pop("from_amount", 0) or 0,
        "to_amount": data.pop("to_amount", 0) or 0,
        "reward": data.pop("reward", 0) or 0,
    }
    return [legacy_rule] if legacy_rule["reward"] else []


def replaceRules(reward_system_id, rules, request):
    commonQuery.hardDeleteRecords(
        RewardRule,
        {"reward_system_id": reward_system_id},
        request=request,
        tenant_config=True,
    )
    for rule in rules or []:
        reward = int(rule.get("reward") or 0)
        if reward <= 0:
            continue
        commonQuery.createRecord(
            RewardRule,
            {
                "reward_system_id": reward_system_id,
                "from_amount": rule.get("from_amount") or 0,
                "to_amount": rule.get("to_amount") or 0,
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


def getOrCreateBalance(customer_id, reward_system_id, request):
    balance = commonQuery.findOneRecord(
        CustomerRewardBalance,
        {"customer_id": customer_id, "reward_system_id": reward_system_id},
        request=request,
        tenant_config=True,
    )
    if balance:
        return balance

    reward_system = ensureRewardSystem(reward_system_id, request)
    return commonQuery.createRecord(
        CustomerRewardBalance,
        {
            "customer_id": customer_id,
            "reward_system_id": reward_system_id,
            "points": 0,
            "lifetime_points": 0,
            "target_points": reward_system.get("target") or 0,
        },
        request=request,
        tenant_config=True,
    )


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
            "attributes": ["id", "name", "coupon_id", "target", "description", "status"],
        }
        result = commonQuery.fetchPaginatedData(
            RewardSystem,
            data,
            fieldConfig,
            options,
            request=request,
            tenant_config=True,
        )
        result["items"] = [attachRewardRule(item, request) for item in result["items"]]
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
            has_rule_update = "rules" in data or any(key in data for key in ["from_amount", "to_amount", "reward"])
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
        if status not in [0, 1]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Status must be 0 or 1.")
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
        points = int(data.get("points") or 0)
        if points <= 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Points must be greater than 0.")
        ensureCustomer(data.get("customer_id"), request)
        ensureRewardSystem(data.get("reward_system_id"), request)
        balance = getOrCreateBalance(data["customer_id"], data["reward_system_id"], request)
        CustomerRewardBalance.objects.filter(id=balance["id"]).update(
            points=F("points") + points,
            lifetime_points=F("lifetime_points") + points,
        )
        updated = commonQuery.findOneRecord(
            CustomerRewardBalance,
            balance["id"],
            request=request,
            tenant_config=True,
        )
        return successResponse("Reward points added successfully.", data=updated)

    @staticmethod
    def redeem(data, request):
        points = int(data.get("points") or 0)
        if points <= 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Points must be greater than 0.")
        ensureCustomer(data.get("customer_id"), request)
        ensureRewardSystem(data.get("reward_system_id"), request)
        with transaction.atomic():
            balance = getOrCreateBalance(data["customer_id"], data["reward_system_id"], request)
            if int(balance.get("points") or 0) < points:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Customer does not have enough reward points.")

            CustomerRewardBalance.objects.filter(id=balance["id"]).update(
                points=F("points") - points,
            )
            redemption = commonQuery.createRecord(
                RewardRedemption,
                {
                    "customer_id": data["customer_id"],
                    "reward_system_id": data["reward_system_id"],
                    "points_redeemed": points,
                    "note": data.get("note") or "",
                },
                request=request,
                tenant_config=True,
            )
            updated_balance = commonQuery.findOneRecord(
                CustomerRewardBalance,
                balance["id"],
                request=request,
                tenant_config=True,
            )
            return successResponse(
                "Reward points redeemed successfully.",
                data={"redemption": redemption, "balance": updated_balance},
            )
