package com.nebula.product;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface CatalogMapper {
    @Select("""
            SELECT p.id, p.product_code, p.name, p.category,
                   COALESCE(jsonb_agg(jsonb_build_object('id', m.id, 'model_code', m.model_code,
                   'name', m.name)) FILTER (WHERE m.id IS NOT NULL), '[]'::jsonb)::text AS models
            FROM biz.products p LEFT JOIN biz.product_models m ON m.product_id = p.id
            WHERE p.tenant_id = #{tenantId} GROUP BY p.id ORDER BY p.product_code
            """)
    List<Map<String, Object>> listProducts(String tenantId);

    @Select("""
            SELECT p.id, p.product_code, p.name, p.category,
                   COALESCE(jsonb_agg(DISTINCT jsonb_build_object('id', m.id, 'model_code', m.model_code,
                   'name', m.name)) FILTER (WHERE m.id IS NOT NULL), '[]'::jsonb)::text AS models
            FROM biz.products p LEFT JOIN biz.product_models m ON m.product_id = p.id
            WHERE p.tenant_id = #{tenantId} AND p.id = #{id} GROUP BY p.id
            """)
    Map<String, Object> getProduct(@Param("tenantId") String tenantId, @Param("id") UUID id);

    @Select("""
            SELECT d.id, d.serial_no, d.nickname, d.version, d.created_at, d.updated_at,
                   p.id AS product_id, p.name AS product_name, m.id AS model_id,
                   m.model_code, m.name AS model_name, f.id AS firmware_id, f.version AS firmware_version
            FROM biz.devices d JOIN biz.product_models m ON m.id = d.model_id
            JOIN biz.products p ON p.id = m.product_id JOIN biz.firmwares f ON f.id = d.firmware_id
            WHERE d.tenant_id = #{tenantId} AND d.owner_id = #{ownerId} ORDER BY d.updated_at DESC
            """)
    List<Map<String, Object>> listDevices(@Param("tenantId") String tenantId, @Param("ownerId") UUID ownerId);

    @Select("""
            SELECT d.id, d.owner_id, d.serial_no, d.nickname, d.version, d.created_at, d.updated_at,
                   p.id AS product_id, p.name AS product_name, m.id AS model_id,
                   m.model_code, m.name AS model_name, f.id AS firmware_id, f.version AS firmware_version
            FROM biz.devices d JOIN biz.product_models m ON m.id = d.model_id
            JOIN biz.products p ON p.id = m.product_id JOIN biz.firmwares f ON f.id = d.firmware_id
            WHERE d.tenant_id = #{tenantId} AND d.id = #{id}
            """)
    Map<String, Object> getDevice(@Param("tenantId") String tenantId, @Param("id") UUID id);

    @Select("""
            SELECT count(*) FROM biz.firmwares f JOIN biz.product_models m ON m.id = f.model_id
            JOIN biz.products p ON p.id = m.product_id
            WHERE p.tenant_id = #{tenantId} AND m.id = #{modelId} AND f.id = #{firmwareId}
            """)
    int validModelFirmware(@Param("tenantId") String tenantId, @Param("modelId") UUID modelId,
                           @Param("firmwareId") UUID firmwareId);

    @Insert("""
            INSERT INTO biz.devices(id, tenant_id, owner_id, model_id, firmware_id, serial_no, nickname)
            VALUES(#{id}, #{tenantId}, #{ownerId}, #{modelId}, #{firmwareId}, #{serialNo}, #{nickname})
            """)
    int insertDevice(@Param("id") UUID id, @Param("tenantId") String tenantId,
                     @Param("ownerId") UUID ownerId, @Param("modelId") UUID modelId,
                     @Param("firmwareId") UUID firmwareId, @Param("serialNo") String serialNo,
                     @Param("nickname") String nickname);

    @Update("""
            UPDATE biz.devices SET nickname = COALESCE(#{nickname}, nickname),
              firmware_id = COALESCE(#{firmwareId}, firmware_id), version = version + 1, updated_at = now()
            WHERE id = #{id} AND tenant_id = #{tenantId} AND owner_id = #{ownerId} AND version = #{version}
            """)
    int updateDevice(@Param("id") UUID id, @Param("tenantId") String tenantId,
                     @Param("ownerId") UUID ownerId, @Param("nickname") String nickname,
                     @Param("firmwareId") UUID firmwareId, @Param("version") long version);

    @Insert("INSERT INTO biz.products(id, tenant_id, product_code, name, category) VALUES(#{id}, 'demo', #{code}, #{name}, #{category})")
    int seedProduct(@Param("id") UUID id, @Param("code") String code, @Param("name") String name,
                    @Param("category") String category);

    @Insert("INSERT INTO biz.product_models(id, product_id, model_code, name) VALUES(#{id}, #{productId}, #{code}, #{name})")
    int seedModel(@Param("id") UUID id, @Param("productId") UUID productId,
                  @Param("code") String code, @Param("name") String name);

    @Insert("INSERT INTO biz.firmwares(id, model_id, version, released_at) VALUES(#{id}, #{modelId}, #{version}, #{releasedAt})")
    int seedFirmware(@Param("id") UUID id, @Param("modelId") UUID modelId,
                     @Param("version") String version, @Param("releasedAt") LocalDate releasedAt);

    @Insert("""
            INSERT INTO biz.products(id, tenant_id, product_code, name, category)
            VALUES(#{id}, #{tenantId}, #{code}, #{name}, #{category})
            """)
    int insertProduct(@Param("id") UUID id, @Param("tenantId") String tenantId,
                      @Param("code") String code, @Param("name") String name,
                      @Param("category") String category);

    @Update("""
            UPDATE biz.products SET name = #{name}, category = #{category}, updated_at = now()
            WHERE id = #{id} AND tenant_id = #{tenantId}
            """)
    int updateProduct(@Param("tenantId") String tenantId, @Param("id") UUID id,
                      @Param("name") String name, @Param("category") String category);

    @Insert("""
            INSERT INTO biz.product_models(id, product_id, model_code, name)
            SELECT #{id}, id, #{code}, #{name} FROM biz.products
            WHERE id = #{productId} AND tenant_id = #{tenantId}
            """)
    int insertModel(@Param("id") UUID id, @Param("tenantId") String tenantId,
                    @Param("productId") UUID productId, @Param("code") String code,
                    @Param("name") String name);

    @Insert("""
            INSERT INTO biz.firmwares(id, model_id, version, released_at)
            SELECT #{id}, m.id, #{version}, #{releasedAt} FROM biz.product_models m
            JOIN biz.products p ON p.id = m.product_id
            WHERE m.id = #{modelId} AND p.tenant_id = #{tenantId}
            """)
    int insertFirmware(@Param("id") UUID id, @Param("tenantId") String tenantId,
                       @Param("modelId") UUID modelId, @Param("version") String version,
                       @Param("releasedAt") LocalDate releasedAt);

    @Select("""
            SELECT f.id, f.model_id, f.version, f.released_at
            FROM biz.firmwares f JOIN biz.product_models m ON m.id = f.model_id
            JOIN biz.products p ON p.id = m.product_id
            WHERE p.tenant_id = #{tenantId} AND m.id = #{modelId}
            ORDER BY f.released_at DESC, f.version DESC
            """)
    List<Map<String, Object>> listFirmwares(@Param("tenantId") String tenantId,
                                            @Param("modelId") UUID modelId);
}
