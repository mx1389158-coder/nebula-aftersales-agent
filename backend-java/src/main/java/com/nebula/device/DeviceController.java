package com.nebula.device;

import com.nebula.security.BusinessPrincipal;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/business/v1/devices")
public class DeviceController {
    private final DeviceService devices;

    public DeviceController(DeviceService devices) { this.devices = devices; }

    @GetMapping
    List<Map<String, Object>> list(@AuthenticationPrincipal Jwt jwt) {
        return devices.list(BusinessPrincipal.from(jwt));
    }

    @GetMapping("/{id}")
    Map<String, Object> get(@PathVariable UUID id, @AuthenticationPrincipal Jwt jwt) {
        return devices.get(BusinessPrincipal.from(jwt), id);
    }

    @PostMapping("/bind")
    Map<String, Object> bind(@Valid @RequestBody BindRequest request, @AuthenticationPrincipal Jwt jwt) {
        return devices.bind(BusinessPrincipal.from(jwt), request.modelId(), request.firmwareId(),
                request.serialNo(), request.nickname());
    }

    @PatchMapping("/{id}")
    Map<String, Object> update(@PathVariable UUID id, @Valid @RequestBody UpdateRequest request,
                               @AuthenticationPrincipal Jwt jwt) {
        return devices.update(BusinessPrincipal.from(jwt), id, request.nickname(),
                request.firmwareId(), request.version());
    }

    public record BindRequest(@NotNull UUID modelId, @NotNull UUID firmwareId,
                              @NotBlank @Size(max = 100) String serialNo,
                              @Size(max = 120) String nickname) {}
    public record UpdateRequest(@Size(max = 120) String nickname, UUID firmwareId, long version) {}
}
