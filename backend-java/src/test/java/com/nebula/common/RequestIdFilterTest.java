package com.nebula.common;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

class RequestIdFilterTest {
    @Test
    void preservesRequestAndTraceAcrossTheResponse() throws Exception {
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.addHeader("X-Request-ID", "request-1");
        request.addHeader("X-Trace-ID", "trace-1");
        MockHttpServletResponse response = new MockHttpServletResponse();

        new RequestIdFilter().doFilter(request, response, new MockFilterChain());

        assertThat(request.getAttribute(RequestIdFilter.ATTRIBUTE)).isEqualTo("request-1");
        assertThat(request.getAttribute(RequestIdFilter.TRACE_ATTRIBUTE)).isEqualTo("trace-1");
        assertThat(response.getHeader("X-Request-ID")).isEqualTo("request-1");
        assertThat(response.getHeader("X-Trace-ID")).isEqualTo("trace-1");
    }
}
