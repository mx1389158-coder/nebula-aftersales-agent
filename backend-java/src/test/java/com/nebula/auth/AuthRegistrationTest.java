package com.nebula.auth;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.nebula.common.BusinessException;
import java.time.Instant;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.security.crypto.password.PasswordEncoder;

class AuthRegistrationTest {
    private UserMapper users;
    private PasswordEncoder passwords;
    private TokenService tokens;
    private AuthService auth;

    @BeforeEach
    void setUp() {
        users = mock(UserMapper.class);
        passwords = mock(PasswordEncoder.class);
        tokens = mock(TokenService.class);
        auth = new AuthService(users, passwords, tokens);
    }

    @Test
    void registersActiveUserAndIssuesToken() {
        when(users.findByLogin("demo", "new@example.com")).thenReturn(null);
        when(passwords.encode("safe-password")).thenReturn("encoded");
        when(tokens.issue(any(UserAccount.class)))
                .thenReturn(new TokenService.IssuedToken("access-token", Instant.parse("2026-11-08T00:00:00Z")));

        Map<String, Object> result = auth.register(
                "demo", " New@Example.com ", " 新用户 ", "safe-password");

        ArgumentCaptor<UserAccount> account = ArgumentCaptor.forClass(UserAccount.class);
        verify(users).insert(account.capture());
        verify(users).insertRole(account.getValue().id(), "USER");
        assertThat(account.getValue().email()).isEqualTo("new@example.com");
        assertThat(account.getValue().displayName()).isEqualTo("新用户");
        assertThat(account.getValue().status()).isEqualTo("ACTIVE");
        assertThat(account.getValue().role()).isEqualTo("USER");
        assertThat(result.get("access_token")).isEqualTo("access-token");
    }

    @Test
    void rejectsAnExistingAccount() {
        when(users.findByLogin("demo", "existing@example.com")).thenReturn(
                new UserAccount(null, "demo", "existing@example.com", "existing@example.com",
                        "encoded", "已有用户", "ACTIVE", "USER"));

        assertThatThrownBy(() -> auth.register(
                "demo", "existing@example.com", "重复用户", "safe-password"))
                .isInstanceOf(BusinessException.class)
                .hasMessage("该邮箱已注册，请直接登录");
        verify(users, never()).insert(any(UserAccount.class));
    }
}
