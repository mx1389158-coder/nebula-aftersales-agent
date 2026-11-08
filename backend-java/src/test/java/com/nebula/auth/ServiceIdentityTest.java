package com.nebula.auth;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;

import com.nebula.common.BusinessException;
import com.nebula.security.SecurityProperties;
import com.nimbusds.jwt.SignedJWT;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.security.crypto.password.PasswordEncoder;

class ServiceIdentityTest {
    private AuthService auth;

    @BeforeEach
    void setUp() {
        SecurityProperties properties = new SecurityProperties(
                "service-identity-test-secret-at-least-32-bytes", "issuer", "audience", 5,
                "expected-credential");
        auth = new AuthService(mock(UserMapper.class), mock(PasswordEncoder.class),
                new TokenService(properties));
    }

    @Test
    void rejectsWrongServiceCredential() {
        assertThatThrownBy(() -> auth.serviceToken("demo", "wrong"))
                .isInstanceOf(BusinessException.class);
    }

    @Test
    void rejectsAllServiceTokensWhenCredentialIsDisabled() {
        SecurityProperties disabled = new SecurityProperties(
                "service-identity-test-secret-at-least-32-bytes", "issuer", "audience", 5, "");
        AuthService disabledAuth = new AuthService(
                mock(UserMapper.class), mock(PasswordEncoder.class), new TokenService(disabled));

        assertThatThrownBy(() -> disabledAuth.serviceToken("demo", "public-default"))
                .isInstanceOf(BusinessException.class);
    }

    @Test
    void issuesTenantScopedServiceToken() throws Exception {
        Map<String, Object> response = auth.serviceToken("demo", "expected-credential");
        SignedJWT jwt = SignedJWT.parse((String) response.get("access_token"));
        assertThat(jwt.getJWTClaimsSet().getSubject())
                .isEqualTo("00000000-0000-0000-0000-000000000200");
        assertThat(jwt.getJWTClaimsSet().getStringClaim("tenant_id")).isEqualTo("demo");
        assertThat(jwt.getJWTClaimsSet().getStringListClaim("roles")).containsExactly("SERVICE");
    }
}
