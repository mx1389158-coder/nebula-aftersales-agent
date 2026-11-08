package com.nebula.product;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.ObjectMapper;

class ProductServiceTest {
    @Test
    void exposesDatabaseJsonAsAnArrayOfModels() {
        CatalogMapper catalog = mock(CatalogMapper.class);
        UUID modelId = UUID.randomUUID();
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", UUID.randomUUID());
        row.put("product_code", "ROUTER");
        row.put("models", "[{\"id\":\"" + modelId + "\",\"model_code\":\"X2\",\"name\":\"X2\"}]");
        when(catalog.listProducts("demo")).thenReturn(List.of(row));

        List<Map<String, Object>> products = new ProductService(catalog, new ObjectMapper())
                .list("demo");

        assertThat(products.getFirst().get("models")).isInstanceOf(List.class);
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> models = (List<Map<String, Object>>) products.getFirst().get("models");
        assertThat(models).singleElement().satisfies(model -> {
            assertThat(model.get("id")).isEqualTo(modelId.toString());
            assertThat(model.get("model_code")).isEqualTo("X2");
        });
    }
}
