package com.nebula.product;

import com.nebula.common.BusinessException;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class ProductService {
    private final CatalogMapper catalog;

    public ProductService(CatalogMapper catalog) { this.catalog = catalog; }

    @Cacheable(cacheNames = "business-products", key = "#tenantId")
    public List<Map<String, Object>> list(String tenantId) { return catalog.listProducts(tenantId); }

    @Cacheable(cacheNames = "business-product", key = "#tenantId + ':' + #id")
    public Map<String, Object> get(String tenantId, UUID id) {
        Map<String, Object> product = catalog.getProduct(tenantId, id);
        if (product == null) throw new BusinessException(HttpStatus.NOT_FOUND, "PRODUCT_NOT_FOUND", "产品不存在");
        return product;
    }
}
