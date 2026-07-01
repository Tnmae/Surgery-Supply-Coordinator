"""Role-Based Access Control (RBAC) utilities."""

from enum import Enum
from typing import Set


class UserRole(str, Enum):
    """User roles in the system."""
    OR_COORDINATOR = "OR_COORDINATOR"
    SUPPLY_ADMIN = "SUPPLY_ADMIN"
    BLOOD_BANK_TECH = "BLOOD_BANK_TECH"
    ORGAN_COORDINATOR = "ORGAN_COORDINATOR"
    VIEWER = "VIEWER"


class Permission(str, Enum):
    """System permissions."""
    CHECK_READINESS = "CHECK_READINESS"
    VIEW_SURGERY = "VIEW_SURGERY"
    VIEW_AUDIT_TRAIL = "VIEW_AUDIT_TRAIL"
    MANAGE_INVENTORY = "MANAGE_INVENTORY"
    OVERRIDE_BLOCKER = "OVERRIDE_BLOCKER"


class RBAC:
    """Role-based access control manager."""
    
    # Role to permissions mapping
    ROLE_PERMISSIONS = {
        UserRole.OR_COORDINATOR: {
            Permission.CHECK_READINESS,
            Permission.VIEW_SURGERY,
            Permission.VIEW_AUDIT_TRAIL,
        },
        UserRole.SUPPLY_ADMIN: {
            Permission.CHECK_READINESS,
            Permission.VIEW_SURGERY,
            Permission.VIEW_AUDIT_TRAIL,
            Permission.MANAGE_INVENTORY,
        },
        UserRole.BLOOD_BANK_TECH: {
            Permission.VIEW_SURGERY,
            Permission.VIEW_AUDIT_TRAIL,
            Permission.MANAGE_INVENTORY,
        },
        UserRole.ORGAN_COORDINATOR: {
            Permission.VIEW_SURGERY,
            Permission.VIEW_AUDIT_TRAIL,
            Permission.MANAGE_INVENTORY,
        },
        UserRole.VIEWER: {
            Permission.VIEW_SURGERY,
            Permission.VIEW_AUDIT_TRAIL,
        },
    }
    
    @staticmethod
    def has_permission(role: str, permission: Permission) -> bool:
        """Check if a role has a specific permission."""
        try:
            role_enum = UserRole(role)
            permissions = RBAC.ROLE_PERMISSIONS.get(role_enum, set())
            return permission in permissions
        except ValueError:
            return False
    
    @staticmethod
    def can_check_readiness(role: str) -> bool:
        """Check if a role can check surgery readiness."""
        return RBAC.has_permission(role, Permission.CHECK_READINESS)
    
    @staticmethod
    def can_view_surgery(role: str) -> bool:
        """Check if a role can view surgery details."""
        return RBAC.has_permission(role, Permission.VIEW_SURGERY)
    
    @staticmethod
    def can_view_audit_trail(role: str) -> bool:
        """Check if a role can view audit trails."""
        return RBAC.has_permission(role, Permission.VIEW_AUDIT_TRAIL)
    
    @staticmethod
    def can_manage_inventory(role: str) -> bool:
        """Check if a role can manage inventory."""
        return RBAC.has_permission(role, Permission.MANAGE_INVENTORY)
