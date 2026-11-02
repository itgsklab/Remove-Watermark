from pypdf import PasswordType, PdfReader
from pypdf.constants import UserAccessPermissions
from pypdf.errors import PyPdfError

from wmrm.application.assets import AssetError


def reject_unsupported_pdf_security(reader: PdfReader) -> None:
    """Reject encrypted or permission-restricted inputs with a precise public error.

    The application intentionally has no password input and never writes a decrypted replacement.
    Empty-password user access is inspected only to distinguish permission restrictions from other
    encryption; it does not make the document eligible for processing.
    """
    if not reader.is_encrypted:
        return

    try:
        password_type = reader.decrypt("")
    except (PyPdfError, RuntimeError, TypeError, ValueError):
        password_type = PasswordType.NOT_DECRYPTED
    if password_type == PasswordType.NOT_DECRYPTED:
        raise AssetError(
            "PASSWORD_REQUIRED",
            "PDF 已加密且需要密码；请在可信工具中解除密码保护后重新上传。",
            422,
        )

    if password_type == PasswordType.USER_PASSWORD:
        permissions = reader.user_access_permissions
        denied: list[str] = []
        if permissions is None or UserAccessPermissions.MODIFY not in permissions:
            denied.append("修改")
        if permissions is None or UserAccessPermissions.EXTRACT not in permissions:
            denied.append("内容提取")
        if denied:
            raise AssetError(
                "PDF_PERMISSION_RESTRICTED",
                f"PDF 权限设置禁止{'和'.join(denied)}；本工具不会绕过文档权限。",
                422,
            )

    raise AssetError(
        "PDF_ENCRYPTION_UNSUPPORTED",
        "PDF 使用加密保护；即使无需输入密码，本工具也不会生成解除加密的新副本。",
        422,
    )
