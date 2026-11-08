package com.nebula.product;

import com.nebula.security.BusinessPrincipal;
import com.nebula.audit.AuditService;
import com.nebula.common.RequestIdFilter;
import jakarta.servlet.http.HttpServletRequest;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.time.LocalDate;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.RequestBody;

@RestController
@RequestMapping("/api/business/v1/products")
public class ProductController {
    private final ProductService products;
    private final AuditService audit;

    public ProductController(ProductService products, AuditService audit) {
        this.products = products; this.audit = audit;
    }

    @GetMapping
    List<Map<String, Object>> list(@AuthenticationPrincipal Jwt jwt) {
        return products.list(BusinessPrincipal.from(jwt).tenantId());
    }

    @GetMapping("/{id}")
    Map<String, Object> get(@PathVariable UUID id, @AuthenticationPrincipal Jwt jwt) {
        return products.get(BusinessPrincipal.from(jwt).tenantId(), id);
    }

    @GetMapping("/models/{modelId}/firmwares")
    List<Map<String, Object>> firmwares(@PathVariable UUID modelId, @AuthenticationPrincipal Jwt jwt) {
        return products.firmwares(BusinessPrincipal.from(jwt).tenantId(), modelId);
    }

    @PostMapping
    @PreAuthorize("hasRole('ADMIN')")
    Map<String, Object> create(@Valid @RequestBody ProductRequest body, @AuthenticationPrincipal Jwt jwt,
                               HttpServletRequest request) {
        BusinessPrincipal principal = BusinessPrincipal.from(jwt);
        Map<String, Object> result = products.create(principal.tenantId(), body.productCode(), body.name(), body.category());
        record(principal, "PRODUCT_CREATED", "product", (UUID) result.get("id"), request);
        return result;
    }

    @PatchMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    Map<String, Object> update(@PathVariable UUID id, @Valid @RequestBody ProductUpdate body,
            @AuthenticationPrincipal Jwt jwt, HttpServletRequest request) {
        BusinessPrincipal principal = BusinessPrincipal.from(jwt);
        Map<String, Object> result = products.update(principal.tenantId(), id, body.name(), body.category());
        record(principal, "PRODUCT_UPDATED", "product", id, request);
        return result;
    }

    @PostMapping("/{productId}/models")
    @PreAuthorize("hasRole('ADMIN')")
    Map<String, Object> createModel(@PathVariable UUID productId, @Valid @RequestBody ModelRequest body,
            @AuthenticationPrincipal Jwt jwt, HttpServletRequest request) {
        BusinessPrincipal principal = BusinessPrincipal.from(jwt);
        Map<String, Object> result = products.createModel(principal.tenantId(), productId, body.modelCode(), body.name());
        record(principal, "PRODUCT_MODEL_CREATED", "product_model", (UUID) result.get("id"), request);
        return result;
    }

    @PostMapping("/models/{modelId}/firmwares")
    @PreAuthorize("hasRole('ADMIN')")
    Map<String, Object> createFirmware(@PathVariable UUID modelId,
            @Valid @RequestBody FirmwareRequest body, @AuthenticationPrincipal Jwt jwt,
            HttpServletRequest request) {
        BusinessPrincipal principal = BusinessPrincipal.from(jwt);
        Map<String, Object> result = products.createFirmware(principal.tenantId(), modelId,
                body.version(), body.releasedAt());
        record(principal, "FIRMWARE_CREATED", "firmware", (UUID) result.get("id"), request);
        return result;
    }

    private void record(BusinessPrincipal principal, String action, String resourceType,
                        UUID resourceId, HttpServletRequest request) {
        Object requestId = request.getAttribute(RequestIdFilter.ATTRIBUTE);
        Object traceId = request.getAttribute(RequestIdFilter.TRACE_ATTRIBUTE);
        audit.record(principal.tenantId(), principal.userId(), action, resourceType, resourceId,
                requestId == null ? null : requestId.toString(),
                traceId == null ? null : traceId.toString(), Map.of());
    }

    public record ProductRequest(@NotBlank @Size(max = 64) String productCode,
            @NotBlank @Size(max = 160) String name, @NotBlank @Size(max = 80) String category) {}
    public record ProductUpdate(@NotBlank @Size(max = 160) String name,
            @NotBlank @Size(max = 80) String category) {}
    public record ModelRequest(@NotBlank @Size(max = 64) String modelCode,
            @NotBlank @Size(max = 160) String name) {}
    public record FirmwareRequest(@NotBlank @Size(max = 40) String version,
            @jakarta.validation.constraints.NotNull LocalDate releasedAt) {}
}
