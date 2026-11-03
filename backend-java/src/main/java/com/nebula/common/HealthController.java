package com.nebula.common;

import java.util.Map;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/business/v1")
public class HealthController {
    private final JdbcTemplate jdbc;

    public HealthController(JdbcTemplate jdbc) { this.jdbc = jdbc; }

    @GetMapping("/health")
    Map<String, Object> health() {
        Integer value = jdbc.queryForObject("SELECT 1", Integer.class);
        return Map.of("status", "ok", "database", value != null && value == 1 ? "ok" : "error");
    }
}
