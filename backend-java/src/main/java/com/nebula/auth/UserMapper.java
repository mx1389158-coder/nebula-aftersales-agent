package com.nebula.auth;

import java.util.UUID;
import java.util.List;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;
import org.apache.ibatis.annotations.Delete;

@Mapper
public interface UserMapper {
    @Select("""
            SELECT u.id, u.tenant_id, u.username, u.email, u.password_hash, u.display_name,
                   u.status, COALESCE((SELECT ur.role_code FROM biz.user_roles ur
                     WHERE ur.user_id = u.id ORDER BY CASE ur.role_code
                     WHEN 'ADMIN' THEN 1 WHEN 'SUPPORT' THEN 2 ELSE 3 END LIMIT 1), 'USER') AS role
            FROM biz.users u
            WHERE u.tenant_id = #{tenantId} AND (u.username = #{login} OR u.email = #{login})
            """)
    UserAccount findByLogin(@Param("tenantId") String tenantId, @Param("login") String login);

    @Select("""
            SELECT u.id, u.tenant_id, u.username, u.email, u.password_hash, u.display_name,
                   u.status, COALESCE((SELECT ur.role_code FROM biz.user_roles ur
                     WHERE ur.user_id = u.id ORDER BY CASE ur.role_code
                     WHEN 'ADMIN' THEN 1 WHEN 'SUPPORT' THEN 2 ELSE 3 END LIMIT 1), 'USER') AS role
            FROM biz.users u WHERE u.id = #{id} AND u.tenant_id = #{tenantId}
            """)
    UserAccount findById(@Param("tenantId") String tenantId, @Param("id") UUID id);

    @Select("SELECT count(*) FROM biz.users")
    int count();

    @Insert("""
            INSERT INTO biz.users(id, tenant_id, username, email, password_hash, display_name)
            VALUES(#{id}, #{tenantId}, #{username}, #{email}, #{passwordHash}, #{displayName})
            """)
    int insert(UserAccount account);

    @Insert("INSERT INTO biz.user_roles(user_id, role_code) VALUES(#{userId}, #{role})")
    int insertRole(@Param("userId") UUID userId, @Param("role") String role);

    @Select("""
            SELECT u.id, u.tenant_id, u.username, u.email, u.password_hash, u.display_name,
                   u.status, COALESCE((SELECT ur.role_code FROM biz.user_roles ur
                     WHERE ur.user_id = u.id ORDER BY CASE ur.role_code
                     WHEN 'ADMIN' THEN 1 WHEN 'SUPPORT' THEN 2 ELSE 3 END LIMIT 1), 'USER') AS role
            FROM biz.users u WHERE u.tenant_id = #{tenantId} ORDER BY u.created_at
            """)
    List<UserAccount> list(String tenantId);

    @Update("UPDATE biz.users SET status = #{status}, updated_at = now() WHERE tenant_id = #{tenantId} AND id = #{id}")
    int updateStatus(@Param("tenantId") String tenantId, @Param("id") UUID id,
                     @Param("status") String status);

    @Delete("DELETE FROM biz.user_roles WHERE user_id = #{userId}")
    int deleteRoles(UUID userId);
}
