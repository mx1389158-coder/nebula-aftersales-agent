package com.nebula.auth;

import com.nebula.common.BusinessException;
import com.nebula.security.BusinessPrincipal;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/business/v1")
public class AuthController {
    private final AuthService auth;
    private final UserMapper users;

    public AuthController(AuthService auth, UserMapper users) {
        this.auth = auth;
        this.users = users;
    }

    @PostMapping("/auth/login")
    Map<String, Object> login(@Valid @RequestBody LoginRequest request,
            @RequestHeader(value = "X-Tenant-ID", defaultValue = "demo") String tenantId) {
        return auth.login(tenantId, request.username(), request.password());
    }

    @GetMapping("/users/me")
    Map<String, Object> me(@AuthenticationPrincipal Jwt jwt) {
        BusinessPrincipal principal = BusinessPrincipal.from(jwt);
        UserAccount user = users.findById(principal.tenantId(), principal.userId());
        if (user == null) throw new BusinessException(HttpStatus.NOT_FOUND, "USER_NOT_FOUND", "用户不存在");
        return auth.publicUser(user);
    }

    public record LoginRequest(
            @NotBlank @Size(max = 255) String username,
            @NotBlank @Size(min = 8, max = 256) String password
    ) {}
}
