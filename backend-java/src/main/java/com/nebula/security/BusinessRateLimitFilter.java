package com.nebula.security;

import tools.jackson.databind.ObjectMapper;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.time.Duration;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.RedisConnectionFailureException;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.MediaType;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
public class BusinessRateLimitFilter extends OncePerRequestFilter {
    private final StringRedisTemplate redis;
    private final ObjectMapper objectMapper;
    private final int limit;
    private final int windowSeconds;

    public BusinessRateLimitFilter(StringRedisTemplate redis, ObjectMapper objectMapper,
            @Value("${nebula.rate-limit.requests:180}") int limit,
            @Value("${nebula.rate-limit.window-seconds:60}") int windowSeconds) {
        this.redis = redis;
        this.objectMapper = objectMapper;
        this.limit = limit;
        this.windowSeconds = windowSeconds;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        String subject = authentication != null && authentication.isAuthenticated()
                ? authentication.getName() : request.getRemoteAddr();
        String bucket = Long.toString(System.currentTimeMillis() / (windowSeconds * 1000L));
        String key = "business:rate:" + subject + ":" + bucket;
        try {
            Long value = redis.opsForValue().increment(key);
            if (value != null && value == 1L) redis.expire(key, Duration.ofSeconds(windowSeconds + 2L));
            if (value != null && value > limit) {
                response.setStatus(429);
                response.setContentType(MediaType.APPLICATION_JSON_VALUE);
                objectMapper.writeValue(response.getOutputStream(), Map.of(
                        "status", "error", "error_code", "RATE_LIMITED",
                        "message", "请求过于频繁，请稍后再试"));
                return;
            }
        } catch (RedisConnectionFailureException ignored) {
            // Redis 不可用时限流降级，但业务事实仍由 PostgreSQL 保证。
        }
        filterChain.doFilter(request, response);
    }
}
