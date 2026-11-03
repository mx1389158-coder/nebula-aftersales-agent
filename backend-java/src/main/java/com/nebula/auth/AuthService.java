package com.nebula.auth;

import com.nebula.common.BusinessException;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

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
        TokenService.IssuedToken token = tokens.issue(user);
        return Map.of(
                "access_token", token.value(),
                "token_type", "bearer",
                "expires_at", token.expiresAt(),
                "user", publicUser(user));
    }

    public Map<String, Object> publicUser(UserAccount user) {
        return Map.of(
                "id", user.id(), "tenant_id", user.tenantId(), "username", user.username(),
                "email", user.email(), "display_name", user.displayName(), "role", user.role());
    }
}
