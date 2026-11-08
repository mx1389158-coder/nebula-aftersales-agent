package com.nebula.security;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties("nebula.security")
public record SecurityProperties(
        String jwtSecret,
        String issuer,
        String audience,
        long accessTokenMinutes,
        String serviceCredential
) {}
