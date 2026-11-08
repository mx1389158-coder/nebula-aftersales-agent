package com.nebula.auth;

import com.nebula.audit.AuditService;
import com.nebula.common.BusinessException;
import com.nebula.common.RequestIdFilter;
import com.nebula.security.BusinessPrincipal;
import jakarta.servlet.http.HttpServletRequest;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class UserAdminService {
    private static final Set<String> STATUSES = Set.of("ACTIVE", "DISABLED");
    private static final Set<String> ROLES = Set.of("USER", "SUPPORT", "ADMIN");
    private final UserMapper users;
    private final AuthService auth;
    private final AuditService audit;

    public UserAdminService(UserMapper users, AuthService auth, AuditService audit) {
        this.users = users; this.auth = auth; this.audit = audit;
    }

    public List<Map<String, Object>> list(String tenantId) {
        return users.list(tenantId).stream().map(auth::publicUser).toList();
    }

    @Transactional
    public Map<String, Object> update(BusinessPrincipal principal, UUID id, String status,
                                      String role, HttpServletRequest request) {
        UserAccount target = users.findById(principal.tenantId(), id);
        if (target == null) throw new BusinessException(HttpStatus.NOT_FOUND, "USER_NOT_FOUND", "用户不存在");
        if (status != null) {
            String normalized = status.toUpperCase();
            if (!STATUSES.contains(normalized)) throw new BusinessException(HttpStatus.BAD_REQUEST,
                    "INVALID_USER_STATUS", "用户状态必须是 ACTIVE 或 DISABLED");
            if (principal.userId().equals(id) && "DISABLED".equals(normalized)) {
                throw new BusinessException(HttpStatus.CONFLICT, "CANNOT_DISABLE_SELF", "管理员不能禁用自己");
            }
            users.updateStatus(principal.tenantId(), id, normalized);
        }
        if (role != null) {
            String normalized = role.toUpperCase();
            if (!ROLES.contains(normalized)) throw new BusinessException(HttpStatus.BAD_REQUEST,
                    "INVALID_USER_ROLE", "角色必须是 USER、SUPPORT 或 ADMIN");
            if (principal.userId().equals(id) && !"ADMIN".equals(normalized)) {
                throw new BusinessException(HttpStatus.CONFLICT, "CANNOT_DEMOTE_SELF", "管理员不能移除自己的管理员角色");
            }
            users.deleteRoles(id);
            users.insertRole(id, normalized);
        }
        audit.record(principal.tenantId(), principal.userId(), "USER_UPDATED", "user", id,
                attribute(request, RequestIdFilter.ATTRIBUTE), attribute(request, RequestIdFilter.TRACE_ATTRIBUTE),
                Map.of("status", status == null ? target.status() : status,
                       "role", role == null ? target.role() : role));
        return auth.publicUser(users.findById(principal.tenantId(), id));
    }

    private String attribute(HttpServletRequest request, String name) {
        Object value = request.getAttribute(name);
        return value == null ? null : value.toString();
    }
}
