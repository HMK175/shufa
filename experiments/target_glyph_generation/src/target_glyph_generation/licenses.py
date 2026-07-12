"""字体许可白名单。"""

ACCEPTED_LICENSES = {"OFL-1.1", "Apache-2.0"}


def is_accepted_license(license_id: str) -> bool:
    """仅接受已在项目方案中明确批准的许可标识。"""
    return license_id in ACCEPTED_LICENSES
