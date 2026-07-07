# type: ignore
import shutil
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from django.conf import settings

from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.responses import successResponse
from apps.settings.services import OptionSettingService


class ModuleService:
    MODULES_DIR = Path(settings.BASE_DIR) / "modules"
    PUBLIC_MODULES_DIR = Path(settings.BASE_DIR) / "public" / "modules"

    @staticmethod
    def modulesDir():
        ModuleService.MODULES_DIR.mkdir(parents=True, exist_ok=True)
        return ModuleService.MODULES_DIR

    @staticmethod
    def publicModulesDir():
        ModuleService.PUBLIC_MODULES_DIR.mkdir(parents=True, exist_ok=True)
        return ModuleService.PUBLIC_MODULES_DIR

    @staticmethod
    def enabledModules(user):
        value = OptionSettingService.getOptionValue(user.company, user.branch, "enabled_modules", [])
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, str) and value:
            return [item.strip() for item in value.split(",") if item.strip()]
        return []

    @staticmethod
    def saveEnabledModules(user, modules):
        selected = []
        for namespace in modules:
            if namespace and namespace not in selected:
                selected.append(namespace)
        OptionSettingService.ensureOptionValue(user.company, user.branch, "enabled_modules", selected, user=user)

    @staticmethod
    def text(root, tag, default=""):
        node = root.find(tag)
        return (node.text or "").strip() if node is not None and node.text is not None else default

    @staticmethod
    def description(root):
        node = root.find("description")
        if node is None:
            return ""
        locales = node.findall("locale")
        if locales:
            values = {}
            for locale in locales:
                lang = locale.attrib.get("lang")
                if lang:
                    values[lang] = (locale.text or "").strip()
            return values
        return (node.text or "").strip()

    @staticmethod
    def dependencies(root):
        requires = root.find("requires")
        if requires is None:
            return {}
        values = {}
        for dependency in requires.findall("dependency"):
            namespace = dependency.attrib.get("namespace")
            if not namespace:
                continue
            values[namespace] = {
                "min-version": dependency.attrib.get("min-version"),
                "max-version": dependency.attrib.get("max-version"),
                "name": (dependency.text or "").strip(),
            }
        return values

    @staticmethod
    def coreRequirements(root):
        core = root.find("core")
        if core is None:
            return {"min-version": None, "max-version": None}
        return {
            "min-version": core.attrib.get("min-version"),
            "max-version": core.attrib.get("max-version"),
        }

    @staticmethod
    def moduleFromDirectory(directory, user):
        config_path = directory / "config.xml"
        if not config_path.exists():
            return None
        try:
            root = ElementTree.parse(config_path).getroot()
        except ElementTree.ParseError:
            return {
                "namespace": directory.name,
                "name": directory.name,
                "author": "",
                "version": "",
                "description": "",
                "enabled": False,
                "autoloaded": False,
                "psr-4-compliance": False,
                "invalid": True,
                "files": [item.name for item in directory.iterdir()],
                "requires": {},
                "core": {"min-version": None, "max-version": None},
            }

        namespace = ModuleService.text(root, "namespace", directory.name)
        index_file = directory / f"{namespace}Module.php"
        enabled = namespace in ModuleService.enabledModules(user)
        psr4 = namespace == directory.name
        return {
            "namespace": namespace,
            "name": ModuleService.text(root, "name", namespace),
            "author": ModuleService.text(root, "author"),
            "version": ModuleService.text(root, "version"),
            "description": ModuleService.description(root),
            "enabled": enabled,
            "autoloaded": False,
            "psr-4-compliance": psr4,
            "invalid": not psr4 or not index_file.exists(),
            "files": [item.name for item in directory.iterdir()],
            "requires": ModuleService.dependencies(root),
            "core": ModuleService.coreRequirements(root),
            "path": str(directory),
            "relativePath": f"modules/{directory.name}/",
        }

    @staticmethod
    def loadModules(user):
        modules = {}
        for directory in sorted(ModuleService.modulesDir().iterdir()):
            if not directory.is_dir():
                continue
            module = ModuleService.moduleFromDirectory(directory, user)
            if module is not None:
                modules[module["namespace"]] = module
        return modules

    @staticmethod
    def filteredModules(user, argument=""):
        modules = ModuleService.loadModules(user)
        if argument == "enabled":
            return {key: item for key, item in modules.items() if item.get("enabled")}
        if argument == "disabled":
            return {key: item for key, item in modules.items() if not item.get("enabled") and not item.get("invalid")}
        if argument == "invalid":
            return {key: item for key, item in modules.items() if item.get("invalid")}
        return modules

    @staticmethod
    def listModules(user, argument=""):
        all_modules = ModuleService.loadModules(user)
        modules = ModuleService.filteredModules(user, argument)
        return successResponse(
            "Modules fetched successfully.",
            data={
                "modules": modules,
                "total_enabled": len([item for item in all_modules.values() if item.get("enabled")]),
                "total_disabled": len([item for item in all_modules.values() if not item.get("enabled") and not item.get("invalid")]),
                "total_invalid": len([item for item in all_modules.values() if item.get("invalid")]),
            },
        )

    @staticmethod
    def getModule(user, namespace):
        module = ModuleService.loadModules(user).get(namespace)
        if not module:
            raise api_error(404, ErrorCodes.NOT_FOUND, f'Unable to locate a module having as identifier "{namespace}".')
        return module

    @staticmethod
    def enable(user, namespace):
        module = ModuleService.getModule(user, namespace)
        if module.get("invalid"):
            raise api_error(400, ErrorCodes.BAD_REQUEST, f'The module "{module.get("name")}" cannot be enabled.')
        if module.get("autoloaded"):
            raise api_error(400, ErrorCodes.BAD_REQUEST, f'The module "{module.get("name")}" is autoloaded and cannot be enabled.')
        enabled = ModuleService.enabledModules(user)
        if namespace not in enabled:
            enabled.append(namespace)
            ModuleService.saveEnabledModules(user, enabled)
        return successResponse("The module has correctly been enabled.", data={"module": namespace})

    @staticmethod
    def disable(user, namespace):
        module = ModuleService.getModule(user, namespace)
        if module.get("autoloaded"):
            raise api_error(400, ErrorCodes.BAD_REQUEST, f'The module "{module.get("name")}" is autoloaded and cannot be disabled.')
        enabled = [item for item in ModuleService.enabledModules(user) if item != namespace]
        ModuleService.saveEnabledModules(user, enabled)
        return successResponse("The Module has been disabled.", data={"module": namespace})

    @staticmethod
    def delete(user, namespace):
        module = ModuleService.getModule(user, namespace)
        if module.get("autoloaded"):
            raise api_error(400, ErrorCodes.BAD_REQUEST, f'The module "{module.get("name")}" is autoloaded and cannot be deleted.')
        ModuleService.disable(user, namespace)
        directory = ModuleService.modulesDir() / namespace
        if directory.exists() and directory.is_dir():
            shutil.rmtree(directory)
        return successResponse(f'The modules "{module.get("name")}" was deleted successfully.', data={"module": namespace})

    @staticmethod
    def archive(user, namespace):
        module = ModuleService.getModule(user, namespace)
        directory = Path(module.get("path") or "")
        if not directory.exists() or not directory.is_dir():
            raise api_error(404, ErrorCodes.NOT_FOUND, "Unable to locate the requested module.")

        archive_root = Path(tempfile.mkdtemp(prefix="module-download-"))
        archive_base = archive_root / namespace
        archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=directory.parent, base_dir=directory.name)
        return Path(archive_path), module

    @staticmethod
    def upload(user, uploaded_file):
        if uploaded_file is None:
            raise api_error(422, ErrorCodes.VALIDATION_ERROR, "The module file is required.")
        if not uploaded_file.name.lower().endswith(".zip"):
            raise api_error(422, ErrorCodes.VALIDATION_ERROR, "Choose the zip file you would like to upload")

        temp_path = ModuleService.modulesDir() / f".upload-{uploaded_file.name}"
        with temp_path.open("wb") as target:
            for chunk in uploaded_file.chunks():
                target.write(chunk)

        try:
            with zipfile.ZipFile(temp_path) as archive:
                names = [name for name in archive.namelist() if name and not name.startswith("__MACOSX/")]
                config_name = next((name for name in names if name.endswith("config.xml")), None)
                if not config_name:
                    raise api_error(400, ErrorCodes.BAD_REQUEST, "Unable to extract the module configuration.")
                top_level = config_name.split("/")[0]
                archive.extractall(ModuleService.modulesDir())
                extracted_dir = ModuleService.modulesDir() / top_level
                module = ModuleService.moduleFromDirectory(extracted_dir, user)
                if not module:
                    raise api_error(400, ErrorCodes.BAD_REQUEST, "Unable to load the uploaded module.")
                return successResponse("The module has been successfully installed.", data={"module": module})
        finally:
            if temp_path.exists():
                temp_path.unlink()

    @staticmethod
    def createSymlink(payload):
        module = (payload or {}).get("module") or {}
        if not module:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Module not specified.")
        ModuleService.publicModulesDir()
        return successResponse("Symbolic link created successfully.", data={"module": module.get("namespace")})

    @staticmethod
    def fixPermissions():
        ModuleService.publicModulesDir()
        return successResponse("Directory permissions fixed successfully.")
