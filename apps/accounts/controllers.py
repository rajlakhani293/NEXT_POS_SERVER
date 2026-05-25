from apps.accounts.services import AccountsService
from apps.common.responses import success_response


class AccountsController:
    @staticmethod
    def defaultRoles(request):
        data = AccountsService.getDefaultRoleBlueprint()
        return success_response("Default role blueprint fetched successfully.", data=data)

    @staticmethod
    def sendOtp(request, payload):
        data = AccountsService.sendOtp(payload)
        return success_response("OTP generated successfully.", data=data)

    @staticmethod
    def verifyOtp(request, payload):
        data = AccountsService.verifyOtp(request, payload)
        return success_response("OTP verified successfully.", data=data)

    @staticmethod
    def identityLogin(request, payload):
        data = AccountsService.identityLogin(request, payload)
        return success_response("Identity login successful.", data=data)

    @staticmethod
    def googleLogin(request, payload):
        data = AccountsService.googleLogin(request, payload)
        return success_response("Google login successful.", data=data)

    @staticmethod
    def me(request):
        data = AccountsService.currentUser(request.user)
        return success_response("Current user fetched successfully.", data=data)

    @staticmethod
    def logout(request):
        token_value = request.auth.get("token")
        AccountsService.logout(token_value)
        return success_response("Logged out successfully.")

    @staticmethod
    def deleteWorkspace(request):
        data = AccountsService.deleteWorkspace(request.user)
        return success_response("Workspace deleted successfully.", data=data)

    @staticmethod
    def listRoles(request):
        data = AccountsService.listRoles(request.user)
        return success_response("Roles fetched successfully.", data=data)

    @staticmethod
    def createRole(request, payload):
        data = AccountsService.createRole(request.user, payload)
        return success_response("Role created successfully.", data=data)

    @staticmethod
    def updateRole(request, role_id, payload):
        data = AccountsService.updateRole(request.user, role_id, payload)
        return success_response("Role updated successfully.", data=data)

    @staticmethod
    def deleteRole(request, role_id):
        data = AccountsService.deleteRole(request.user, role_id)
        return success_response("Role deleted successfully.", data=data)

    @staticmethod
    def assignRole(request, user_id, payload):
        data = AccountsService.assignRole(request.user, user_id, payload.role_id)
        return success_response("Role assigned successfully.", data=data)
