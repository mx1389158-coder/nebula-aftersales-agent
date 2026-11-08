package com.nebula.common;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.Optional;
import java.util.UUID;
import org.slf4j.MDC;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
public class RequestIdFilter extends OncePerRequestFilter {
    public static final String ATTRIBUTE = "nebula.request_id";
    public static final String TRACE_ATTRIBUTE = "nebula.trace_id";

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        String requestId = Optional.ofNullable(request.getHeader("X-Request-ID"))
                .filter(value -> !value.isBlank()).orElseGet(() -> UUID.randomUUID().toString());
        String traceId = Optional.ofNullable(request.getHeader("X-Trace-ID"))
                .filter(value -> !value.isBlank()).orElse(requestId);
        request.setAttribute(ATTRIBUTE, requestId);
        request.setAttribute(TRACE_ATTRIBUTE, traceId);
        response.setHeader("X-Request-ID", requestId);
        response.setHeader("X-Trace-ID", traceId);
        MDC.put("request_id", requestId);
        MDC.put("trace_id", traceId);
        try {
            filterChain.doFilter(request, response);
        } finally {
            MDC.remove("request_id");
            MDC.remove("trace_id");
        }
    }
}
