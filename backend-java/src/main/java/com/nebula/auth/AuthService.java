package com.nebula.auth;

import com.nebula.common.BusinessException;
import java.util.Map;
import java.util.Locale;
import java.util.UUID;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AuthService {
    private final UserMapper users;
    private final PasswordEncoder passwords;
    private final TokenService tokens;

    public AuthService(UserMapper users, PasswordEncoder passwords, TokenService tokens) {
        this.users = users;
        this.passwords = passwords;
        this.tokens = tokens;
    }

    public Map<String, Object> login(String tenantId, String login, String password) {
        UserAccount user = users.findByLogin(tenantId, login);
        if (user == null || !"ACTIVE".equals(user.status())
                || !passwords.matches(password, user.passwordHash())) {
            throw new BusinessException(HttpStatus.UNAUTHORIZED, "INVALID_CREDENTIALS", "用户名或密码错误");
        }
        return authenticated(user);
    }

    @Transactional
    public Map<String, Object> register(String tenantId, String email, String displayName,
                                        String password) {
        String normalizedEmail = email.trim().toLowerCase(Locale.ROOT);
        String normalizedName = displayName.trim();
        if (users.findByLogin(tenantId, normalizedEmail) != null) {
            throw new BusinessException(HttpStatus.CONFLICT, "ACCOUNT_ALREADY_EXISTS",
                    "该邮箱已注册，请直接登录");
        }

        UserAccount account = new UserAccount(UUID.randomUUID(), tenantId, normalizedEmail,
                normalizedEmail, passwords.encode(password), normalizedName, "ACTIVE", "USER");
        try {
            users.insert(account);
            users.insertRole(account.id(), "USER");
        } catch (DuplicateKeyException exception) {
            throw new BusinessException(HttpStatus.CONFLICT, "ACCOUNT_ALREADY_EXISTS",
                    "该邮箱已注册，请直接登录");
        }
        return authenticated(account);
    }

    public Map<String, Object> serviceToken(String tenantId, String credential) {
        String expected = tokens.serviceCredential();
        if (expected == null || expected.isBlank() || credential == null
                || !MessageDigest.isEqual(expected.getBytes(StandardCharsets.UTF_8),
                        credential.getBytes(StandardCharsets.UTF_8))) {
            throw new BusinessException(HttpStatus.UNAUTHORIZED, "INVALID_SERVICE_CREDENTIAL",
                    "服务凭据无效");
        }
        TokenService.IssuedToken token = tokens.issueService(tenantId);
        return Map.of("access_token", token.value(), "token_type", "bearer",
                "expires_at", token.expiresAt());
    }

    public Map<String, Object> publicUser(UserAccount user) {
        return Map.of(
                "id", user.id(), "tenant_id", user.tenantId(), "username", user.username(),
                "email", user.email(), "display_name", user.displayName(), "role", user.role(),
                "status", user.status());
    }

    private Map<String, Object> authenticated(UserAccount user) {
        TokenService.IssuedToken token = tokens.issue(user);
        return Map.of(
                "access_token", token.value(),
                "token_type", "bearer",
                "expires_at", token.expiresAt(),
                "user", publicUser(user));
    }
}
