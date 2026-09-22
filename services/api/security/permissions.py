from fastapi import HTTPException, status
from typing import List


class Roles:
    OWNER = "Owner"
    ADMIN = "Admin"
    CODER = "Coder"
    REVIEWER = "Reviewer"
    READ_ONLY = "Read-only"

    ALL = [OWNER, ADMIN, CODER, REVIEWER, READ_ONLY]


def require_roles(allowed_roles: List[str]):
    def role_checker(current_user):
        if current_user.role not in allowed_roles and current_user.role != Roles.OWNER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this operation."
            )
        return current_user
    return role_checker
