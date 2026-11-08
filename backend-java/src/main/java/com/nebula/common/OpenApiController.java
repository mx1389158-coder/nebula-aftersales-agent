package com.nebula.common;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class OpenApiController {
    @GetMapping("/api/business/v1/openapi.json")
    Map<String, Object> spec() {
        Map<String, Object> paths = new LinkedHashMap<>();
        operation(paths, "/api/business/v1/auth/login", "post", "用户登录", false);
        operation(paths, "/api/business/v1/auth/register", "post", "用户注册", false);
        operation(paths, "/api/business/v1/auth/service-token", "post", "签发服务身份令牌", false);
        operation(paths, "/api/business/v1/users/me", "get", "当前用户", true);
        operation(paths, "/api/business/v1/products", "get", "产品目录", true);
        operation(paths, "/api/business/v1/products", "post", "新建产品（管理员）", true);
        operation(paths, "/api/business/v1/devices", "get", "我的设备", true);
        operation(paths, "/api/business/v1/devices/bind", "post", "绑定设备", true);
        operation(paths, "/api/business/v1/tickets", "get", "工单列表", true);
        operation(paths, "/api/business/v1/tickets", "post", "幂等创建工单", true);
        operation(paths, "/api/business/v1/tickets/{id}", "get", "工单详情与事件", true);
        operation(paths, "/api/business/v1/tickets/{id}/status", "patch", "售后更新状态", true);
        operation(paths, "/api/business/v1/tickets/idempotency/{key}", "get", "幂等结果查询", true);
        operation(paths, "/api/business/v1/admin/users", "get", "用户管理", true);
        operation(paths, "/api/business/v1/admin/audit-logs", "get", "审计日志", true);
        return Map.of(
                "openapi", "3.1.0",
                "info", Map.of("title", "Nebula Business API", "version", "2.1.0"),
                "servers", List.of(Map.of("url", "/")),
                "components", Map.of("securitySchemes", Map.of("bearerAuth", Map.of(
                        "type", "http", "scheme", "bearer", "bearerFormat", "JWT"))),
                "paths", paths);
    }

    @SuppressWarnings("unchecked")
    private void operation(Map<String, Object> paths, String path, String method,
                           String summary, boolean secured) {
        Map<String, Object> item = (Map<String, Object>) paths.computeIfAbsent(path,
                ignored -> new LinkedHashMap<String, Object>());
        Map<String, Object> operation = new LinkedHashMap<>();
        operation.put("summary", summary);
        operation.put("responses", Map.of("200", Map.of("description", "成功")));
        if (secured) operation.put("security", List.of(Map.of("bearerAuth", List.of())));
        item.put(method, operation);
    }
}
