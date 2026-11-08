package com.nebula.product;

import com.nebula.common.BusinessException;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import tools.jackson.core.JacksonException;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.ObjectMapper;

@Service
public class ProductService {
    private final CatalogMapper catalog;
    private final ObjectMapper json;

    public ProductService(CatalogMapper catalog, ObjectMapper json) {
        this.catalog = catalog;
        this.json = json;
    }

    @Cacheable(cacheNames = "business-products", key = "#tenantId")
    public List<Map<String, Object>> list(String tenantId) {
        return catalog.listProducts(tenantId).stream().map(this::normalizeModels).toList();
    }

    @Cacheable(cacheNames = "business-product", key = "#tenantId + ':' + #id")
    public Map<String, Object> get(String tenantId, UUID id) {
        Map<String, Object> product = catalog.getProduct(tenantId, id);
        if (product == null) throw new BusinessException(HttpStatus.NOT_FOUND, "PRODUCT_NOT_FOUND", "产品不存在");
        return normalizeModels(product);
    }

    public List<Map<String, Object>> firmwares(String tenantId, UUID modelId) {
        return catalog.listFirmwares(tenantId, modelId);
    }

    @CacheEvict(cacheNames = {"business-products", "business-product"}, allEntries = true)
    public Map<String, Object> create(String tenantId, String code, String name, String category) {
        UUID id = UUID.randomUUID();
        catalog.insertProduct(id, tenantId, code.trim(), name.trim(), category.trim());
        return getUncached(tenantId, id);
    }

    @CacheEvict(cacheNames = {"business-products", "business-product"}, allEntries = true)
    public Map<String, Object> update(String tenantId, UUID id, String name, String category) {
        if (catalog.updateProduct(tenantId, id, name.trim(), category.trim()) != 1) {
            throw new BusinessException(HttpStatus.NOT_FOUND, "PRODUCT_NOT_FOUND", "产品不存在");
        }
        return getUncached(tenantId, id);
    }

    @CacheEvict(cacheNames = {"business-products", "business-product"}, allEntries = true)
    public Map<String, Object> createModel(String tenantId, UUID productId, String code, String name) {
        UUID id = UUID.randomUUID();
        if (catalog.insertModel(id, tenantId, productId, code.trim(), name.trim()) != 1) {
            throw new BusinessException(HttpStatus.NOT_FOUND, "PRODUCT_NOT_FOUND", "产品不存在");
        }
        return Map.of("id", id, "product_id", productId, "model_code", code.trim(), "name", name.trim());
    }

    public Map<String, Object> createFirmware(String tenantId, UUID modelId, String version,
                                               java.time.LocalDate releasedAt) {
        UUID id = UUID.randomUUID();
        if (catalog.insertFirmware(id, tenantId, modelId, version.trim(), releasedAt) != 1) {
            throw new BusinessException(HttpStatus.NOT_FOUND, "MODEL_NOT_FOUND", "产品型号不存在");
        }
        return Map.of("id", id, "model_id", modelId, "version", version.trim(),
                "released_at", releasedAt);
    }

    private Map<String, Object> getUncached(String tenantId, UUID id) {
        Map<String, Object> product = catalog.getProduct(tenantId, id);
        if (product == null) throw new BusinessException(HttpStatus.NOT_FOUND, "PRODUCT_NOT_FOUND", "产品不存在");
        return normalizeModels(product);
    }

    private Map<String, Object> normalizeModels(Map<String, Object> product) {
        Object rawModels = product.get("models");
        if (rawModels instanceof List<?>) return product;
        try {
            List<Map<String, Object>> models = json.readValue(
                    rawModels == null ? "[]" : rawModels.toString(),
                    new TypeReference<>() {});
            Map<String, Object> normalized = new LinkedHashMap<>(product);
            normalized.put("models", models);
            return normalized;
        } catch (JacksonException exception) {
            throw new IllegalStateException("Invalid product models JSON returned by the database", exception);
        }
    }
}
