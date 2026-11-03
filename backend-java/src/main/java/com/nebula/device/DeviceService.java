package com.nebula.device;

import com.nebula.common.BusinessException;
import com.nebula.product.CatalogMapper;
import com.nebula.security.BusinessPrincipal;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class DeviceService {
    private final CatalogMapper catalog;

    public DeviceService(CatalogMapper catalog) { this.catalog = catalog; }

    public List<Map<String, Object>> list(BusinessPrincipal principal) {
        return catalog.listDevices(principal.tenantId(), principal.userId());
    }

    public Map<String, Object> get(BusinessPrincipal principal, UUID id) {
        Map<String, Object> device = catalog.getDevice(principal.tenantId(), id);
        requireOwnership(principal, device);
        return device;
    }

    @Transactional
    public Map<String, Object> bind(BusinessPrincipal principal, UUID modelId, UUID firmwareId,
                                    String serialNo, String nickname) {
        if (catalog.validModelFirmware(principal.tenantId(), modelId, firmwareId) != 1) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "INVALID_MODEL_FIRMWARE", "型号与固件不匹配");
        }
        UUID id = UUID.randomUUID();
        try {
            catalog.insertDevice(id, principal.tenantId(), principal.userId(), modelId, firmwareId,
                    serialNo, nickname);
        } catch (DataIntegrityViolationException exception) {
            throw new BusinessException(HttpStatus.CONFLICT, "DEVICE_ALREADY_BOUND", "设备序列号已绑定");
        }
        return get(principal, id);
    }

    @Transactional
    public Map<String, Object> update(BusinessPrincipal principal, UUID id, String nickname,
                                      UUID firmwareId, long version) {
        Map<String, Object> current = get(principal, id);
        if (firmwareId != null) {
            UUID modelId = (UUID) current.get("model_id");
            if (catalog.validModelFirmware(principal.tenantId(), modelId, firmwareId) != 1) {
                throw new BusinessException(HttpStatus.BAD_REQUEST, "INVALID_MODEL_FIRMWARE", "型号与固件不匹配");
            }
        }
        if (catalog.updateDevice(id, principal.tenantId(), principal.userId(), nickname, firmwareId, version) != 1) {
            throw new BusinessException(HttpStatus.CONFLICT, "OPTIMISTIC_LOCK_CONFLICT", "设备信息已被更新，请刷新后重试");
        }
        return get(principal, id);
    }

    private void requireOwnership(BusinessPrincipal principal, Map<String, Object> device) {
        if (device == null || (!principal.hasRole("ADMIN")
                && !principal.userId().equals(device.get("owner_id")))) {
            throw new BusinessException(HttpStatus.NOT_FOUND, "DEVICE_NOT_FOUND", "设备不存在或无权访问");
        }
    }
}
