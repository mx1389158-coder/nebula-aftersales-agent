package com.nebula.auth;

import com.nebula.security.SecurityProperties;
import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Date;
import java.util.List;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class TokenService {
    private final SecurityProperties properties;

    public TokenService(SecurityProperties properties) { this.properties = properties; }

    public IssuedToken issue(UserAccount user) {
        return issue(user.id().toString(), user.tenantId(), user.username(), List.of(user.role()));
    }

    public IssuedToken issueService(String tenantId) {
        return issue("00000000-0000-0000-0000-000000000200", tenantId,
                "ai-service", List.of("SERVICE"));
    }

    public String serviceCredential() { return properties.serviceCredential(); }

    private IssuedToken issue(String subject, String tenantId, String username, List<String> roles) {
        Instant now = Instant.now();
        Instant expiresAt = now.plus(properties.accessTokenMinutes(), ChronoUnit.MINUTES);
        JWTClaimsSet claims = new JWTClaimsSet.Builder()
                .subject(subject)
                .issuer(properties.issuer())
                .audience(properties.audience())
                .issueTime(Date.from(now))
                .notBeforeTime(Date.from(now.minusSeconds(5)))
                .expirationTime(Date.from(expiresAt))
                .jwtID(UUID.randomUUID().toString())
                .claim("tenant_id", tenantId)
                .claim("role", roles.getFirst())
                .claim("roles", roles)
                .claim("username", username)
                .build();
        SignedJWT jwt = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), claims);
        try {
            jwt.sign(new MACSigner(properties.jwtSecret().getBytes(StandardCharsets.UTF_8)));
        } catch (JOSEException exception) {
            throw new IllegalStateException("无法签发访问令牌", exception);
        }
        return new IssuedToken(jwt.serialize(), expiresAt);
    }

    public record IssuedToken(String value, Instant expiresAt) {}
}
